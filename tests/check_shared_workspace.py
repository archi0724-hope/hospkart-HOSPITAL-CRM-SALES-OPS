"""Real shared-CRM browser flow using isolated SQLite and fresh user profiles."""
import json
import os
import sys
import tempfile
from pathlib import Path
from threading import Thread
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crm_test_environment import app, login_browser_admin
from openpyxl import Workbook
from playwright.sync_api import sync_playwright
from waitress import create_server
from check_production_browsers import make_workbook


def ready(page):
    page.wait_for_function('dashboardReady && !document.body.inert && sheetState !== null')


def check():
    reports = []
    with tempfile.TemporaryDirectory() as temp, patch.object(app, 'DB_PATH', Path(temp) / 'shared.db'), patch.object(app, 'DATA_DIR', Path(temp)):
        if app.scheduler.running: app.scheduler.pause()
        with sync_playwright() as playwright:
            for channel in os.getenv('BROWSER_CHANNELS', 'chrome,msedge').split(','):
                app.init_db()
                with app.db_conn() as conn:
                    conn.execute('DELETE FROM crm_workspace')
                app.init_db()
                server = create_server(app.app, host='127.0.0.1', port=0)
                Thread(target=server.run, daemon=True).start()
                address = f'http://127.0.0.1:{server.effective_port}/'
                browser = playwright.chromium.launch(channel=None if channel == 'chromium' else channel, headless=True)
                try:
                    owner = browser.new_context(accept_downloads=True)
                    # A real older browser has one locally saved hospital before migration.
                    legacy = {'id': 'LEGACY-001', 'name': 'Preserved Local Hospital', 'city': 'Jaipur', 'status': 'New Lead', 'quote': 0, 'order': 0, 'next': '', 'remark': ''}
                    owner.add_init_script('if(!sessionStorage.getItem("seeded")){localStorage.setItem("hk_v2_clients",'+json.dumps(json.dumps([legacy]))+');sessionStorage.setItem("seeded","1");}')
                    a = owner.new_page(); errors = []
                    a.on('pageerror', lambda error: errors.append(str(error)))
                    login_browser_admin(owner, address)
                    a.goto(address); ready(a)
                    assert a.evaluate('clients[0].id') == 'LEGACY-001'
                    assert a.evaluate('sharedWorkspaceInitialized')
                    other = browser.new_context(accept_downloads=True); b = other.new_page()
                    b.on('pageerror', lambda error: errors.append(str(error)))
                    login_browser_admin(other, address)
                    b.goto(address); ready(b)
                    assert b.evaluate('clients[0].id') == 'LEGACY-001'

                    fixture = Path(temp) / 'clients.xlsx'
                    book = Workbook(); sheet = book.active; sheet.title = 'Clients'
                    sheet.append(['Client ID', 'Hospital Name', 'City', 'Mobile Number'])
                    sheet.append(['UPLOAD-001', 'Shared Uploaded Hospital', 'Delhi', '0012345678'])
                    sheet.append(['UPLOAD-002', 'Shared Uploaded Clinic', 'Kota', '0098765432'])
                    book.save(fixture)
                    a.set_input_files('#excelImportFile', str(fixture))
                    a.locator('#importConfirmAccept').click()
                    a.wait_for_function("clients.some(row=>row.id==='UPLOAD-001') && sharedWorkspaceSaving===0")
                    # No reload or API mock: the second user's 5-second refresh must see it.
                    b.wait_for_function("clients.some(row=>row.id==='UPLOAD-001')", timeout=15000)
                    assert b.evaluate("clients.find(row=>row.id==='UPLOAD-001').mobile") == '0012345678'
                    assert a.locator('#kpiClients').inner_text() == b.locator('#kpiClients').inner_text()

                    # Warm startup checks the server version without redownloading
                    # the workspace or its saved checkpoint archive.
                    with b.expect_response(lambda response: '/api/workspace?' in response.url and 'updated_at=' in response.url) as cached:
                        b.reload(); ready(b)
                    assert cached.value.json()['unchanged'] is True
                    assert b.evaluate("clients.some(row=>row.id==='UPLOAD-001')")

                    # Independent imported sections also travel through the real upload route.
                    for scope, control in [('rghs', 'rghsImportFile'), ('doctors', 'doctorImportFile'), ('potential', 'potentialImportFile')]:
                        a.set_input_files('#' + control, str(fixture))
                        a.locator('#importConfirmAccept').click()
                        a.wait_for_function(f'sectionRecords.{scope}.length===2 && sharedWorkspaceSaving===0')
                        b.wait_for_function(f'sectionRecords.{scope}.length===2', timeout=15000)

                    invoices = Path(temp) / 'invoices.xlsx'; make_workbook(invoices)
                    a.set_input_files('#excelImportFile', str(invoices))
                    a.wait_for_function('invoiceWorkbook?.sheets.length===6 && sectionRecords.served.length===4 && sharedWorkspaceSaving===0')
                    b.wait_for_function('invoiceWorkbook?.sheets.length===6 && sectionRecords.served.length===4', timeout=15000)
                    assert b.evaluate('backups.length') > 0

                    # An editor opened before another user's save cannot overwrite that save.
                    b.evaluate("openClientForm(false,'UPLOAD-001','clients')")
                    a.evaluate("async()=>{clients.find(row=>row.id==='UPLOAD-001').name='Newer Shared Name';await persist();renderAll();}")
                    b.locator('#newName').fill('Stale Editor Name')
                    b.locator('#newRequirement').fill('Clinical supplies')
                    b.locator('#clientSaveButton').click()
                    b.wait_for_function("sharedWorkspaceSaving===0 && browserWorkspaceRecovery?.reason.includes('not saved') && clients.find(row=>row.id==='UPLOAD-001').name==='Newer Shared Name'")
                    assert 'not saved' in b.locator('#sharedRecoveryReason').inner_text().lower()
                    assert b.locator('#sharedRecoveryNotice').is_visible()
                    b.evaluate("closeDrawer('clientDrawer')")
                    assert app.app.test_client().get('/api/workspace').json['workspace']['values']['hk_v2_clients'][1]['name'] == 'Newer Shared Name'

                    # Network failures cannot turn an unsaved browser edit into a successful save.
                    a.route('**/api/workspace', lambda route: route.abort() if route.request.method == 'POST' else route.continue_())
                    a.evaluate("openClientForm(false,'UPLOAD-001','clients')")
                    a.locator('#newName').fill('Unsaved Network Change'); a.locator('#newRequirement').fill('Clinical supplies'); a.locator('#clientSaveButton').click()
                    a.wait_for_function('sharedWorkspaceSaving===0')
                    assert a.evaluate("clients.find(row=>row.id==='UPLOAD-001').name") == 'Newer Shared Name'
                    assert a.locator('#sharedRecoveryNotice').is_visible()
                    a.unroute('**/api/workspace'); a.evaluate("closeDrawer('clientDrawer')")

                    # Browser storage restrictions no longer prevent access to the shared database.
                    blocked = browser.new_context(); blocked.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new DOMException('blocked','SecurityError')}});Object.defineProperty(window,'indexedDB',{get(){throw new DOMException('blocked','SecurityError')}})")
                    c = blocked.new_page(); c.goto(address); ready(c)
                    assert c.evaluate("clients.some(row=>row.name==='Newer Shared Name')")
                    blocked.close()

                    corrupt = browser.new_context(accept_downloads=True)
                    corrupt.add_init_script("localStorage.setItem('hk_v2_clients','[null]')")
                    c = corrupt.new_page(); c.goto(address); ready(c)
                    assert c.evaluate("clients.some(row=>row.name==='Newer Shared Name')")
                    with c.expect_download() as download:
                        c.get_by_role('button', name='Download preserved browser data', exact=True).click()
                    recovered = Path(temp) / 'raw-recovery.json'; download.value.save_as(recovered)
                    assert '[null]' in recovered.read_text()
                    corrupt.close()

                    # Checkpoint downloads still contain every imported worksheet.
                    a.evaluate("navigate('data')")
                    with a.expect_download() as download:
                        a.get_by_role('button', name='Prepare full data backup', exact=True).click()
                    backup = Path(temp) / 'shared-backup.json'; download.value.save_as(backup)
                    snapshot = json.loads(backup.read_text()); assert len(snapshot['invoiceWorkbook']['sheets']) == 6
                    assert len(snapshot['sections']['served']) == 4
                    before = app.app.test_client().get('/api/workspace').json['workspace']['values']
                    owner.close(); other.close(); server.close()

                    # Start a new server on a new address: a new user gets the same DB records.
                    app.init_db(); server = create_server(app.app, host='127.0.0.1', port=0)
                    Thread(target=server.run, daemon=True).start()
                    fresh = browser.new_context(); c = fresh.new_page()
                    login_browser_admin(fresh, f'http://127.0.0.1:{server.effective_port}/')
                    c.goto(f'http://127.0.0.1:{server.effective_port}/'); ready(c)
                    assert c.evaluate('clients.length') == len(before['hk_v2_clients'])
                    assert c.evaluate('invoiceWorkbook.sheets.length') == 6
                    assert c.evaluate('sectionRecords.served.length') == 4
                    observer = browser.new_context(); d = observer.new_page()
                    d.goto(c.url); ready(d)
                    c.evaluate("navigate('data')")
                    c.locator('#resetAcknowledge').check(); c.locator('#resetPhrase').fill('RESET DASHBOARD')
                    c.locator('#resetConfirmButton').click()
                    c.wait_for_function('!dashboardResetting && clients.length===0 && invoiceWorkbook===null')
                    d.wait_for_function('clients.length===0 && invoiceWorkbook===null && Object.values(sectionRecords).every(rows=>rows.length===0)', timeout=15000)
                    observer.close()
                    fresh.close()
                    assert not errors, errors
                    reports.append({'browser': channel, 'legacy_migration': True, 'shared_excel_uploads': True,
                                    'automatic_cross_profile_refresh': True, 'shared_sections_workbook_backups': True,
                                    'stale_edit_rejected': True, 'network_failure_retains_data': True,
                                    'blocked_and_corrupt_browser_storage': True, 'server_restart_persistence': True, 'shared_reset': True,
                                    'javascript_errors': errors})
                except Exception:
                    try:
                        print(json.dumps(b.evaluate("({revision:sharedWorkspaceRevision,saving:sharedWorkspaceSaving,reason:document.getElementById('sharedRecoveryReason').textContent,toast:document.getElementById('toast').textContent,drawer:document.getElementById('clientDrawer').className,formValid:document.getElementById('clientForm').checkValidity(),name:clients.find(row=>row.id==='UPLOAD-001')?.name,editName:document.getElementById('newName').value})")), flush=True)
                    except Exception:
                        pass
                    raise
                finally:
                    browser.close(); server.close()
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    check()
