import json
import re
import unittest
from io import BytesIO

from openpyxl import Workbook

import app


class ExcelImportTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def upload(self, rows, header_rows=None):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Already Served'
        for row in rows:
            sheet.append(row)
        stream = BytesIO()
        workbook.save(stream)
        workbook.close()
        stream.seek(0)
        data = {'file': (stream, 'served.xlsx')}
        if header_rows is not None:
            data['header_rows'] = json.dumps(header_rows)
        return self.client.post('/api/import-excel', data=data)

    def test_annotated_headers_after_title_and_blank_rows(self):
        response = self.upload([['Already Served Customers'], [], ['Hospital Name (as per invoice)', 'City', 'Email'], ['Aarogya Hospital', 'Jaipur', 'purchase@example.com']])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['sheet_previews']['Already Served']['header_row'], 2)
        self.assertEqual(response.json['sheets']['Already Served'][0]['Hospital Name (as per invoice)'], 'Aarogya Hospital')

    def test_expanded_alias_after_more_than_twenty_intro_rows(self):
        rows = [['Served client register']] + [[] for _ in range(25)] + [['Name of the Party', 'City'], ['City Hospital', 'Kota']]
        response = self.upload(rows)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['sheet_previews']['Already Served']['header_row'], 26)
        self.assertEqual(len(response.json['sheets']['Already Served']), 1)

    def test_unrecognized_name_column_returns_preview_for_manual_mapping(self):
        response = self.upload([['Already Served'], [], ['Buyer / Outlet', 'City', 'Email'], ['Custom Hospital', 'Jaipur', 'buyer@example.com']])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['sheet_previews']['Already Served']['header_row'], 2)
        self.assertEqual(response.json['sheets']['Already Served'][0]['Buyer / Outlet'], 'Custom Hospital')
        self.assertEqual(response.json['sheet_previews']['Already Served']['rows'][2][0], 'Buyer / Outlet')

    def test_explicit_header_row_reparses_unknown_columns(self):
        rows = [['Company register'], ['Notes'], ['Purchaser Label', 'Location'], ['Test Hospital', 'Jaipur']]
        response = self.upload(rows, {'Already Served': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['sheets']['Already Served'], [{'Purchaser Label': 'Test Hospital', 'Location': 'Jaipur'}])

    def test_blank_and_duplicate_headers_do_not_drop_columns(self):
        response = self.upload([['Hospital Name', 'Remarks', 'Remarks', None], ['Test Hospital', 'First note', 'Second note', 'Extra field']])
        row = response.json['sheets']['Already Served'][0]
        self.assertEqual(row['Remarks'], 'First note')
        self.assertEqual(row['Remarks (2)'], 'Second note')
        self.assertEqual(row['Column 4'], 'Extra field')

    def test_invalid_header_selection_has_actionable_error(self):
        for value in [-1, 999, '1', True]:
            with self.subTest(value=value):
                response = self.upload([['Hospital Name'], ['Test Hospital']], {'Already Served': value})
                self.assertEqual(response.status_code, 400)
                self.assertIn('valid header row', response.json['error'])
        self.assertEqual(self.upload([['Hospital Name'], ['Test Hospital']], []).status_code, 400)

    def test_browser_uses_the_same_name_aliases_as_backend(self):
        html = self.client.get('/').get_data(as_text=True)
        aliases = json.loads(re.search(r'const clientNameAliases=(\[[^\n]*\]);', html).group(1))
        self.assertEqual(set(aliases), app.CLIENT_NAME_HEADERS)


if __name__ == '__main__':
    unittest.main()
