"""End-to-end regression checks for stored invoice workbooks and the Dashboard."""
import json
import os
import sys
import tempfile
from pathlib import Path
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server


def check():
    with tempfile.TemporaryDirectory() as temp:
        app.DB_PATH = Path(temp) / 'test.db'
        app.init_db()
        server = make_server('127.0.0.1', 5011, app.app)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel=os.getenv('BROWSER_CHANNEL', 'chrome'))
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto('http://127.0.0.1:5011')
                page.wait_for_function("invoiceWorkbook?.sheets.length === 6")
                assert page.locator('#page-dashboard').is_visible()
                assert page.locator('#clientRows').is_visible()
                assert page.locator('#invoiceMetrics, #invoiceDetailRows, #invoiceDashboard').count() == 0
                assert page.locator('#servedTotal').inner_text() == '38'
                actual = page.evaluate("invoiceSheet('Client Summary').reduce((sum,row)=>sum+row['Invoice Total (₹)'],0)")
                assert round(actual, 2) == 3135013.91, actual
                stored = page.evaluate("JSON.parse(dashboardStorage.get('hk_v2_invoice_workbook'))")
                assert stored['sheets'] == page.evaluate('invoiceWorkbook.sheets')
                assert len(stored['sheets']) == 6
                page.reload()
                page.wait_for_function("invoiceWorkbook?.sheets.length === 6")
                assert page.locator('#invoiceMetrics, #invoiceDetailRows, #invoiceDashboard').count() == 0
                assert page.locator('#clientRows').is_visible()
                assert page.evaluate("JSON.parse(dashboardStorage.get('hk_v2_invoice_workbook')).sheets.length") == 6
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile page overflows'
                # Re-import must retain all sheets without duplicating client records.
                before = page.evaluate('clients.length')
                from openpyxl import Workbook
                imported = Workbook()
                imported.remove(imported.active)
                snapshot = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'imported_invoice_workbook.json').read_text(encoding='utf-8'))
                for sheet in snapshot['workbook']['sheets']:
                    worksheet = imported.create_sheet(sheet['name'])
                    columns = list(sheet['rows'][0])
                    worksheet.append(columns)
                    for row in sheet['rows']:
                        worksheet.append([row.get(column) for column in columns])
                file = Path(temp) / 'invoice-reimport.xlsx'
                imported.save(file)
                imported.close()
                page.set_input_files('#servedImportFile', str(file))
                page.wait_for_function("invoiceWorkbook.filename === 'invoice-reimport.xlsx'")
                assert page.evaluate('clients.length') == before
                assert page.locator('#servedTotal').inner_text() == '38'
                assert page.locator('#invoiceMetrics, #invoiceDetailRows, #invoiceDashboard').count() == 0
                # Reset suppression clears the browser copy without displaying analytics.
                page.evaluate("writeDashboardValues({hk_v2_invoice_workbook:null,hk_v2_reset_revision:'test'})")
                page.reload()
                page.wait_for_timeout(500)
                assert page.locator('#invoiceMetrics, #invoiceDetailRows, #invoiceDashboard').count() == 0
                assert not errors, errors
                browser.close()
                print(json.dumps({'passed': True, 'clients': 38, 'workbook_sheets': 6, 'invoice_value': actual, 'browser_errors': errors}))
        finally:
            server.shutdown()
            app.scheduler.shutdown(wait=False)


if __name__ == '__main__':
    check()
