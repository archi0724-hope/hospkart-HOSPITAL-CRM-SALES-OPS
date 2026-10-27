"""Verify upload/edit/sync/removal and activity history with no sign-in."""
import json
import os
import sys
import tempfile
from pathlib import Path
from threading import Thread
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from crm_test_environment import app
from playwright.sync_api import sync_playwright
from waitress import create_server
from check_production_browsers import make_workbook
from test_spreadsheet_sync import FakeSheets,connection_payload


def check():
    reports=[]
    with sync_playwright() as playwright:
        for channel in os.getenv('BROWSER_CHANNELS','chrome,msedge').split(','):
            with tempfile.TemporaryDirectory() as temp,patch.object(app,'DB_PATH',Path(temp)/'crm.db'),patch.object(app,'DATA_DIR',Path(temp)),patch.dict(app.app.config,{'ADMIN_ACCESS_REQUIRED':False}):
                app.init_db();provider=FakeSheets()
                with patch.object(app.sheet_sync,'provider',provider):
                    server=create_server(app.app,host='127.0.0.1',port=0);Thread(target=server.run,daemon=True).start()
                    address=f'http://127.0.0.1:{server.effective_port}/'
                    browser=playwright.chromium.launch(**({} if channel=='chromium' else {'channel':channel}),headless=True)
                    context=browser.new_context();page=context.new_page();errors=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    try:
                        page.goto(address);page.wait_for_function('dashboardReady&&!document.body.inert&&sheetState!==null')
                        assert page.evaluate('crmAdminSession.can_edit && !crmAdminSession.login_required && !crmAdminSession.admin')
                        assert page.locator('input[type=password]').count()==0
                        assert not context.cookies()
                        page.evaluate("navigate('clients')")
                        page.get_by_role('button',name='+ Add Client',exact=True).click()
                        page.locator('#newName').fill('No-login Hospital');page.locator('#newCity').fill('Jaipur');page.locator('#newRequirement').fill('Medical supplies')
                        page.locator('#clientSaveButton').click();page.wait_for_function("clients.some(row=>row.name==='No-login Hospital')&&!sharedWorkspaceSaving")
                        # Preview/import and sync through real APIs with no auth cookie.
                        headers={'X-CRM-Request':'1'}
                        preview=context.request.post(address+'api/spreadsheet/preview',data=connection_payload(),headers=headers)
                        assert preview.ok,preview.text()
                        imported=context.request.post(address+'api/spreadsheet/import',data={'token':preview.json()['token']},headers=headers)
                        assert imported.ok,imported.text()
                        page.evaluate('async()=>await applySheetState(await sheetRequest("status"))')
                        page.evaluate("navigate('leads')")
                        assert page.locator('#sheetSyncButton').is_enabled()
                        provider.rows[0].append(['0002','Second Hospital','00009','New Lead','2026-10-02',''])
                        page.locator('#sheetSyncButton').click();page.wait_for_function("!sheetBusy&&sectionRecords.leads.some(row=>row.id==='0002')")
                        workbook=Path(temp)/'invoices.xlsx';make_workbook(workbook)
                        page.set_input_files('#excelImportFile',str(workbook));page.wait_for_function('invoiceWorkbook?.sheets.length===6&&!sharedWorkspaceSaving')
                        page.evaluate("navigate('data')")
                        page.locator('#importRemovalRows tr').filter(has_text='Categorized Items').get_by_role('button',name='Remove',exact=True).click()
                        assert page.locator('#importRemovalPassword').count()==0
                        page.locator('#importRemovalConfirmation').fill('REMOVE Categorized Items')
                        page.locator('#importRemovalSubmit').click();page.wait_for_function('!importRemovalSubmitting&&invoiceWorkbook.sheets.length===5')
                        page.get_by_role('link',name='Activity log',exact=True).click()
                        page.wait_for_function("document.getElementById('adminActivityRows').textContent.includes('Dashboard user')")
                        assert page.locator('input[type=password]').count()==0
                        assert 'data change' in page.locator('#adminActivityRows').inner_text()
                        assert not errors,errors
                        assert not context.cookies()
                        page.goto(address+'admin');page.wait_for_url(address)
                        reports.append({'browser':channel,'no_login':True,'record_save':True,'spreadsheet_import_sync':True,
                                        'workbook_upload':True,'confirmed_removal':True,'activity_history':True,'javascript_errors':errors})
                    finally:
                        context.close();browser.close();server.close()
    print(json.dumps(reports,indent=2))


if __name__=='__main__':check()
