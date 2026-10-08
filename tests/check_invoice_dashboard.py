"""End-to-end regression checks against the supplied workbook and local Flask app."""
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
                browser = playwright.chromium.launch(channel=os.getenv('BROWSER_CHANNEL','chrome'))
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto('http://127.0.0.1:5011')
                page.locator('#invoiceMetrics').get_by_text('38', exact=True).wait_for()
                metrics = page.locator('#invoiceMetrics').inner_text()
                assert '61' in metrics and '202' in metrics and '6' in metrics, metrics
                assert page.locator('#invoiceDetailRows tr').count() == 61
                assert page.locator('#servedTotal').inner_text() == '38'
                actual = page.evaluate("invoiceSheet('Client Summary').reduce((sum,row)=>sum+row['Invoice Total (₹)'],0)")
                assert round(actual, 2) == 3135013.91, actual
                page.select_option('#invoiceDetailSheet', 'Client Call List')
                assert page.locator('#invoiceDetailRows tr').count() == 202
                assert page.locator('#invoiceDetailHead th').count() == 31
                page.select_option('#invoiceDetailSheet', 'Cancelled Invoices')
                assert page.locator('#invoiceDetailRows tr').count() == 152
                page.select_option('#invoiceStatus', 'Paid')
                assert page.evaluate("uniqueInvoices(invoiceSheet('Client Summary')).filter(row=>row['Invoice Status']==='Paid').length") == 22
                assert '22' in page.locator('#invoiceMetrics').inner_text()
                page.click('button[onclick="clearInvoiceFilters()"]')
                page.select_option('#invoiceDetailSheet', 'Client Summary')
                with page.expect_download() as download:
                    page.click('button[onclick="exportInvoiceDetails()"]')
                assert download.value.suggested_filename.endswith('.xls')
                page.fill('#invoiceSearch', 'nothing-matches-this-query')
                assert 'No matching records.' in page.locator('#invoiceDetailRows').inner_text()
                assert '₹0' not in page.locator('#invoiceMetrics').inner_text()
                page.click('button[onclick="clearInvoiceFilters()"]')
                page.reload()
                page.locator('#invoiceMetrics').get_by_text('38', exact=True).wait_for()
                output = Path(__file__).resolve().parents[1] / 'data' / 'invoice-dashboard-desktop.png'
                page.screenshot(path=str(output), full_page=True)
                page.set_viewport_size({'width': 390, 'height': 844})
                page.screenshot(path=str(output.with_name('invoice-dashboard-mobile.png')), full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile page overflows'
                # Re-import must retain all rows and not duplicate client master records.
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
                # Reset suppression must persist across reloads.
                page.evaluate("localStorage.setItem('hk_v2_invoice_workbook','null');localStorage.setItem('hk_v2_reset_revision','test');")
                page.reload()
                page.wait_for_timeout(500)
                assert page.locator('#invoiceDashboard').is_hidden()
                assert not errors, errors
                browser.close()
                print(json.dumps({'passed': True, 'clients': 38, 'invoices': 61, 'item_rows': 202, 'cancelled_item_rows': 152, 'invoice_value': actual, 'browser_errors': errors}))
        finally:
            server.shutdown()
            app.scheduler.shutdown(wait=False)


if __name__ == '__main__':
    check()
