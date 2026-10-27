"""Real Chrome/Edge checks of admin sign-in, viewer protection and activity UI."""
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
from werkzeug.security import generate_password_hash

PASSWORD = 'browser-personal-admin-123'


def check():
    reports = []
    with tempfile.TemporaryDirectory() as temp, patch.object(app, 'DB_PATH', Path(temp) / 'crm.db'), patch.object(app, 'admin_password_hash', return_value=''):
        app.init_db()
        with app.db_conn() as conn:
            conn.execute('INSERT INTO crm_admin_users VALUES (?,?,1)', ('alice', generate_password_hash(PASSWORD)))
            conn.execute('INSERT INTO crm_admin_users VALUES (?,?,1)', ('bob', generate_password_hash(PASSWORD)))
        server = create_server(app.app, host='127.0.0.1', port=0)
        Thread(target=server.run, daemon=True).start()
        address = f'http://127.0.0.1:{server.effective_port}/'
        try:
            with sync_playwright() as playwright:
                for channel in os.getenv('BROWSER_CHANNELS', 'chrome,msedge').split(','):
                    with app.db_conn() as conn:
                        conn.execute('DELETE FROM crm_workspace')
                    app.init_db()
                    browser = playwright.chromium.launch(**({} if channel == 'chromium' else {'channel': channel}), headless=True)
                    owner, viewer = browser.new_context(), browser.new_context()
                    page, other = owner.new_page(), viewer.new_page()
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(address); other.goto(address)
                    for tab in (page, other):
                        tab.wait_for_function('dashboardReady && !document.body.inert && sheetState !== null')
                    assert not page.evaluate('crmAdminSession.admin')
                    assert page.get_by_role('button', name='+ Add Calling Note', exact=True).is_disabled()
                    denied = viewer.request.post(address + 'api/workspace', data={'revision': 0, 'values': {'hk_v2_clients': []}}, headers={'X-CRM-Request': '1'})
                    assert denied.status == 403
                    page.locator('#adminAccessButton').click()
                    page.locator('#adminUsername').fill('alice')
                    page.locator('#adminLoginPassword').fill('incorrect')
                    page.locator('#adminSignInButton').click()
                    page.wait_for_function("document.getElementById('adminAccessError').textContent.includes('Invalid')")
                    page.locator('#adminLoginPassword').fill(PASSWORD)
                    page.locator('#adminSignInButton').click()
                    page.wait_for_function("crmAdminSession.username === 'alice'")
                    assert page.locator('#adminLoginPassword').input_value() == ''
                    page.wait_for_function("document.getElementById('adminActivityRows').textContent.includes('alice')")
                    assert 'alice' in page.locator('#adminActivityRows').inner_text()
                    page.get_by_role('button', name='Close', exact=True).click()
                    page.evaluate("navigate('clients')")
                    page.get_by_role('button', name='+ Add Client', exact=True).click()
                    page.locator('#newName').fill('Admin Only Hospital')
                    page.locator('#newCity').fill('Jaipur')
                    page.locator('#newRequirement').fill('Medical supplies')
                    page.locator('#clientSaveButton').click()
                    page.wait_for_function("clients.some(row => row.name === 'Admin Only Hospital')")
                    other.evaluate('refreshSharedWorkspace(true)')
                    other.wait_for_function("clients.some(row => row.name === 'Admin Only Hospital')")
                    assert not other.evaluate('crmAdminSession.admin')
                    page.locator('#adminAccessButton').click()
                    page.wait_for_function("document.getElementById('adminActivityRows').textContent.includes('hk_v2_clients') || document.getElementById('adminActivityRows').textContent.includes('clients:')")
                    assert 'added' in page.locator('#adminActivityRows').inner_text()
                    page.reload()
                    page.wait_for_function("dashboardReady && crmAdminSession.username === 'alice'")
                    page.locator('#adminAccessButton').click()
                    page.get_by_role('button', name='Sign out', exact=True).click()
                    page.wait_for_function('!crmAdminSession.admin')
                    assert not viewer.request.get(address + 'api/admin/activity').ok
                    assert not owner.request.post(address + 'api/workspace', data={'revision': 1, 'values': {'hk_v2_clients': []}}, headers={'X-CRM-Request': '1'}).ok
                    page.locator('#adminUsername').fill('bob')
                    page.locator('#adminLoginPassword').fill(PASSWORD)
                    page.locator('#adminSignInButton').click()
                    page.wait_for_function("crmAdminSession.username === 'bob'")
                    page.get_by_role('button', name='Close', exact=True).click()
                    page.evaluate("writeDashboardValues({hk_v2_clients: []})")
                    page.locator('#adminAccessButton').click()
                    page.wait_for_function("document.getElementById('adminActivityRows').textContent.includes('1 removed')")
                    history = owner.request.get(address + 'api/admin/activity').json()['events']
                    assert any(event['actor'] == 'alice' and event['action'] == 'data change' for event in history)
                    assert any(event['actor'] == 'bob' and event['action'] == 'data change' for event in history)
                    assert not errors, errors
                    page.set_viewport_size({'width': 390, 'height': 844})
                    assert page.locator('#adminAccessDialog').is_visible()
                    reports.append({'browser': channel, 'viewer_write_blocked': True, 'named_admin_signin': True,
                                    'create_and_delete_attribution': True, 'history_ui': True,
                                    'logout_revokes_writes': True, 'javascript_errors': errors})
                    owner.close(); viewer.close(); browser.close()
        finally:
            server.close()
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    check()
