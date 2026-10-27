"""Explicitly approved shared dashboard access without login."""
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from flask.testing import FlaskClient
from openpyxl import Workbook
from crm_test_environment import app
import admin_access

HEADERS={'X-CRM-Request':'1'}


class DashboardAccessTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        database=patch.object(app,'DB_PATH',Path(temporary.name)/'crm.db');database.start();self.addCleanup(database.stop)
        policy=patch.dict(app.app.config,{'ADMIN_ACCESS_REQUIRED':False});policy.start();self.addCleanup(policy.stop)
        app.init_db();self.client=FlaskClient(app.app)

    def save(self,records,revision=0,headers=None):
        return self.client.post('/api/workspace',json={'revision':revision,'values':{'hk_v2_clients':records}},headers=headers or HEADERS)

    def test_access_requires_no_account_or_password(self):
        status=self.client.get('/api/admin/session').json
        self.assertTrue(status['can_edit']);self.assertFalse(status['login_required']);self.assertFalse(status['admin'])
        self.assertIsNone(status['username'])
        self.assertEqual(self.client.get('/admin').status_code,302)
        self.assertEqual(self.client.get('/admin').headers['Location'],'/')
        for url in ['/','/activity']:
            page=self.client.get(url)
            self.assertEqual(page.status_code,200)
            self.assertNotIn('type="password"',page.get_data(as_text=True))

    def test_any_dashboard_user_can_add_edit_remove_and_is_honestly_logged(self):
        self.assertEqual(self.save([{'id':'C1','name':'Hospital A'}]).status_code,200)
        self.assertEqual(self.save([{'id':'C1','name':'Hospital B'}],1).status_code,200)
        self.assertEqual(self.save([],2).status_code,200)
        history=self.client.get('/api/admin/activity').json['events']
        self.assertEqual(len(history),3)
        self.assertTrue(all(event['actor']=='Dashboard user' for event in history))
        changes=history[0]['details']['operations'][0]['changes']['hk_v2_clients']
        self.assertEqual(changes['removed'],1)

    def test_upload_and_spreadsheet_source_do_not_require_login(self):
        book=Workbook();book.active.append(['Name','City']);book.active.append(['Synthetic Hospital','Jaipur'])
        stream=BytesIO();book.save(stream);stream.seek(0)
        self.assertEqual(self.client.post('/api/import-excel',data={'file':(stream,'synthetic.xlsx')}).status_code,200)
        source=self.client.post('/api/spreadsheet/source',json={'link':'https://docs.google.com/spreadsheets/d/synthetic_sheet_123456/edit','mode':'form_responses'},headers=HEADERS)
        self.assertEqual(source.status_code,200)

    def test_removal_still_needs_exact_confirmation_without_password(self):
        payload={'scope':'worksheet','name':'Sheet A','confirmation':'wrong'}
        self.assertEqual(self.client.post('/api/admin/remove-import',json=payload).status_code,400)
        payload['confirmation']='REMOVE Sheet A'
        self.assertEqual(self.client.post('/api/admin/remove-import',json=payload).status_code,200)
        self.assertEqual(self.client.post('/api/dashboard/reset',json={'confirmed_reset':True,'confirmation':'wrong'}).status_code,400)

    def test_origin_validation_and_stale_edit_protection_remain(self):
        self.assertEqual(self.save([{'id':'C1','name':'Hospital'}]).status_code,200)
        self.assertEqual(self.save([],0).status_code,409)
        self.assertEqual(self.save([],1,{**HEADERS,'Origin':'https://untrusted.example'}).status_code,403)
        self.assertEqual(len(self.client.get('/api/workspace').json['workspace']['values']['hk_v2_clients']),1)

    def test_audit_failure_keeps_the_last_saved_records(self):
        with patch.object(admin_access,'add_event',side_effect=app.sqlite3.DatabaseError('audit unavailable')):
            self.assertEqual(self.save([{'id':'C1','name':'Hospital'}]).status_code,503)
        self.assertEqual(self.client.get('/api/workspace').json['workspace']['revision'],0)


if __name__=='__main__':unittest.main()
