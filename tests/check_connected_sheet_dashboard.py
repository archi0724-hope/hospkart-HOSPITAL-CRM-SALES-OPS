"""Connected sheets show records/counts; setup stays in the admin dialog."""
import json
import os
import sys
from pathlib import Path
from threading import Thread

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from crm_test_environment import app, login_browser_admin
import test_form_responses as form_tests
from playwright.sync_api import sync_playwright
from waitress import create_server


def check():
    reports=[]
    with sync_playwright() as playwright:
        for channel in os.getenv('BROWSER_CHANNELS','chrome,msedge').split(','):
            fixture=form_tests.FormResponseTests('test_response_create_edit_reorder_and_repeat');fixture.setUp()
            fixture.connect(fixture.payload)
            current=fixture.client.get('/api/workspace').json['workspace']
            leads=current['values']['hk_v2_leads']
            for row in leads:row['status']='Contacted'
            saved=fixture.client.post('/api/workspace',json={'revision':current['revision'],'values':{
                'hk_v2_leads':leads,'hk_v2_clients':[{'id':'MASTER-1','name':'Existing hospital','status':'New Lead'}]}},headers=form_tests.HEADERS)
            assert saved.status_code==200,saved.json
            server=create_server(app.app,host='127.0.0.1',port=0);Thread(target=server.run,daemon=True).start()
            address=f'http://127.0.0.1:{server.effective_port}/'
            browser=playwright.chromium.launch(**({} if channel=='chromium' else {'channel':channel}),headless=True)
            context=browser.new_context(viewport={'width':1440,'height':1000});page=context.new_page();errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            try:
                page.goto(address);page.wait_for_function('dashboardReady&&!document.body.inert&&sheetState?.connection')
                page.evaluate("navigate('leads')")
                assert page.locator('#page-leads #sheetConnectPanel').count()==0
                assert not page.locator('#spreadsheetConnectionDialog').is_visible()
                assert not page.locator('#sheetManageButton').is_visible()
                assert page.locator('#sheetStatusText').inner_text().startswith('Connected:')
                assert page.locator('#leadTotal').inner_text()=='2'
                assert page.locator('#navLeads').inner_text()=='2'
                assert page.locator('#leadQueryCount').inner_text()=='1'
                assert page.locator('#sheetQueryTotal').inner_text()=='1'
                assert page.locator('#kpiClients').inner_text()=='3'
                assert page.locator('#sheetLeadRows tr').count()==2
                assert page.locator('#sheetQueryRows tr').count()==1
                # A new query response creates one lead and a linked query, adding
                # exactly one to workspace headcount, including on repeat sync.
                fixture.provider.rows[0].append(['10/27/2026 16:00:00','Sales Team','10/27/2026','Customer C','0012345680','',
                    'Customer Query','Hospital C','Service','Need assistance','High'])
                app.sheet_sync.sync()
                page.evaluate('async()=>{document.activeElement.blur();await applySheetState(await sheetRequest("status"));}')
                page.wait_for_function("document.getElementById('leadTotal').textContent==='3'&&document.getElementById('kpiClients').textContent==='4'")
                assert page.locator('#leadQueryCount').inner_text()=='2'
                assert page.locator('#navLeads').inner_text()=='3'
                assert page.locator('#sheetQueryTotal').inner_text()=='2'
                app.sheet_sync.sync()
                page.evaluate('async()=>await applySheetState(await sheetRequest("status"))')
                assert page.locator('#kpiClients').inner_text()=='4'
                assert not page.locator('#spreadsheetConnectionDialog').is_visible()
                login_browser_admin(context,address);page.evaluate('refreshAdminAccess()')
                page.wait_for_function('crmAdminSession.admin')
                page.locator('#sheetManageButton').click()
                assert page.locator('#spreadsheetConnectionDialog').is_visible()
                assert page.locator('#sheetLinkInput').is_visible()
                page.get_by_role('button',name='Close spreadsheet setup',exact=True).click()
                page.set_viewport_size({'width':390,'height':844})
                assert page.locator('#leadTotal').inner_text()=='3'
                assert not page.locator('#spreadsheetConnectionDialog').is_visible()
                assert not errors,errors
                reports.append({'browser':channel,'main_setup_removed':True,'admin_management':True,
                    'saved_queries_counted':True,'headcount_includes_synced_responses':True,
                    'repeat_sync_no_double_count':True,'javascript_errors':errors})
            finally:
                context.close();browser.close();server.close();fixture.doCleanups()
    print(json.dumps(reports,indent=2))


if __name__=='__main__':check()
