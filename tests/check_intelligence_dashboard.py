"""Synthetic browser checks for the intelligence overview and existing workflows."""
import json
import os
import sys
from pathlib import Path
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crm_test_environment import app
from test_crm_knowledge import CRMKnowledgeTests
from playwright.sync_api import sync_playwright
from waitress import create_server


def check():
    fixture = CRMKnowledgeTests('test_counts_match_saved_records_and_new_edits_are_immediate')
    fixture.setUp()
    server = create_server(app.app, host='127.0.0.1', port=0)
    Thread(target=server.run, daemon=True).start()
    address = f'http://127.0.0.1:{server.effective_port}/'
    reports = []
    try:
        with sync_playwright() as playwright:
            for channel in os.getenv('BROWSER_CHANNELS', 'chrome,msedge').split(','):
                browser = playwright.chromium.launch(**({} if channel == 'chromium' else {'channel': channel}), headless=True)
                context = browser.new_context(viewport={'width':1440, 'height':1080})
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(address)
                page.wait_for_function('dashboardReady && !document.body.inert && sheetState !== null && intelligenceSnapshot !== null')
                status = context.request.get(address+'api/quotesaarthi/knowledge').json()
                assert page.locator('#intelligenceOverdue').inner_text() == str(status['followup_counts']['overdue'])
                assert page.locator('#intelligenceToday').inner_text() == str(status['followup_counts']['due_today'])
                assert page.locator('#intelligenceComplaints').inner_text() == '0'
                before = fixture.client.get('/api/workspace').json['workspace']
                assert int(page.locator('#kpiClients').inner_text()) == status['workspace_records']
                page.locator('#search').fill('Beta Clinic')
                assert page.locator('#intelligenceOverdue').inner_text() == str(status['followup_counts']['overdue'])
                assert fixture.client.get('/api/workspace').json['workspace']['revision'] == before['revision']
                page.keyboard.press('Control+k')
                assert page.locator('#workspaceCommandDialog').is_visible()
                page.locator('#workspaceCommandInput').fill('Reports')
                page.locator('#workspaceCommandInput').press('Enter')
                page.wait_for_function("currentView === 'reports'")
                page.get_by_role('button', name='Search workspace commands',exact=True).click()
                page.locator('#workspaceCommandInput').fill('<img src=x onerror=alert(1)>')
                assert page.locator('#workspaceCommandResults img').count() == 0
                page.keyboard.press('Escape')
                page.locator('#workspaceCommandDialog').wait_for(state='hidden')
                assert not page.locator('#workspaceCommandDialog').is_visible()
                page.evaluate("navigate('dashboard');clearFilters()")
                page.get_by_role('button',name='Ask for my CRM brief',exact=False).click()
                page.wait_for_function("!quoteSaarthiSubmitting && document.querySelectorAll('#chatBody .bot').length > 1")
                assert 'CRM summary:' in page.locator('#chatBody .bot').last.inner_text()
                page.get_by_role('button',name='Close QuoteSaarthi',exact=True).click()
                # A saved revision must update the overview without a page reload.
                fixture.save({'hk_v2_leads':[{'id':'L001','name':'Future lead','status':'New Lead','next':'2099-01-01'}]})
                page.evaluate('refreshSharedWorkspace(true)')
                page.wait_for_function('intelligenceSnapshot.revision === sharedWorkspaceRevision && intelligenceSnapshot.workspace_records === 3')
                assert page.locator('#intelligenceOverdue').inner_text() == '2'
                # Failed server reads use an explicitly labeled browser copy.
                page.route('**/api/quotesaarthi/knowledge', lambda route:route.fulfill(status=503,content_type='application/json',body='{"ok":false,"error":"Unavailable"}'))
                page.locator('#intelligenceRefresh').click()
                page.wait_for_function("intelligenceSnapshot?.offline_copy === true")
                assert page.locator('#intelligenceOverdue').inner_text() == '2'
                assert 'browser copy' in page.locator('#intelligenceSource').inner_text()
                assert 'not verified with server' in page.locator('#intelligenceScope').inner_text()
                page.unroute('**/api/quotesaarthi/knowledge')
                page.locator('#intelligenceRefresh').click()
                page.wait_for_function("document.getElementById('intelligenceOverdue').textContent === '2' && !intelligenceSnapshot.offline_copy")
                if channel == os.getenv('BROWSER_CHANNELS','chrome,msedge').split(',')[0]:
                    page.screenshot(path=str(Path(__file__).resolve().parents[1]/'data'/'quotesaarthi-intelligence-desktop.png'))
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                assert page.locator('#adminAccessButton').count() == 0
                page.get_by_role('button',name='Search workspace commands',exact=True).click()
                assert page.locator('#workspaceCommandDialog').is_visible()
                page.keyboard.press('Escape')
                page.locator('#workspaceCommandDialog').wait_for(state='hidden')
                page.get_by_role('button',name='Open QuoteSaarthi',exact=True).click()
                box = page.locator('#chatWidget').bounding_box()
                assert box and box['x'] >= 0 and box['x']+box['width'] <= 390
                page.get_by_role('button',name='Close QuoteSaarthi',exact=True).click()
                if channel == os.getenv('BROWSER_CHANNELS','chrome,msedge').split(',')[0]:
                    page.screenshot(path=str(Path(__file__).resolve().parents[1]/'data'/'quotesaarthi-intelligence-mobile.png'))
                assert not errors, errors
                reports.append({'browser':channel,'saved_insights':True,'unfiltered_counts':True,
                    'keyboard_navigation':True,'safe_search':True,'assistant_brief':True,'revision_refresh':True,
                    'unavailable_state':True,'mobile_layout':True,'javascript_errors':errors})
                context.close();browser.close()
                fixture.save({'hk_v2_leads':[{'id':'L001','name':'Alpha Hospital','city':'Jaipur','status':'Query Received','next':'2026-10-23','product':'Pump'},
                                           {'id':'L002','name':'Gamma Hospital','status':'New Lead','next':'2026-10-25'}]})
    finally:
        server.close();fixture.doCleanups()
    print(json.dumps(reports,indent=2))


if __name__ == '__main__':
    check()
