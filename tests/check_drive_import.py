"""Real shared Drive link and Excel import flow using synthetic workbooks only."""
import json
import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from threading import Thread
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from crm_test_environment import app, login_browser_admin
from openpyxl import Workbook
from playwright.sync_api import sync_playwright
from waitress import create_server
from spreadsheet_sync import SheetError


def fixture(*_):
    book=Workbook();sheet=book.active;sheet.title='Hospitals'
    sheet.append(['Name','City','Phone','Status']);sheet.append(['Shared Drive Hospital','Jaipur','0012345678','New Lead'])
    content=BytesIO();book.save(content);content.seek(0)
    return content,'Hospitals.xlsx','.xlsx'


def check():
    reports=[]
    with tempfile.TemporaryDirectory() as temp,patch.object(app,'DB_PATH',Path(temp)/'crm.db'):
        app.init_db()
        if app.scheduler.running:app.scheduler.pause()
        server=create_server(app.app,host='127.0.0.1',port=0);Thread(target=server.run,daemon=True).start()
        try:
            with sync_playwright() as p:
                for channel in os.getenv('BROWSER_CHANNELS','chrome,msedge').split(','):
                    with app.db_conn() as conn:
                        conn.execute('DELETE FROM shared_drive_links');conn.execute('DELETE FROM crm_workspace')
                    app.init_db()
                    browser=p.chromium.launch(**({} if channel=='chromium' else {'channel':channel}),headless=True)
                    a=browser.new_page();b=browser.new_page();errors=[]
                    for page in (a,b):
                        page.on('pageerror',lambda error:errors.append(str(error)))
                        login_browser_admin(page.context, f'http://127.0.0.1:{server.effective_port}/')
                        page.goto(f'http://127.0.0.1:{server.effective_port}/');page.wait_for_function('dashboardReady&&!document.body.inert');page.evaluate('openDriveImport()')
                        page.evaluate('document.activeElement.blur()')
                    a.locator('#driveImportLabel').fill('Team workbook <script>')
                    a.locator('#driveImportLink').fill('https://drive.google.com/file/d/test_private_workbook_123456/view')
                    assert a.locator('#driveLinkSaveButton').evaluate('button=>button.form.id')=='driveLinkForm'
                    a.locator('#driveLinkSaveButton').click()
                    try:a.wait_for_function('!driveImportBusy&&sharedDriveLinks.length===1',timeout=5000)
                    except Exception:
                        print('Save diagnostic:',a.locator('#driveImportMessage').inner_text(),errors,flush=True)
                        raise
                    b.wait_for_function('sharedDriveLinks.length===1',timeout=15000)
                    assert b.locator('#driveImportRows').get_by_role('link',name='Open Drive file').get_attribute('href').startswith('https://drive.google.com/')
                    assert b.locator('#driveImportRows script').count()==0
                    assert b.evaluate('clients.length')==0
                    with patch.object(app.drive_import_provider,'download',side_effect=fixture):
                        a.locator('#driveImportRows').get_by_role('button',name='Preview / import',exact=True).click()
                        a.locator('#importConfirm:not(.hidden)').wait_for()
                        assert a.evaluate('clients.length')==0
                        a.locator('#importConfirmAccept').click()
                        a.wait_for_function('!driveImportBusy&&clients.length===1')
                    b.wait_for_function('clients.length===1',timeout=15000)
                    assert b.evaluate('clients[0].name')=='Shared Drive Hospital'
                    assert b.evaluate('clients[0].mobile')=='0012345678'
                    with patch.object(app.drive_import_provider,'download',side_effect=SheetError('Missing Viewer permission.',403)):
                        a.locator('#driveImportRows').get_by_role('button',name='Preview / import',exact=True).click()
                        a.wait_for_function('!driveImportBusy')
                        assert 'Missing Viewer' in a.locator('#driveImportMessage').inner_text()
                        assert a.evaluate('clients.length')==1
                    a.reload();a.wait_for_function('dashboardReady&&!document.body.inert');a.evaluate('openDriveImport()')
                    assert a.evaluate('sharedDriveLinks.length')==1
                    a.get_by_role('button',name='Copy this CRM link',exact=True).click()
                    assert 'localhost address works only' in a.locator('#driveImportMessage').inner_text()
                    a.locator('#driveImportTarget').select_option('leads');a.locator('#driveImportLabel').fill('Lead response sheet')
                    a.locator('#driveImportLink').fill('https://docs.google.com/spreadsheets/d/test_private_workbook_987654/edit')
                    a.locator('#driveLinkSaveButton').click();a.wait_for_function('!driveImportBusy&&sharedDriveLinks.length===2')
                    a.locator('#driveImportRows').get_by_role('button',name='Connect for sync',exact=True).click()
                    assert a.locator('#sheetLinkInput').input_value().endswith('/test_private_workbook_987654/edit')
                    assert a.locator('#sheetConnectPanel').get_attribute('open') is not None
                    a.set_viewport_size({'width':390,'height':844});a.evaluate('openDriveImport()')
                    assert a.locator('#driveImportLink').is_visible()
                    assert not errors,errors
                    reports.append({'browser':channel,'shared_links':True,'preview_before_import':True,'shared_import':True,
                                    'permission_failure_retains_data':True,'reload':True,'lead_sync_handoff':True,'mobile':True,'javascript_errors':errors})
                    browser.close()
        finally:server.close()
    print(json.dumps(reports,indent=2))


if __name__=='__main__':check()
