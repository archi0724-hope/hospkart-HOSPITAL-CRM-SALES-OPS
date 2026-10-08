import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

import app


class ImportRemovalAuthorizationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'admin.hash'
        path_patch = patch.object(app, 'ADMIN_PASSWORD_PATH', self.path)
        path_patch.start()
        self.addCleanup(path_patch.stop)
        env_patch = patch.dict(app.os.environ, {'ADMIN_PASSWORD_HASH': ''})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        app.admin_attempts.clear()
        self.client = app.app.test_client()
        self.password = 'test-admin-password-only'
        self.payload = {'scope': 'worksheet', 'name': 'Categorized Items', 'confirmation': 'REMOVE Categorized Items', 'password': self.password}

    def configure(self):
        self.path.write_text(generate_password_hash(self.password), encoding='utf-8')

    def test_unconfigured_admin_cannot_remove_imports(self):
        self.assertFalse(self.client.get('/api/admin/status').json['configured'])
        self.assertEqual(self.client.post('/api/admin/remove-import', json=self.payload).status_code, 503)

    def test_wrong_password_and_browser_admin_flag_are_rejected(self):
        self.configure()
        for password in ['wrong', None, True]:
            response = self.client.post('/api/admin/remove-import', json={**self.payload, 'password': password, 'is_admin': True})
            self.assertEqual(response.status_code, 403)

    def test_authorization_is_for_exact_selected_import_only(self):
        self.configure()
        response = self.client.post('/api/admin/remove-import', json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'ok': True, 'authorized_scope': 'worksheet', 'authorized_name': 'Categorized Items'})
        self.assertNotIn('password', str(response.json))

    def test_rghs_section_removal_is_supported(self):
        self.configure()
        payload = {**self.payload, 'scope': 'segment', 'name': 'rghs', 'confirmation': 'REMOVE rghs'}
        response = self.client.post('/api/admin/remove-import', json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'ok': True, 'authorized_scope': 'segment', 'authorized_name': 'rghs'})

    def test_confirmation_and_scope_are_required(self):
        self.configure()
        for updates in [{'confirmation': 'REMOVE EVERYTHING'}, {'scope': 'dashboard'}, {'name': ''}, {'scope': 'segment', 'name': 'unknown'}]:
            with self.subTest(updates=updates):
                self.assertEqual(self.client.post('/api/admin/remove-import', json={**self.payload, **updates}).status_code, 400)

    def test_foreign_origin_is_rejected(self):
        self.configure()
        self.assertEqual(self.client.post('/api/admin/remove-import', json=self.payload, headers={'Origin':'https://unrelated.example'}).status_code, 403)

    def test_repeated_bad_passwords_are_throttled(self):
        self.configure()
        for _ in range(5):
            self.assertEqual(self.client.post('/api/admin/remove-import', json={**self.payload, 'password': 'wrong'}).status_code, 403)
        self.assertEqual(self.client.post('/api/admin/remove-import', json=self.payload).status_code, 429)

    def test_successful_authorization_does_not_mutate_original_workbook(self):
        self.configure()
        before = self.client.get('/api/invoice-workbook').json
        self.client.post('/api/admin/remove-import', json=self.payload)
        self.assertEqual(self.client.get('/api/invoice-workbook').json, before)


if __name__ == '__main__':
    unittest.main()
