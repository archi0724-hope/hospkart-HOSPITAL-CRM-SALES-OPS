"""Authorization and audit tests use real logins and anonymous Flask clients."""
import hashlib
import hmac
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from flask.testing import FlaskClient
from werkzeug.security import generate_password_hash
from crm_test_environment import app
import admin_access

HEADERS = {'X-CRM-Request': '1'}
PASSWORD = 'personal-admin-password-123'


class AdminAccessTests(unittest.TestCase):
    def setUp(self):
        policy = patch.dict(app.app.config, {'ADMIN_ACCESS_REQUIRED': True})
        policy.start(); self.addCleanup(policy.stop)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        db = patch.object(app, 'DB_PATH', Path(temporary.name) / 'crm.db')
        db.start(); self.addCleanup(db.stop)
        shared = patch.object(app, 'admin_password_hash', return_value='')
        shared.start(); self.addCleanup(shared.stop)
        app.init_db()
        with app.db_conn() as conn:
            conn.execute('INSERT INTO crm_admin_users VALUES (?,?,1)', ('alice', generate_password_hash(PASSWORD)))
        self.viewer = FlaskClient(app.app)
        self.admin = FlaskClient(app.app)

    def login(self, client=None, username='alice', password=PASSWORD):
        return (client or self.admin).post('/api/admin/login', json={'username': username, 'password': password})

    def save(self, client=None, records=None, revision=0):
        return (client or self.admin).post('/api/workspace', json={'revision': revision,
            'values': {'hk_v2_clients': records if records is not None else [{'id': 'H-1', 'name': 'Hospital A'}]}}, headers=HEADERS)

    def activity(self):
        return self.admin.get('/api/admin/activity').json['events']

    def test_all_mutation_routes_reject_anonymous_direct_calls(self):
        exemptions = {'/api/admin/login', '/api/admin/logout', '/api/admin/remove-import', *admin_access.READ_POSTS}
        for rule in app.app.url_map.iter_rules():
            if not rule.rule.startswith('/api/') or rule.rule in exemptions or rule.rule.startswith('/api/quotesaarthi/download/'):
                continue
            for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                if method not in rule.methods:
                    continue
                url = rule.rule.replace('<int:job_id>', '1')
                with self.subTest(url=url, method=method):
                    response = self.viewer.open(url, method=method, json={'is_admin': True, 'username': 'alice', 'admin_password': PASSWORD}, headers=HEADERS)
                    self.assertEqual(response.status_code, 403, response.json)
        self.assertEqual(self.viewer.get('/api/workspace').json['workspace']['revision'], 0)
        self.assertEqual(self.viewer.get('/api/admin/activity').status_code, 403)

    def test_dashboard_excludes_admin_panel_and_admin_page_keeps_authentication(self):
        dashboard=self.viewer.get('/').get_data(as_text=True)
        self.assertNotIn('id="adminAccessDialog"',dashboard)
        self.assertNotIn('id="adminAccessButton"',dashboard)
        self.assertNotIn('id="adminLoginPassword"',dashboard)
        page=self.viewer.get('/admin')
        self.assertEqual(page.status_code,200)
        self.assertIn('id="adminLoginPassword"',page.get_data(as_text=True))
        self.assertIn('no-store',page.headers['Cache-Control'])
        self.assertEqual(self.save(self.viewer).status_code,403)

    def test_viewer_can_read_and_export(self):
        self.assertEqual(self.viewer.get('/api/workspace').status_code, 200)
        self.assertEqual(self.viewer.get('/api/spreadsheet/status').status_code, 200)
        self.assertEqual(self.viewer.post('/api/spreadsheet/export', json={'leads': [], 'queries': []}, headers=HEADERS).status_code, 200)

    def test_named_admin_changes_and_removals_are_logged_without_record_values(self):
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.save().status_code, 200)
        self.assertEqual(self.save(records=[{'id': 'H-1', 'name': 'Private changed hospital'}], revision=1).status_code, 200)
        self.assertEqual(self.save(records=[], revision=2).status_code, 200)
        events = [event for event in self.activity() if event['action'] == 'data change']
        self.assertEqual(len(events), 3)
        self.assertTrue(all(event['actor'] == 'alice' for event in events))
        changes = [event['details']['operations'][0]['changes']['hk_v2_clients'] for event in events]
        self.assertEqual(changes[0]['removed'], 1)
        self.assertEqual(changes[1]['edited'], 1)
        self.assertEqual(changes[2]['added'], 1)
        self.assertNotIn('Private changed hospital', json.dumps(events))
        self.assertNotIn(PASSWORD, json.dumps(self.activity()))

    def test_reset_preserves_history_and_logs_deletions(self):
        self.login(); self.save()
        before = len(self.activity())
        response = self.admin.post('/api/dashboard/reset', json={'confirmed_reset': True, 'confirmation': 'RESET DASHBOARD'})
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(self.activity()), before)
        self.assertTrue(any(event['action'] == 'sign-in' for event in self.activity()))
        self.assertEqual(self.viewer.get('/api/workspace').json['workspace']['values']['hk_v2_clients'], [])

    def test_audit_failure_rolls_back_data_and_noop_does_not_log(self):
        self.login()
        with patch.object(admin_access, 'add_event', side_effect=app.sqlite3.DatabaseError('audit unavailable')):
            self.assertEqual(self.save().status_code, 503)
        self.assertEqual(self.viewer.get('/api/workspace').json['workspace']['revision'], 0)
        self.save()
        before = len(self.activity())
        self.assertEqual(self.save(revision=1).status_code, 200)
        self.assertEqual(len(self.activity()), before)
        self.assertEqual(self.save(revision=0).status_code, 409)
        self.assertEqual(len(self.activity()), before)

    def test_logout_expiry_password_rotation_and_disabled_account_revoke_access(self):
        self.login()
        cookie = self.admin.get_cookie(admin_access.COOKIE)
        self.assertTrue(cookie.http_only)
        self.assertEqual(cookie.same_site, 'Strict')
        self.assertEqual(self.admin.post('/api/admin/logout', json={}).status_code, 200)
        self.assertEqual(self.save().status_code, 403)
        self.login()
        with app.db_conn() as conn:
            conn.execute('UPDATE crm_admin_sessions SET expires=?', (time.time()-1,))
        self.assertEqual(self.save().status_code, 403)
        self.login()
        with app.db_conn() as conn:
            conn.execute('UPDATE crm_admin_users SET password_hash=? WHERE username=?', (generate_password_hash('changed-personal-password'), 'alice'))
        self.assertEqual(self.save().status_code, 403)
        self.login(password='changed-personal-password')
        with app.db_conn() as conn:
            conn.execute('UPDATE crm_admin_users SET enabled=0 WHERE username=?', ('alice',))
        self.assertEqual(self.save().status_code, 403)

    def test_cross_origin_requests_and_forged_cookies_cannot_write(self):
        self.login()
        response = self.admin.post('/api/workspace', json={}, headers={**HEADERS, 'Origin': 'https://evil.test'})
        self.assertEqual(response.status_code, 403)
        self.viewer.set_cookie(admin_access.COOKIE, 'alice')
        self.assertEqual(self.save(self.viewer).status_code, 403)
        self.assertEqual(self.viewer.post('/api/admin/login', json={'username': 'alice', 'password': PASSWORD}, headers={'Origin': 'https://evil.test'}).status_code, 403)
        self.assertEqual(self.viewer.post('/api/admin/login', data={'username': 'alice', 'password': PASSWORD}).status_code, 400)

    def test_signin_is_rate_limited(self):
        for _ in range(5):
            self.assertEqual(self.login(password='wrong').status_code, 403)
        self.assertEqual(self.login().status_code, 429)

    def test_activity_pagination_and_database_restart(self):
        self.login()
        with app.db_conn() as conn:
            for index in range(105):
                admin_access.add_event(conn, 'alice', 'test activity', str(index), {})
        first = self.admin.get('/api/admin/activity').json
        self.assertEqual(len(first['events']), 100)
        second = self.admin.get('/api/admin/activity?before=' + str(first['next_before'])).json
        self.assertFalse(set(row['id'] for row in first['events']) & set(row['id'] for row in second['events']))
        app.init_db()
        self.assertEqual(self.admin.get('/api/admin/session').json['username'], 'alice')
        self.assertEqual(self.admin.get('/api/admin/activity').json['events'], first['events'])

    def test_background_writes_are_identified_and_audited(self):
        @admin_access.system_task
        def synchronize():
            with app.db_conn() as conn:
                conn.execute('INSERT INTO sheet_source_preferences VALUES (1,?)', ('{}',))
        synchronize()
        self.login()
        events = [event for event in self.activity() if event['action'] == 'data change']
        self.assertEqual(events[0]['actor'], 'System: synchronize')

    def test_webhook_requires_valid_provider_signature(self):
        payload = b'{"entry":[]}'
        with patch.dict(app.os.environ, {'WHATSAPP_APP_SECRET': 'test-webhook-secret'}):
            self.assertEqual(self.viewer.post('/webhook', data=payload, content_type='application/json').status_code, 403)
            signature = 'sha256=' + hmac.new(b'test-webhook-secret', payload, hashlib.sha256).hexdigest()
            self.assertEqual(self.viewer.post('/webhook', data=payload, content_type='application/json', headers={'X-Hub-Signature-256': signature}).status_code, 200)


if __name__ == '__main__':
    unittest.main()
