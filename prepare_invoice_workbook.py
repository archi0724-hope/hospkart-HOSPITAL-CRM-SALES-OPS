"""Preserve a supplied invoice workbook for the local dashboard.

Run: .venv/Scripts/python.exe prepare_invoice_workbook.py path/to/workbook.xlsx
The existing Excel parser preserves all worksheet columns and cell values.
"""
import json
import sys
from pathlib import Path

import app


def prepare(path):
    source = Path(path)
    with source.open('rb') as stream:
        response = app.app.test_client().post('/api/import-excel', data={'file': (stream, source.name)})
    if response.status_code != 200:
        raise ValueError(response.json['error'])
    payload = {'filename': source.name, 'workbook': {
        'sheets': [{'name': name, 'rows': rows} for name, rows in response.json['sheets'].items()],
        'sheet_previews': response.json['sheet_previews'],
    }}
    target = app.BASE_DIR / 'data' / 'imported_invoice_workbook.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Prepared:', source.name)
    print('Worksheet rows:', {sheet['name']: len(sheet['rows']) for sheet in payload['workbook']['sheets']})


if __name__ == '__main__':
    prepare(sys.argv[1])
