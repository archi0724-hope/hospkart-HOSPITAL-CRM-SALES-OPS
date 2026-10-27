"""Existing-link form imports use fixed Google reads and preserve saved data."""
import csv
from io import StringIO
import unittest
from unittest.mock import Mock, patch

import test_spreadsheet_sync as fixtures
LINK, SheetError = fixtures.LINK, fixtures.SheetError
from test_form_responses import COLUMNS, FORM_LINK
from public_form_sheet import PublicFormSheet

PROFILE = {'gid':1245915998, 'tab_name':'Form Responses 1', 'title':'Synthetic form responses',
           'locale':'en_US', 'timezone':'Asia/Calcutta'}


class ExistingLinkFormTests(unittest.TestCase):
    post = fixtures.SpreadsheetTests.post
    status = fixtures.SpreadsheetTests.status
    connect = fixtures.SpreadsheetTests.connect

    def setUp(self):
        fixtures.SpreadsheetTests.setUp(self)
        self.rows = [COLUMNS,
            ['10/23/2026 15:27:19','Sales Team','10/23/2026','Customer A','0012345678','not provided',
             'Product Inquiry','Hospital A','Medical equipment','Need a pump','High'],
            ['10/23/2026 15:31:41','Sales Team','10/23/2026','Customer B','0012345679','no mail provided',
             'New Sales Lead','Hospital B','Disposables','Need syringes','Medium']]
        self.response = Mock(status_code=200, headers={'Content-Type':'text/csv; charset=utf-8'})
        self.response.__enter__ = Mock(return_value=self.response)
        self.response.__exit__ = Mock(return_value=False)
        self.set_rows(self.rows)
        self.network = patch('public_form_sheet.requests.get', return_value=self.response)
        self.get = self.network.start();self.addCleanup(self.network.stop)
        self.payload = {'link':LINK,'mode':'form_responses','form_link':FORM_LINK,'response_tab':'Form Responses 1',
            'auto_minutes':5,'public_source':PROFILE,'response_mapping':dict(zip(
                ['timestamp','executive','created_date','name','mobile','email','submission_type','company','product','details','priority'],COLUMNS))}

    def set_rows(self, rows):
        output=StringIO();csv.writer(output).writerows(rows)
        self.response.iter_content.side_effect=lambda *_:[output.getvalue().encode()]

    def test_public_response_import_is_idempotent_and_keeps_form_link(self):
        first=self.connect(self.payload)
        self.assertEqual((len(first['leads']),len(first['queries'])),(2,1))
        self.assertEqual(first['connection']['public_source'],PROFILE)
        self.assertEqual(first['source']['form_link'],FORM_LINK)
        second=self.post('sync').json
        self.assertEqual(first['leads'],second['leads'])
        self.assertEqual(first['queries'],second['queries'])
        self.assertTrue(all(counts['added']==0 for counts in second['connection']['report']['counts'].values()))
        args,kwargs=self.get.call_args
        self.assertEqual(args[0],'https://docs.google.com/spreadsheets/d/private_sheet_123456/export')
        self.assertEqual(kwargs['params'],{'format':'csv','gid':1245915998})
        self.assertNotIn('headers',kwargs)

    def test_new_responses_appear_without_reimporting_duplicates(self):
        first=self.connect(self.payload)
        self.rows.append(['10/27/2026 16:00:00','Sales Team','10/27/2026','Customer C','0012345680','',
                          'Customer Query','Hospital C','Services','Need assistance','Medium'])
        self.set_rows(self.rows)
        result=self.post('sync').json
        self.assertEqual((len(result['leads']),len(result['queries'])),(3,2))
        self.assertEqual(result['connection']['report']['counts']['leads']['added'],1)
        self.assertEqual(result['connection']['report']['counts']['queries']['added'],1)

    def test_access_revocation_and_html_keep_previous_records(self):
        first=self.connect(self.payload)
        for status,mime in [(403,'text/html'),(200,'text/html')]:
            self.response.status_code=status;self.response.headers={'Content-Type':mime}
            self.assertGreaterEqual(self.post('sync').status_code,400)
            self.assertEqual(self.status()['leads'],first['leads'])
            self.assertEqual(self.status()['queries'],first['queries'])
            self.assertEqual(self.status()['connection']['last_success'],first['connection']['last_success'])

    def test_invalid_source_configuration_cannot_target_other_hosts(self):
        for profile in [{**PROFILE,'gid':True},{**PROFILE,'gid':-1},{**PROFILE,'url':'http://localhost/private'},
                        {**PROFILE,'timezone':'bad/timezone'}]:
            with self.assertRaises(SheetError):
                PublicFormSheet('private_sheet_123456',profile,SheetError)
        self.assertEqual(self.post('preview',{**self.payload,'link':'http://localhost/private'}).status_code,400)
        self.assertEqual(self.post('preview',{**self.payload,'mode':'tabs'}).status_code,400)

    def test_oversized_sources_are_rejected_before_import(self):
        provider=PublicFormSheet('private_sheet_123456',PROFILE,SheetError,max_bytes=10)
        with self.assertRaises(SheetError):provider.inspect('private_sheet_123456')


if __name__=='__main__':unittest.main()
