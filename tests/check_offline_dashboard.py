"""Dashboard navigation remains usable when the shared database is unavailable."""
import json
import os
import sqlite3
import sys
from pathlib import Path
from threading import Thread
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crm_test_environment import app
from database_readiness import DatabaseReadiness
from playwright.sync_api import sync_playwright
from waitress import create_server


def check():
    state = DatabaseReadiness(Mock(side_effect=sqlite3.DatabaseError('simulated outage')), defer_errors=True)
    reports = []
    with patch.object(app, 'database_readiness', state), sync_playwright() as playwright:
        server = create_server(app.app, host='127.0.0.1',port=0)
        Thread(target=server.run,daemon=True).start()
        address = f'http://127.0.0.1:{server.effective_port}/'
        try:
            for channel in os.getenv('BROWSER_CHANNELS','chrome,msedge').split(','):
                browser = playwright.chromium.launch(**({} if channel=='chromium' else {'channel':channel}),headless=True)
                for cached in (False, True):
                    context=browser.new_context();page=context.new_page();errors=[]
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    if cached:
                        context.add_init_script("""
                            const today = new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
                            localStorage.setItem('hk_v2_clients',JSON.stringify([
                              {id:'CACHED',name:'Cached Test Hospital',status:'Completed / Served',city:'Jaipur',executive:'Test',type:'New Prospect',next:'2000-01-01'},
                              {id:'TODAY',name:'Today Hospital',status:'Contacted',next:today+'T00:00:00+05:30'},
                              {id:'BAD',name:'Invalid Date Hospital',status:'New Lead',next:'2026-02-30'}]));
                            localStorage.setItem('hk_v2_leads','[]');
                            localStorage.setItem('hk_v2_complaints',JSON.stringify([{id:'OPEN',status:'Open',customer_name:'Test',subject:'Test',details:'Test',priority:'High',assigned_owner:'Test',created_at:'2026-10-20T00:00:00+05:30',updated_at:'2026-10-20T00:00:00+05:30'},{id:'DONE',status:'Resolved',customer_name:'Test',subject:'Test',details:'Test',priority:'Low',assigned_owner:'Test',created_at:'2026-10-20T00:00:00+05:30',updated_at:'2026-10-20T00:00:00+05:30'}]));
                        """)
                    response=page.goto(address)
                    assert response.status==200
                    page.wait_for_function("!document.body.inert && document.getElementById('databaseOfflineBanner')!==null")
                    assert page.locator('.sidebar').count()==1
                    assert page.locator('#databaseOfflineMessage').is_visible()
                    assert not page.evaluate('dashboardReady || crmAdminSession.can_edit')
                    assert page.locator('.top-actions button').filter(has_text='+ Add Calling Note').is_disabled()
                    if cached:
                        assert 'saved copy' in page.locator('#databaseOfflineMessage').inner_text()
                        assert page.locator('#kpiClients').inner_text()!='—'
                    else:
                        assert page.locator('#kpiClients').inner_text()=='—'
                    if cached:
                        page.wait_for_function('intelligenceSnapshot?.offline_copy===true')
                        assert page.locator('#intelligenceOverdue').inner_text()=='1'
                        assert page.locator('#intelligenceToday').inner_text()=='1'
                        assert page.locator('#intelligenceComplaints').inner_text()=='1'
                        assert 'browser copy' in page.locator('#intelligenceSource').inner_text()
                        page.evaluate("document.getElementById('search').value='no match';applyFilters()")
                        assert page.locator('#intelligenceOverdue').inner_text()=='1'
                        page.evaluate('clearFilters()')
                        page.get_by_role('button',name='Ask for my CRM brief',exact=False).click()
                        page.wait_for_function("document.getElementById('chatBody').textContent.includes('Offline browser copy')")
                        assert 'Overdue follow-ups: 1' in page.locator('#chatBody').inner_text()
                        page.get_by_role('button',name='Close QuoteSaarthi',exact=True).click()
                        page.evaluate("dashboardStorage.delete('hk_v2_complaints');renderIntelligence(null,true)")
                        assert page.locator('#intelligenceComplaints').inner_text()=='—'
                    else:
                        assert page.locator('#intelligenceOverdue').inner_text()=='—'
                        assert page.locator('#intelligenceToday').inner_text()=='—'
                        assert page.locator('#intelligenceComplaints').inner_text()=='—'
                    page.evaluate("navigate('clients')")
                    assert page.locator('#page-clients').is_visible()
                    if cached:
                        assert 'Cached Test Hospital' in page.locator('#page-clients').inner_text()
                    else:
                        assert page.locator('#clientTotal').inner_text()=='—'
                    assert page.locator('#databaseOfflineBanner').get_attribute('class')=='database-status-note'
                    assert not page.locator('#sharedDatabaseStatus').is_visible()
                    await_reason = 'These changes were not saved. The shared database is unavailable.'
                    page.evaluate('(reason)=>{document.getElementById("sharedRecoveryNotice").classList.remove("hidden");document.getElementById("sharedRecoveryReason").textContent=reason;renderDashboardAvailability();}', await_reason)
                    assert page.locator('#sharedRecoveryNotice').is_visible()
                    assert page.locator('#sharedRecoveryNotice button').filter(has_text='Restore preserved').is_disabled()
                    assert page.locator('#sharedRecoveryNotice button').filter(has_text='Download preserved').is_enabled()
                    assert 'Unsaved changes are preserved' in page.locator('#sharedRecoveryReason').inner_text()
                    assert not errors,errors
                    reports.append({'browser':channel,'cached_copy':cached,'navigation':True,'honest_counts':True,'writes_disabled':True})
                    context.close()
                browser.close()
        finally:server.close()
    print(json.dumps(reports,indent=2))

if __name__=='__main__':check()
