import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crm_test_environment import app


def complaint():
    return {'id': 'CMP-test-001', 'customer_name': 'Test Hospital', 'subject': 'Delivery follow-up',
            'details': 'One item needs replacement.', 'record_scope': 'leads', 'record_id': '0001',
            'assigned_owner': 'Test owner', 'priority': 'High', 'status': 'Open', 'resolution': '',
            'created_at': '2026-10-23T10:00:00+00:00', 'updated_at': '2026-10-23T10:00:00+00:00', 'resolved_at': ''}


class ComplaintTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        db = patch.object(app, 'DB_PATH', Path(self.temp.name) / 'test.db')
        db.start(); self.addCleanup(db.stop)
        app.init_db(); self.client = app.app.test_client()

    def state(self):
        return self.client.get('/api/workspace').json['workspace']

    def save(self, rows, revision=None):
        return self.client.post('/api/workspace', json={'revision': self.state()['revision'] if revision is None else revision,
            'values': {'hk_v2_complaints': rows}}, headers={'X-CRM-Request': '1'})

    def test_create_is_shared_and_survives_database_reinitialization(self):
        row = complaint()
        self.assertEqual(self.save([row]).status_code, 200)
        other = app.app.test_client()
        self.assertEqual(other.get('/api/workspace').json['workspace']['values']['hk_v2_complaints'], [row])
        app.init_db()
        self.assertEqual(self.state()['values']['hk_v2_complaints'], [row])

    def test_resolution_requires_notes_and_timestamp_on_server(self):
        row = complaint(); self.save([row])
        for status in ('Resolved', 'Closed'):
            bad = {**row, 'status': status}
            self.assertEqual(self.save([bad]).status_code, 400)
            self.assertEqual(self.save([{**bad, 'resolution': 'Replaced item'}]).status_code, 400)
        self.assertEqual(self.state()['values']['hk_v2_complaints'][0]['status'], 'Open')

    def test_progress_resolution_closure_and_reopening_keep_same_id(self):
        row = complaint(); self.save([row])
        row.update(status='In Progress', assigned_owner='Service team')
        self.assertEqual(self.save([row]).status_code, 200)
        row.update(status='Resolved', resolution='Replacement delivered.', resolved_at='2026-10-23T11:00:00+00:00')
        self.assertEqual(self.save([row]).status_code, 200)
        row['status'] = 'Closed'; self.assertEqual(self.save([row]).status_code, 200)
        row.update(status='Open', resolved_at=''); self.assertEqual(self.save([row]).status_code, 200)
        saved = self.state()['values']['hk_v2_complaints']
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]['id'], 'CMP-test-001')
        self.assertEqual(saved[0]['resolution'], 'Replacement delivered.')

    def test_invalid_complaints_never_replace_valid_saved_records(self):
        row = complaint(); self.save([row]); before = self.state()
        for changes in ({'subject': ' '}, {'details': ''}, {'customer_name': ''}, {'priority': 'Invalid'},
                        {'status': 'Invalid'}, {'created_at': 'yesterday'}, {'updated_at': '2026-10-23'},
                        {'record_scope': '', 'record_id': 'orphan'}, {'assigned_owner': 123}):
            with self.subTest(changes=changes):
                self.assertEqual(self.save([{**row, **changes}]).status_code, 400)
                self.assertEqual(self.state(), before)
        self.assertEqual(self.save([row, copy.deepcopy(row)]).status_code, 400)

    def test_old_workspace_without_complaints_key_remains_readable(self):
        with app.db_conn() as conn:
            state = self.state()['values']; del state['hk_v2_complaints']
            state['hk_v2_clients'] = [{'id': 'kept', 'name': 'Kept Hospital'}]
            conn.execute('UPDATE crm_workspace SET data=? WHERE id=1', (json.dumps(state),))
        self.assertEqual(self.state()['values']['hk_v2_complaints'], [])
        self.save([complaint()])
        self.assertEqual(self.state()['values']['hk_v2_clients'][0]['id'], 'kept')

    def test_complaints_are_validated_in_backups_and_cleared_on_reset(self):
        row = complaint(); self.save([row])
        backup = {'id': 'backup', 'clients': [], 'calls': [], 'feedback': [], 'complaints': [row]}
        result = self.client.post('/api/workspace', json={'revision': self.state()['revision'], 'values': {'hk_v2_backups': [backup]}}, headers={'X-CRM-Request': '1'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.state()['values']['hk_v2_backups'][0]['complaints'], [row])
        result = self.client.post('/api/dashboard/reset', json={'confirmed_reset': True, 'confirmation': 'RESET DASHBOARD', 'workspace_revision': self.state()['revision']})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.state()['values']['hk_v2_complaints'], [])

    def test_stale_complaint_edit_cannot_overwrite_another_users_resolution(self):
        row = complaint(); self.save([row]); old_revision = self.state()['revision']
        resolved = {**row, 'status': 'Resolved', 'resolution': 'Replacement delivered', 'resolved_at': '2026-10-23T11:00:00+00:00'}
        self.save([resolved])
        self.assertEqual(self.save([{**row, 'subject': 'Stale edit'}], old_revision).status_code, 409)
        self.assertEqual(self.state()['values']['hk_v2_complaints'][0]['status'], 'Resolved')


if __name__ == '__main__': unittest.main()
