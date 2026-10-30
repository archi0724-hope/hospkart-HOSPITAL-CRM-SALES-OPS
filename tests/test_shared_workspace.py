import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crm_test_environment import app
from shared_workspace import empty_values


class SharedWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.db = patch.object(app, 'DB_PATH', Path(self.temp.name) / 'shared.db')
        self.db.start(); self.addCleanup(self.db.stop)
        app.init_db(); self.user_a = app.app.test_client(); self.user_b = app.app.test_client()

    def get(self, client=None):
        return (client or self.user_a).get('/api/workspace').json['workspace']

    def save(self, values, revision=None, client=None, **kwargs):
        return (client or self.user_a).post('/api/workspace', json={
            'revision': self.get()['revision'] if revision is None else revision,
            'values': values, **kwargs}, headers={'X-CRM-Request': '1'})

    def test_fresh_database_is_empty_and_does_not_publish_demo_records(self):
        state = self.get()
        self.assertEqual(state['values'], empty_values())
        self.assertFalse(state['initialized'])
        self.assertEqual(state['revision'], 0)

    def test_uploads_records_and_workbook_are_shared_and_persisted(self):
        values = empty_values()
        values['hk_v2_clients'] = [{'id': '0001', 'name': 'Shared Hospital', 'mobile': '000123'}]
        values['hk_v2_calls'] = [{'clientId': '0001', 'notes': 'Follow up'}]
        values['hk_v2_feedback'] = [{'clientId': '0001', 'text': 'Good'}]
        for scope in ('rghs', 'leads', 'served', 'doctors', 'potential'):
            values['hk_v2_' + scope] = [{'id': scope + '-1', 'name': scope + ' upload'}]
        values['hk_v2_segments'] = {scope: values['hk_v2_' + scope] for scope in ('served', 'doctors', 'potential')}
        values['hk_v2_invoice_workbook'] = {'filename': 'Private.xlsx', 'sheets': [{'name': 'Invoices', 'rows': [{'Invoice': '0001'}]}]}
        self.assertEqual(self.save(values).status_code, 200)
        self.assertEqual(self.get(self.user_b)['values'], values)
        app.init_db()
        self.assertEqual(self.get(app.app.test_client())['values'], values)

    def test_stale_user_cannot_overwrite_another_users_import(self):
        revision = self.get()['revision']
        self.save({'hk_v2_clients': [{'id': '1', 'name': 'First user'}]}, revision)
        rejected = self.save({'hk_v2_clients': [{'id': '2', 'name': 'Stale user'}]}, revision, self.user_b)
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(rejected.json['workspace']['values']['hk_v2_clients'][0]['name'], 'First user')
        self.assertEqual(self.get()['values']['hk_v2_clients'][0]['name'], 'First user')

    def test_compact_save_preserves_other_records_and_returns_section_aliases(self):
        clients = [{'id': 'c1', 'name': 'Kept hospital'}]
        self.save({'hk_v2_clients': clients})
        doctors = [{'id': 'd1', 'name': 'Updated doctor'}]
        response = self.save({'hk_v2_doctors': doctors}, response='changes')
        self.assertEqual(response.status_code, 200)
        values = response.json['workspace']['values']
        self.assertNotIn('hk_v2_clients', values)
        self.assertNotIn('hk_v2_backups', values)
        self.assertEqual(values['hk_v2_doctors'], doctors)
        self.assertEqual(values['hk_v2_segments']['doctors'], doctors)
        self.assertEqual(self.get()['values']['hk_v2_clients'], clients)
        rejected = self.save({'hk_v2_doctors': []}, revision=0, response='changes')
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(rejected.json['workspace']['values']['hk_v2_clients'], clients)

    def test_browser_cache_requires_matching_revision_and_timestamp(self):
        state = self.save({'hk_v2_clients': [{'id': 'c1', 'name': 'Current hospital'}]}).json['workspace']
        result = self.user_a.get('/api/workspace', query_string={'revision': state['revision'], 'updated_at': state['updated_at']})
        self.assertTrue(result.json['unchanged'])
        different = self.user_a.get('/api/workspace', query_string={'revision': state['revision'], 'updated_at': 'older-cache'})
        self.assertEqual(different.json['workspace']['values']['hk_v2_clients'][0]['name'], 'Current hospital')

    def test_compact_record_edit_keeps_saved_checkpoint_archive(self):
        checkpoint = {'id': 'saved', 'clients': [{'id': 'old', 'name': 'Historic hospital'}], 'calls': [], 'feedback': [], 'invoiceWorkbook': None}
        self.save({'hk_v2_backups': [checkpoint]})
        response = self.save({'hk_v2_clients': [{'id': 'new', 'name': 'Current hospital'}]}, response='changes')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('hk_v2_backups', response.json['workspace']['values'])
        self.assertEqual(self.get()['values']['hk_v2_backups'], [checkpoint])

    def test_initial_migration_cannot_replace_an_initialized_workspace(self):
        self.save({'hk_v2_clients': [{'id': '1', 'name': 'Shared'}]}, initialize_only=True)
        result = self.save({'hk_v2_clients': [{'id': '2', 'name': 'Old browser'}]}, initialize_only=True)
        self.assertEqual(result.status_code, 409)
        self.assertEqual(self.get()['values']['hk_v2_clients'][0]['name'], 'Shared')

    def test_section_aliases_stay_consistent_and_conflicting_aliases_are_rejected(self):
        doctors = [{'id': 'd1', 'name': 'Doctor'}]
        self.save({'hk_v2_doctors': doctors})
        self.assertEqual(self.get()['values']['hk_v2_segments']['doctors'], doctors)
        result = self.save({'hk_v2_doctors': doctors, 'hk_v2_segments': {'doctors': []}})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(self.get()['values']['hk_v2_doctors'], doctors)

    def test_invalid_payload_is_atomic_and_rejects_system_keys(self):
        for values in ({'OPENAI_API_KEY': 'bad'}, {'hk_v2_clients': [None]}, {'hk_v2_clients': [{'id': '1'}]},
                       {'hk_v2_invoice_workbook': {'sheets': None}}, {'hk_v2_backups': [{}]},
                       {'hk_v2_clients': [], 'hk_v2_segments': {'doctors': [None]}}):
            with self.subTest(values=values):
                self.assertEqual(self.save(values).status_code, 400)
                self.assertEqual(self.get()['revision'], 0)
        self.assertEqual(self.save({'hk_v2_clients': []}, revision=True).status_code, 400)

    def test_database_failure_keeps_old_state_and_revision(self):
        self.save({'hk_v2_clients': [{'id': '1', 'name': 'Kept'}]})
        before = self.get()
        with app.db_conn() as conn:
            conn.execute("CREATE TRIGGER fail_save BEFORE UPDATE ON crm_workspace BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        self.assertEqual(self.save({'hk_v2_clients': []}).status_code, 503)
        self.assertEqual(self.get(), before)

    def test_reset_is_shared_atomic_and_stale_reset_is_rejected(self):
        revision = self.get()['revision']
        self.save({'hk_v2_clients': [{'id': '1', 'name': 'Shared'}]})
        confirmation = {'confirmed_reset': True, 'confirmation': 'RESET DASHBOARD', 'workspace_revision': revision}
        self.assertEqual(self.user_a.post('/api/dashboard/reset', json=confirmation).status_code, 409)
        self.assertEqual(len(self.get()['values']['hk_v2_clients']), 1)
        confirmation['workspace_revision'] = self.get()['revision']
        result = self.user_a.post('/api/dashboard/reset', json=confirmation)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.get(self.user_b)['values']['hk_v2_clients'], [])
        self.assertTrue(self.get()['initialized'])

    def test_identical_save_does_not_bump_revision_and_poll_can_be_conditional(self):
        state = self.save({'hk_v2_clients': []}).json['workspace']
        second = self.save({'hk_v2_clients': []}).json['workspace']
        self.assertEqual(state['revision'], second['revision'])
        response = self.user_b.get('/api/workspace?revision=' + str(state['revision']))
        self.assertTrue(response.json['unchanged'])
        self.assertIn('no-store', response.headers['Cache-Control'])

    def test_cross_origin_and_non_json_writes_are_rejected(self):
        self.assertEqual(self.user_a.post('/api/workspace', json={'revision': 0, 'values': {'hk_v2_clients': []}}).status_code, 403)
        response = self.user_a.post('/api/workspace', json={'revision': 0, 'values': {'hk_v2_clients': []}},
                                    headers={'X-CRM-Request': '1', 'Origin': 'https://external.invalid'})
        self.assertEqual(response.status_code, 403)


if __name__ == '__main__':
    unittest.main()
