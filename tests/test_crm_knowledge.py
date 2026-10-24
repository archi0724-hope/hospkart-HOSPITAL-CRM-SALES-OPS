"""Source-backed assistant tests; synthetic SQLite data, no external AI calls."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from crm_test_environment import app
from quotesaarthi.crm import build_knowledge, matches, reply


class CRMKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.db_patch=patch.object(app,'DB_PATH',Path(self.temp.name)/'crm.db')
        self.db_patch.start();self.addCleanup(self.db_patch.stop)
        app.init_db();self.client=app.app.test_client()
        self.save({'hk_v2_clients':[
            {'id':'C001','name':'Alpha Hospital','city':'Jaipur','status':'Contacted','next':'2026-10-22','contact':'Alpha contact','requirement':'Need a pump'},
            {'id':'C002','name':'Beta Clinic','city':'Delhi','status':'Delivered','next':'2026-10-23'}],
            'hk_v2_leads':[{'id':'L001','name':'Alpha Hospital','city':'Jaipur','status':'Query Received','next':'2026-10-23','product':'Pump'},
                           {'id':'L002','name':'Gamma Hospital','status':'New Lead','next':'2026-10-25'}]})

    def save(self, values):
        workspace=self.client.get('/api/workspace').json['workspace']
        response=self.client.post('/api/workspace',json={'revision':workspace['revision'],'values':values},headers={'X-CRM-Request':'1'})
        self.assertEqual(response.status_code,200,response.json)

    def knowledge(self):
        with app.db_conn() as conn:
            conn.execute('BEGIN')
            return build_knowledge(conn,datetime(2026,10,23,12,tzinfo=ZoneInfo('Asia/Kolkata')))

    def chat(self,message,context=None):
        with patch('app.requests.post') as outgoing:
            response=self.client.post('/api/quotesaarthi/chat',json={'message':message,'context':context or {}})
        outgoing.assert_not_called()
        self.assertEqual(response.status_code,200,response.json)
        return response.json

    def test_counts_match_saved_records_and_new_edits_are_immediate(self):
        initial=self.chat('Summarize CRM dashboard',{'kpis':{'workspace_records':99999}})
        self.assertIn('4 workspace records',initial['reply']);self.assertNotIn('99999',initial['reply'])
        self.save({'hk_v2_leads':[{'id':'L003','name':'New Hospital','status':'New Lead'}]})
        after=self.chat('Show leads')
        self.assertIn('Leads & Queries: 1 records',after['reply'])
        self.assertGreater(after['knowledge']['revision'],initial['knowledge']['revision'])

    def test_counts_keep_workspace_copies_and_distinct_clients_separate(self):
        knowledge=self.knowledge()
        self.assertEqual(knowledge['workspace_records'],4)
        self.assertEqual(knowledge['workspaces']['clients']['records'],2)
        self.assertEqual(knowledge['workspaces']['leads']['records'],2)
        self.assertIn('not a unique hospital count',reply('CRM summary',knowledge))

    def test_followup_counts_use_ist_and_show_sample_scope(self):
        knowledge=self.knowledge()
        self.assertEqual(knowledge['followup_counts'],{'scheduled':4,'overdue':1,'due_today':2})
        answer=reply('Show overdue follow-ups',knowledge)
        self.assertIn('Alpha Hospital',answer);self.assertNotIn('Beta Clinic [',answer)
        self.assertIn('Closed-stage records',answer)

    def test_queries_match_dashboard_fallback_and_independent_queries(self):
        self.assertEqual(len(self.knowledge()['queries']),1)
        with app.db_conn() as conn:
            conn.execute('INSERT INTO sheet_leads VALUES (?,?)',('L001',json.dumps({'id':'L001','name':'Alpha Hospital'})))
            conn.execute('INSERT INTO sheet_queries VALUES (?,?,?)',('Q0001','L001',json.dumps({'id':'Q0001','lead_id':'L001','subject':'Real query','status':'Open'})))
        knowledge=self.knowledge()
        self.assertEqual(len(knowledge['queries']),1)
        self.assertIn('Q0001',reply('Show queries',knowledge));self.assertNotIn('CRM-Q:L001',reply('Show queries',knowledge))

    def test_imported_iso_timestamps_are_valid_followup_dates_in_ist(self):
        self.save({'hk_v2_leads':[{'id':'T1','name':'Timestamp lead','next':'2026-10-23T00:00:00'},
                                   {'id':'T2','name':'Zoned lead','next':'2026-10-23T23:45:00-04:00'}]})
        knowledge=self.knowledge()
        self.assertTrue(knowledge['checks']['passed'])
        dates={row['id']:row['next'] for row in knowledge['followups']}
        self.assertEqual(dates['T1'],'2026-10-23')
        self.assertEqual(dates['T2'],'2026-10-24')

    def test_complaints_resolutions_and_untrusted_data_are_read_only(self):
        with app.db_conn() as conn:
            workspace=json.loads(conn.execute('SELECT data FROM crm_workspace').fetchone()['data'])
            workspace['hk_v2_complaints']=[{'id':'CMP-1','customer_name':'Alpha Hospital','subject':'Damaged item',
                'status':'Resolved','priority':'High','assigned_owner':'Service','resolution':'Replaced item'}]
            conn.execute('UPDATE crm_workspace SET data=?',(json.dumps(workspace),))
        answer=self.chat('Show resolved complaints')['reply']
        self.assertIn('1 resolved/closed',answer);self.assertIn('Replaced item',answer)
        self.assertIn('read-only',self.chat('Resolve complaints')['reply'])
        self.assertEqual(self.knowledge()['complaints'][0]['status'],'Resolved')

    def test_invoice_totals_deduplicate_cancelled_and_item_rows(self):
        rows=[{'Invoice No.':'INV001','Client / Hospital':'Alpha','Delivery City / Location':'Jaipur','Invoice Total (₹)':'₹1,250.50'},
              {'Invoice No.':'inv001','Client / Hospital':'Alpha','Invoice Total (₹)':'1250.50'},
              {'Invoice No.':'INV002','Invoice Status':'Cancelled','Invoice Total (₹)':'9000'}]
        self.save({'hk_v2_invoice_workbook':{'filename':'test.xlsx','sheets':[{'name':'Client Summary','rows':rows}]}})
        analysis=self.knowledge()['invoice_analysis']
        self.assertEqual(analysis['invoice_count'],1);self.assertEqual(analysis['invoice_value'],'1250.50')
        self.assertIn('INR 1250.50',self.chat('Invoice summary')['reply'])

    def test_missing_or_invalid_invoice_totals_are_not_guessed(self):
        self.assertIn('unavailable',self.chat('Invoice summary')['reply'])
        self.save({'hk_v2_invoice_workbook':{'sheets':[{'name':'Client Summary','rows':[{'Invoice No.':'I1','Invoice Total (₹)':'unknown'}]}]}})
        self.assertIsNone(self.knowledge()['invoice_analysis']['invoice_value'])
        self.assertFalse(self.knowledge()['checks']['passed'])

    def test_knowledge_checks_detect_bad_ids_dates_and_query_relationships(self):
        self.save({'hk_v2_leads':[{'id':'DUP','name':'One','next':'bad date'},{'id':'DUP','name':'Two'}]})
        reasons={item['reason'] for item in self.knowledge()['checks']['issues']}
        self.assertIn('Duplicate record IDs',reasons)
        self.assertIn('Invalid follow-up dates excluded from date queues',reasons)
        response=self.client.get('/api/quotesaarthi/knowledge')
        self.assertEqual(response.status_code,200)
        self.assertIn('no-store',response.headers['Cache-Control'])
        self.assertNotIn('Alpha contact',response.get_data(as_text=True))

    def test_drafts_lookup_saved_reference_and_ignore_forged_browser_fields(self):
        answer=self.chat('Draft a WhatsApp follow-up',{'selected_client':{'id':'C001','name':'Forged','requirement':'Guarantee delivery today'}})['reply']
        self.assertIn('Alpha contact',answer);self.assertIn('pump',answer)
        self.assertNotIn('Guarantee',answer);self.assertNotIn('Forged',answer)
        self.assertIn('Draft only',answer)
        self.assertIn('Select a hospital/client',self.chat('Draft a WhatsApp follow-up')['reply'])

    def test_lookup_keeps_duplicate_workspace_records_and_ids_visible(self):
        answer=self.chat('Find Alpha Hospital')['reply']
        self.assertIn('C001',answer);self.assertIn('L001',answer)
        self.assertIn('Hospitals & Clients',answer);self.assertIn('Leads & Queries',answer)

    def test_product_and_invoice_workflows_keep_catalogue_routing(self):
        for message in ('Hospital Bed vendor listing','make a tax invoice of IV Set 10 units with GST 18%','Quote IV Set 50 units','GST 18%'):
            self.assertFalse(matches(message),message)
        for message in ('CRM summary','Invoice summary','Show queries','pending complaints','Find Alpha Hospital'):
            self.assertTrue(matches(message),message)

    def test_database_failure_does_not_guess_or_use_browser_cache(self):
        with patch('quotesaarthi.crm.build_knowledge',side_effect=RuntimeError('private failure details')):
            result=self.client.post('/api/quotesaarthi/chat',json={'message':'CRM summary','context':{'kpis':{'workspace_records':777}}})
        self.assertEqual(result.status_code,503)
        self.assertNotIn('private failure',result.json['error']);self.assertNotIn('777',str(result.json))
