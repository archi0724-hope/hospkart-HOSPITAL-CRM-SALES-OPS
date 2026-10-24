"""Real widget checks against temporary saved CRM records, without AI requests."""
import json
import os
import sys
from pathlib import Path
from threading import Thread
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crm_test_environment import app
from playwright.sync_api import sync_playwright
from waitress import create_server
from test_crm_knowledge import CRMKnowledgeTests


def check():
    reports=[]
    fixture=CRMKnowledgeTests('test_counts_match_saved_records_and_new_edits_are_immediate');fixture.setUp()
    server=create_server(app.app,host='127.0.0.1',port=0);Thread(target=server.run,daemon=True).start()
    if app.scheduler.running: app.scheduler.pause()
    try:
        with sync_playwright() as p, patch('app.requests.post',side_effect=AssertionError('CRM chat must stay local')):
            for channel in os.getenv('BROWSER_CHANNELS','chrome,msedge').split(','):
                browser=p.chromium.launch(**({} if channel=='chromium' else {'channel':channel}),headless=True)
                page=browser.new_page(viewport={'width':1280,'height':960});errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.effective_port}/')
                page.wait_for_function('dashboardReady&&!document.body.inert')
                before=page.evaluate('JSON.stringify({clients,sectionRecords,complaints})')
                expected_records=page.evaluate('workspaceRecords().length')
                page.get_by_role('button',name='Open QuoteSaarthi',exact=True).click()
                page.wait_for_function("document.getElementById('quoteKnowledgeStatus').textContent.includes('Live CRM')")

                def ask(message):
                    page.locator('#chatInput').fill(message);page.locator('.chat-send').click()
                    page.wait_for_function('!quoteSaarthiSubmitting')
                    return page.locator('#chatBody .bot').last.inner_text()

                summary=ask('Summarize CRM dashboard')
                assert f'{expected_records} workspace records' in summary,summary
                assert 'Leads & Queries: 2' in ask('Show leads')
                assert 'CRM-Q:L001' in ask('Show queries')
                assert '0 pending' in ask('Show pending complaints')
                assert 'C001' in ask('Find Alpha Hospital')
                assert 'data checks' in ask('Test CRM knowledge').lower()
                assert 'read-only' in ask('Delete CRM records')
                assert page.evaluate('JSON.stringify({clients,sectionRecords,complaints})')==before

                # A separate user saves a new source revision; the next reply reads it directly.
                with app.db_conn() as conn:
                    workspace=json.loads(conn.execute('SELECT data FROM crm_workspace').fetchone()['data'])
                    workspace['hk_v2_leads'].append({'id':'AUTO-'+channel,'name':'Fresh upload','status':'New Lead'})
                    conn.execute('UPDATE crm_workspace SET data=?, revision=revision+1',(json.dumps(workspace),))
                expected=3
                assert f'Leads & Queries: {expected}' in ask('Show leads')
                draft=page.evaluate("quoteSaarthiRequest('Draft a WhatsApp follow-up',{selected_client:{id:'C001',workspaceScope:'clients'}},'crm')")
                assert 'Alpha contact' in draft['reply'] and 'Draft only' in draft['reply']
                page.set_viewport_size({'width':390,'height':844})
                box=page.locator('#chatWidget').bounding_box()
                assert box and box['x']>=0 and box['x']+box['width']<=390
                page.reload();page.wait_for_function('dashboardReady&&!document.body.inert')
                page.evaluate('toggleChat(true)')
                assert f'Leads & Queries: {expected}' in ask('Show leads')
                assert not errors,errors
                reports.append({'browser':channel,'saved_counts':True,'queries_complaints':True,
                    'new_upload_automatic':True,'read_only':True,'mobile_reload':True,'javascript_errors':errors})
                # Restore fixture baseline for the next browser.
                fixture.save({'hk_v2_leads':[{'id':'L001','name':'Alpha Hospital','city':'Jaipur','status':'Query Received','next':'2026-10-23','product':'Pump'},
                                           {'id':'L002','name':'Gamma Hospital','status':'New Lead','next':'2026-10-25'}]})
                browser.close()
    finally:
        server.close();fixture.doCleanups()
    print(json.dumps(reports,indent=2))


if __name__=='__main__':check()
