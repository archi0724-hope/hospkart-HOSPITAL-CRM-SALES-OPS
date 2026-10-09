"""Prepare private workbook checks in temporary storage, never in the live app."""
import json
import os
from pathlib import Path

import app


def prepare_test_workbook(directory):
    saved = app.DATA_DIR / 'imported_invoice_workbook.json'
    source = os.getenv('HOSPKART_TEST_WORKBOOK', '').strip()
    if source:
        path = Path(source)
        with path.open('rb') as stream:
            response = app.app.test_client().post('/api/import-excel', data={'file': (stream, path.name)})
        if response.status_code != 200:
            raise RuntimeError(response.json.get('error', 'Workbook import failed'))
        snapshot = {'filename': path.name, 'workbook': {'sheets': [{'name': name, 'rows': rows} for name, rows in response.json['sheets'].items()], 'sheet_previews': response.json['sheet_previews']}}
    elif saved.exists():
        snapshot = json.loads(saved.read_text(encoding='utf-8'))
    else:
        raise RuntimeError('Set HOSPKART_TEST_WORKBOOK to the supplied invoice Excel path, or prepare a local workbook first. Tests do not change live dashboard data.')
    app.DATA_DIR = Path(directory)
    app.DB_PATH = app.DATA_DIR / 'test.db'
    app.ADMIN_PASSWORD_PATH = app.DATA_DIR / 'admin.hash'
    app.DATA_DIR.joinpath('imported_invoice_workbook.json').write_text(json.dumps(snapshot, ensure_ascii=False), encoding='utf-8')
    app.init_db()
    if app.scheduler.running:
        app.scheduler.pause()
    return snapshot
