"""Complaint lifecycle across independent Chrome/Edge profiles; synthetic data only."""
import json
import os
import sys
import tempfile
from pathlib import Path
from threading import Thread
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crm_test_environment import app
from playwright.sync_api import sync_playwright
from waitress import create_server


def check():
    reports = []
    with tempfile.TemporaryDirectory() as temp, patch.object(app, 'DB_PATH', Path(temp) / 'test.db'), patch.object(app, 'DATA_DIR', Path(temp)):
        app.init_db()
        if app.scheduler.running: app.scheduler.pause()
        server = create_server(app.app, host='127.0.0.1', port=0); Thread(target=server.run, daemon=True).start()
        address = f'http://127.0.0.1:{server.effective_port}/'
        try:
            with sync_playwright() as p:
                for channel in os.getenv('BROWSER_CHANNELS', 'chrome,msedge').split(','):
                    with app.db_conn() as conn: conn.execute('DELETE FROM crm_workspace')
                    app.init_db()
                    app.app.test_client().post('/api/workspace', json={'revision': 0, 'values': {'hk_v2_leads': [
                        {'id': '0001', 'name': 'Test Hospital', 'status': 'New Lead', 'city': 'Test', 'next': '', 'remark': '', 'quote': 0, 'order': 0}]}}, headers={'X-CRM-Request': '1'})
                    browser = p.chromium.launch(channel=None if channel == 'chromium' else channel, headless=True)
                    owner = browser.new_context(accept_downloads=True); peer = browser.new_context(); a = owner.new_page(); b = peer.new_page(); errors = []
                    for page in (a, b):
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.goto(address); page.wait_for_function('dashboardReady&&!document.body.inert'); page.evaluate("navigate('leads')")
                    a.get_by_role('button', name='+ Add Complaint', exact=True).click()
                    a.locator('#complaintRelatedRecord').select_option(label='Test Hospital · Leads & Queries · 0001')
                    a.locator('#complaintSubject').fill('Replacement needed <img src=x onerror=alert(1)>')
                    a.locator('#complaintDetails').fill('A delivered item needs replacement.\nPlease follow up.')
                    a.locator('#complaintOwner').fill('Service team'); a.locator('#complaintPriority').select_option('High')
                    a.locator('#complaintSaveButton').click(); a.wait_for_function('complaints.length===1&&!complaintSaving')
                    identifier = a.evaluate('complaints[0].id')
                    b.wait_for_function('complaints.length===1', timeout=15000)
                    assert b.locator('#complaintPending').inner_text() == '1'
                    assert b.locator('#complaintUrgent').inner_text() == '1'
                    assert b.locator('#complaintRows img').count() == 0
                    assert b.evaluate('complaints[0].record_id') == '0001'

                    a.locator('#complaintRows').get_by_role('button', name='View / Update', exact=True).click()
                    a.locator('#complaintStatus').select_option('In Progress'); a.locator('#complaintSaveButton').click()
                    a.wait_for_function("complaints[0].status==='In Progress'&&!complaintSaving")
                    b.wait_for_function("complaints[0].status==='In Progress'", timeout=15000)
                    a.locator('#complaintRows').get_by_role('button', name='Resolve', exact=True).click()
                    a.locator('#complaintSaveButton').click()
                    assert a.locator('#complaintResolution').evaluate('field=>!field.validity.valid')
                    assert a.evaluate('complaints[0].status') == 'In Progress'
                    a.locator('#complaintResolution').fill('Replacement delivered and confirmed by customer.')
                    a.locator('#complaintSaveButton').click()
                    a.wait_for_function("complaints[0].status==='Resolved'&&!complaintSaving")
                    b.wait_for_function("complaints[0].status==='Resolved'", timeout=15000)
                    assert b.locator('#complaintResolved').inner_text() == '1'
                    assert b.locator('#complaintPending').inner_text() == '0'
                    assert 'Replacement delivered' in b.locator('#complaintRows').inner_text()
                    assert b.evaluate('complaints[0].resolved_at')

                    b.locator('#complaintStatusFilter').select_option('Open'); assert b.locator('#complaintRows [data-complaint-index]').count() == 0
                    b.locator('#complaintStatusFilter').select_option('Resolved'); assert b.locator('#complaintRows [data-complaint-index]').count() == 1
                    a.locator('#complaintRows').get_by_role('button', name='Reopen', exact=True).click()
                    a.locator('#complaintSaveButton').click(); a.wait_for_function("complaints[0].status==='Open'&&!complaintSaving")
                    assert a.evaluate('complaints[0].id') == identifier
                    assert a.evaluate('complaints[0].resolved_at') == ''

                    # A checkpoint has complaints; restoring an older checkpoint does not erase them.
                    snapshot = a.evaluate("makeDashboardBackup('Complaint backup')")
                    assert snapshot['complaints'][0]['id'] == identifier
                    a.evaluate("async()=>{const old=makeDashboardBackup('Old snapshot');delete old.complaints;await applyDashboardCheckpoint(old,'Restore old checkpoint test');}")
                    assert a.evaluate('complaints.length') == 1
                    a.reload(); a.wait_for_function('dashboardReady&&!document.body.inert')
                    assert a.evaluate('complaints[0].id') == identifier
                    a.evaluate("navigate('leads')"); a.set_viewport_size({'width': 390, 'height': 844})
                    a.get_by_role('button', name='+ Add Complaint', exact=True).click()
                    assert a.locator('#complaintSubject').is_visible()
                    a.locator('#complaintCancelButton').click()
                    assert not errors, errors
                    reports.append({'browser': channel, 'create_and_shared_visibility': True, 'resolution_required': True,
                                    'resolve_and_reopen': True, 'filters_counts_and_safe_text': True,
                                    'backup_compatibility_and_reload': True, 'mobile': True, 'javascript_errors': errors})
                    owner.close(); peer.close(); browser.close()
        finally: server.close()
    print(json.dumps(reports, indent=2))


if __name__ == '__main__': check()
