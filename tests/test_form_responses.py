"""Form response imports use synthetic fixtures and isolated SQLite databases."""
import copy
import unittest
import test_spreadsheet_sync as fixtures

LINK, HEADERS = fixtures.LINK, fixtures.HEADERS

FORM_LINK = 'https://docs.google.com/forms/d/e/example_private_form_123456/viewform'
COLUMNS = ['Timestamp', 'Lead Generator Name', 'Date of Lead Generation', 'Customer Full Name',
           'Customer Contact Number', 'Customer Email Address', 'Type of Submission',
           'Hospital or Organization Name', 'Products or Services of Interest',
           'Detailed Description of Lead or Query', 'Urgency Level']


class FormResponseTests(unittest.TestCase):
    post = fixtures.SpreadsheetTests.post
    status = fixtures.SpreadsheetTests.status
    connect = fixtures.SpreadsheetTests.connect

    def setUp(self):
        fixtures.SpreadsheetTests.setUp(self)
        self.provider.rows = [[COLUMNS,
            ['10/23/2026 15:27:19', 'Sales Team', '10/23/2026', 'Customer A', '0012345678', 'not provided',
             'Product Inquiry', 'Hospital A', 'Medical Equipment', 'Need a pump', 'High'],
            ['10/23/2026 15:31:41', 'Sales Team', '10/23/2026', 'Customer A', '0098765432', 'a@example.com',
             'New Sales Lead', 'Hospital A', 'Disposables', 'Need syringes', 'Medium']]]
        self.provider.inspect = lambda file_id: {'id': file_id, 'name': 'Form responses', 'url': LINK.split('#')[0],
            'locale': 'en_US', 'timezone': 'Asia/Calcutta', 'tabs': [{'id': 1245915998, 'name': 'Form Responses 1'}]}
        self.payload = {'link': LINK, 'mode': 'form_responses', 'form_link': FORM_LINK,
            'response_tab': 'Form Responses 1', 'auto_minutes': 5,
            'response_mapping': dict(zip(['timestamp', 'executive', 'created_date', 'name', 'mobile', 'email',
                                         'submission_type', 'company', 'product', 'details', 'priority'], COLUMNS))}

    def test_response_create_edit_reorder_and_repeat(self):
        preview = self.post('preview', self.payload).json
        self.assertEqual(self.status()['leads'], [])
        self.assertEqual(len(preview['report']['warnings']), 1)
        result = self.post('import', {'token': preview['token']}).json
        self.assertEqual((len(result['leads']), len(result['queries'])), (2, 1))
        query = result['queries'][0]
        lead = next(row for row in result['leads'] if row['id'] == query['lead_id'])
        self.assertEqual(lead['mobile'], '0012345678')
        self.assertEqual(lead['email'], '')
        self.assertEqual(lead['status'], 'Query Received')
        self.assertEqual(query['created_date'], '2026-10-23T15:27:19+05:30')
        self.provider.rows[0][1][9] = 'Edited pump request'
        self.provider.rows[0][1:] = list(reversed(self.provider.rows[0][1:]))
        updated = self.post('sync').json
        self.assertEqual(updated['queries'][0]['id'], query['id'])
        self.assertEqual(updated['queries'][0]['details'], 'Edited pump request')
        self.assertNotEqual(updated['queries'][0]['updated_date'], query['updated_date'])
        repeated = self.post('sync').json
        self.assertEqual(repeated['connection']['report']['counts']['leads']['unchanged'], 2)
        self.assertEqual(repeated['connection']['report']['counts']['queries']['unchanged'], 1)
        self.provider.rows[0] = [COLUMNS]
        self.assertEqual(len(self.post('sync').json['leads']), 2)

    def test_duplicate_timestamps_missing_values_and_bad_email_rejected(self):
        self.provider.rows[0].append(copy.deepcopy(self.provider.rows[0][1]))
        self.provider.rows[0][2][5] = 'bad email'
        result = self.connect(self.payload)
        self.assertEqual(result['leads'], [])
        self.assertEqual(result['queries'], [])
        self.assertEqual(result['connection']['report']['counts']['leads']['rejected'], 3)
        self.provider.rows[0] = [COLUMNS, ['', 'Team', '', 'Customer', '', '', 'Product Inquiry', '', '', 'Details']]
        self.assertEqual(self.post('sync').json['connection']['report']['counts']['leads']['rejected'], 1)

    def test_immutable_response_ids_allow_same_timestamp_and_timestamp_edit(self):
        self.provider.rows[0][0] = COLUMNS + ['Response ID']
        self.provider.rows[0][1].append('response-0001')
        self.provider.rows[0][2].append('response-0002')
        self.provider.rows[0][2][0] = self.provider.rows[0][1][0]
        self.payload['response_mapping']['response_id'] = 'Response ID'
        initial = self.connect(self.payload)
        ids = {lead['id'] for lead in initial['leads']}
        self.provider.rows[0][1][0] = '10/24/2026 15:27:19'
        self.assertEqual({lead['id'] for lead in self.post('sync').json['leads']}, ids)

    def test_invalid_duplicate_response_cannot_make_identity_unambiguous(self):
        self.provider.rows[0].append(copy.deepcopy(self.provider.rows[0][1]))
        self.provider.rows[0][-1][6] = 'Unknown submission type'
        result = self.connect(self.payload)
        self.assertEqual(len(result['leads']), 1)
        self.assertEqual(len(result['queries']), 0)
        self.assertEqual(result['connection']['report']['counts']['leads']['rejected'], 2)

    def test_source_links_persist_without_claiming_connection(self):
        result = self.post('source', {'link': LINK, 'form_link': FORM_LINK, 'mode': 'form_responses'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.status()['source']['form_link'], FORM_LINK)
        self.assertIsNone(self.status()['connection'])
        for invalid in ['javascript:alert(1)', 'https://evil.example/form', FORM_LINK.replace('docs.google.com', 'evil@docs.google.com')]:
            self.assertEqual(self.post('source', {'link': LINK, 'form_link': invalid}).status_code, 400)

    def test_form_errors_keep_last_saved_data_and_status(self):
        before = self.connect(self.payload)
        self.provider.rows[0][0][0] = 'Renamed timestamp'
        self.assertEqual(self.post('sync').status_code, 400)
        after = self.status()
        self.assertEqual(after['leads'], before['leads'])
        self.assertEqual(after['connection']['last_success'], before['connection']['last_success'])

    def test_form_sync_preserves_crm_pipeline_stage(self):
        self.connect(self.payload)
        workspace = self.client.get('/api/workspace').json['workspace']
        leads = workspace['values']['hk_v2_leads']
        for lead in leads: lead['status'] = 'Contacted'
        saved = self.client.post('/api/workspace', json={'revision': workspace['revision'], 'values': {'hk_v2_leads': leads}}, headers=HEADERS)
        self.assertEqual(saved.status_code, 200)
        self.post('sync')
        self.assertTrue(all(row['status'] == 'Contacted' for row in self.client.get('/api/workspace').json['workspace']['values']['hk_v2_leads']))
