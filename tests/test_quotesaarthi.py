import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from quotesaarthi.runtime import QuoteSaarthiService


def make_catalogue(path):
    columns=['id','product_name','category','manufacturer','vendor_name','price','specs','warranty','stock','vendor_status','product_status']
    rows=[['1','IV Set','Injection','Test','Vendor A',10,'Luer lock','Not provided',100,'Active','Published'],['2','IV Set','Injection','Test','Vendor B',12,'Luer lock','Not provided',0,'Active','Published'],['3','Hospital Bed','Equipment','Test','Vendor A',1000,'Manual bed','1 year',10,'Active','Published'],['4','IV Set','Injection','Test','Vendor C',8,'Luer lock','Not provided',50,'Inactive','Published']]
    with Path(path).open('w',newline='',encoding='utf-8') as stream:
        writer=csv.writer(stream);writer.writerow(columns);writer.writerows(rows)


class QuoteSaarthiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.catalog=self.root/'products.csv';make_catalogue(self.catalog)
        self.service=QuoteSaarthiService(self.catalog,self.root)
        self.env=patch.dict(os.environ,{'QUOTESAARTHI_USE_OLLAMA':'false'});self.env.start();self.addCleanup(self.env.stop)
        self.provider=patch('quotesaarthi.runtime.get_service',return_value=self.service);self.provider.start();self.addCleanup(self.provider.stop)
        self.client=app.app.test_client()

    def chat(self,message,session=None):
        return self.client.post('/api/quotesaarthi/chat',json={'message':message,'session_id':session})

    def test_catalogue_search_does_not_need_an_ai_provider(self):
        with patch('app.requests.post') as post:
            response=self.chat('IV Set vendor listing')
        self.assertEqual(response.status_code,200)
        self.assertIn('Vendor A',response.json['reply'])
        self.assertIn('INR 8.00',response.json['reply'])
        self.assertEqual(len(response.json['session_id']),43)
        post.assert_not_called()

    def test_quote_arithmetic_and_downloads_are_conversation_scoped(self):
        response=self.chat('Quote IV Set 10 units with 5% discount and GST 18%')
        self.assertEqual(response.status_code,200)
        data=response.json;self.assertEqual(len(data['exports']),2)
        self.assertIn('INR 89.68',data['reply'])
        name=next(export['name'] for export in data['exports'] if export['format']=='json')
        with self.client.post('/api/quotesaarthi/download/'+name,json={'session_id':data['session_id']}) as download:
            quote=json.loads(download.data)
        self.assertTrue(quote['draft'])
        self.assertEqual(quote['discount_amount'],4)
        self.assertEqual(quote['gst_amount'],13.68)
        self.assertEqual(quote['final_amount'],89.68)
        pdf=next(export['name'] for export in data['exports'] if export['format']=='pdf')
        with self.client.post('/api/quotesaarthi/download/'+pdf,json={'session_id':data['session_id']}) as download:
            self.assertTrue(download.data.startswith(b'%PDF'))
        other=self.chat('hello').json['session_id']
        self.assertEqual(self.client.post('/api/quotesaarthi/download/'+name,json={'session_id':other}).status_code,404)
        self.assertEqual(self.client.post('/api/quotesaarthi/download/'+name,json={}).status_code,403)

    def test_missing_gst_is_clarified_and_followup_generates_quote(self):
        first=self.chat('Quote IV Set 10 units')
        self.assertIn('GST rate confirm',first.json['reply'])
        self.assertEqual(first.json['exports'],[])
        second=self.chat('GST 5%',first.json['session_id'])
        self.assertIn('GST (5%',second.json['reply'])
        self.assertEqual(len(second.json['exports']),2)

    def test_missing_quantity_is_not_assumed(self):
        response=self.chat('Quote IV Set GST 18%')
        self.assertIn('Quantity confirm',response.json['reply'])
        self.assertEqual(response.json['exports'],[])

    def test_invalid_numbers_do_not_export(self):
        for query in ['Quote IV Set 0 units GST 18%','Quote IV Set -10 units GST 18%','Quote IV Set 10 units GST -5%','Quote IV Set 10 units GST 101%','Quote IV Set 10 units 150% discount GST 18%','Quote IV Set 10 units -5% discount GST 18%']:
            with self.subTest(query=query):
                response=self.chat(query)
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json['exports'],[])
                self.assertNotIn('DRAFT QUOTATION',response.json['reply'])

    def test_vendor_filter_does_not_leak_other_vendor_offers(self):
        response=self.chat('Vendor A IV Set listing')
        self.assertIn('Vendor A',response.json['reply'])
        self.assertNotIn('Vendor B',response.json['reply'])
        self.assertNotIn('Vendor C',response.json['reply'])

    def test_active_and_stock_filters_keep_original_catalogue(self):
        first=self.chat('IV Set active vendors only in-stock')
        self.assertIn('Vendor A',first.json['reply'])
        self.assertNotIn('Vendor B',first.json['reply'])
        self.assertNotIn('Vendor C',first.json['reply'])
        second=self.chat('IV Set vendor listing',first.json['session_id'])
        self.assertIn('Vendor C',second.json['reply'])

    def test_conversations_do_not_share_selected_products(self):
        first=self.chat('Quote IV Set 10 units')
        second=self.chat('Quote Hospital Bed 2 units')
        a=self.chat('GST 18%',first.json['session_id'])
        b=self.chat('GST 5%',second.json['session_id'])
        self.assertIn('Product: IV Set',a.json['reply'])
        self.assertIn('Product: Hospital Bed',b.json['reply'])
        self.assertNotEqual(a.json['session_id'],b.json['session_id'])

    def test_new_conversation_resets_selected_product(self):
        first=self.chat('Quote IV Set 10 units')
        self.chat('cancel',first.json['session_id'])
        response=self.chat('GST 18%',first.json['session_id'])
        self.assertEqual(response.json['exports'],[])

    def test_invalid_requests_and_expired_sessions(self):
        for body in [[],{'message':123},{'message':'x'*4001},{'message':'hello','session_id':'../unsafe'}]:
            self.assertEqual(self.client.post('/api/quotesaarthi/chat',json=body).status_code,400)
        self.assertEqual(self.chat('hello','x'*43).status_code,409)

    @patch('app.smartbot_reply',return_value='Source-backed CRM summary')
    def test_crm_summary_keeps_existing_context(self, reply):
        context={'kpis':{'workspace_records':2168}}
        response=self.client.post('/api/quotesaarthi/chat',json={'message':'Summarize the CRM dashboard','context':context})
        self.assertEqual(response.json['reply'],'Source-backed CRM summary')
        reply.assert_called_once_with('Summarize the CRM dashboard',context)

    def test_missing_catalogue_does_not_break_dashboard(self):
        with patch('quotesaarthi.runtime.get_service',return_value=QuoteSaarthiService(self.root/'missing.csv',self.root)):
            self.assertEqual(self.chat('IV Set listing').status_code,503)
        self.assertEqual(self.client.get('/').status_code,200)

    def test_multi_item_requests_require_separate_quotes(self):
        response=self.chat('Quote IV Set 10 units and Hospital Bed 2 units with GST 18%')
        self.assertIn('ek product supported',response.json['reply'])
        self.assertEqual(response.json['exports'],[])

    def test_fresh_quote_does_not_reuse_previous_quantity_or_tax(self):
        first=self.chat('Quote IV Set 10 units with GST 18%')
        token=first.json['session_id']
        self.assertIn('Quantity confirm',self.chat('Quote Hospital Bed',token).json['reply'])
        self.assertIn('GST rate confirm',self.chat('Quote Hospital Bed 2 units',token).json['reply'])
        self.assertEqual(self.chat('Quote Hospital Bed 2 units',token).json['exports'],[])

    def test_invoice_workflow_collects_confirmed_gst(self):
        gst_only=self.chat('make a tax invoice of IV Set 10 units with GST 18%')
        self.assertIn('Discount',gst_only.json['reply'])
        response=self.chat('make a tax invoice of IV Set')
        token=response.json['session_id']
        self.assertIn('Quantity',response.json['reply'])
        self.assertIn('Discount',self.chat('10',token).json['reply'])
        self.assertIn('GST rate confirm',self.chat('5',token).json['reply'])
        self.assertIn('0–100%',self.chat('150',token).json['reply'])
        for value in ['18','Test Hospital','Rajasthan','08','NA','Jaipur','Rajasthan','NA','NA','NA','NA','Review terms','NA']:
            response=self.chat(value,token)
        self.assertEqual(len(response.json['exports']),2,response.json)
        self.assertIn('INR 89.68',response.json['reply'])


if __name__=='__main__':unittest.main()
