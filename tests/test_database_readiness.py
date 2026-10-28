"""Startup recovery uses maintenance responses, never an empty fallback database."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from flask.testing import FlaskClient
from crm_test_environment import app
from database_readiness import DatabaseReadiness


class DatabaseReadinessTests(unittest.TestCase):
    def test_retries_are_throttled_and_recover_after_database_returns(self):
        initialize = Mock(side_effect=[sqlite3.DatabaseError('unavailable'), None])
        state = DatabaseReadiness(initialize, defer_errors=True)
        with patch('database_readiness.monotonic', return_value=100):
            self.assertFalse(state.ensure())
            self.assertFalse(state.ensure())
        self.assertEqual(initialize.call_count, 1)
        with patch('database_readiness.monotonic', return_value=161):
            self.assertTrue(state.ensure())
            self.assertTrue(state.ensure())
        self.assertEqual(initialize.call_count, 2)

    def test_local_database_errors_still_fail_explicitly(self):
        state = DatabaseReadiness(Mock(side_effect=sqlite3.DatabaseError('unavailable')))
        with self.assertRaises(sqlite3.DatabaseError):
            state.ensure()

    def test_maintenance_blocks_writes_and_recovery_loads_the_saved_database(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(app, 'DB_PATH', Path(temp)/'crm.db'):
            app.init_db()
            client = FlaskClient(app.app)
            record = {'id': 'SAVED', 'name': 'Existing hospital'}
            saved = client.post('/api/workspace', json={'revision': 0, 'values': {'hk_v2_clients': [record]}}, headers={'X-CRM-Request': '1'})
            self.assertEqual(saved.status_code, 200)
            state = DatabaseReadiness(Mock(side_effect=sqlite3.DatabaseError('unavailable')), defer_errors=True)
            with patch.object(app, 'database_readiness', state):
                page = client.get('/')
                self.assertEqual(page.status_code, 200)
                self.assertIn('page-dashboard', page.get_data(as_text=True))
                self.assertIn('offline-dashboard.js', page.get_data(as_text=True))
                self.assertEqual(client.get('/api/health').status_code, 503)
                self.assertEqual(client.post('/api/workspace', json={}).status_code, 503)
                self.assertEqual(client.get('/static/admin-access.js').status_code, 200)
                job = Mock();app.when_database_ready(job)();job.assert_not_called()
                state.initialize = app.init_db;state.next_attempt = 0
                self.assertEqual(client.get('/').status_code, 200)
                self.assertEqual(client.get('/api/workspace').json['workspace']['values']['hk_v2_clients'], [record])
                app.when_database_ready(job)();job.assert_called_once()


if __name__ == '__main__':unittest.main()
