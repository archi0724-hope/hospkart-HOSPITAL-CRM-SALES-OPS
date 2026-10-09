import tempfile
import unittest
from pathlib import Path
from threading import Event, Thread
from unittest.mock import patch

import app


class DashboardResetTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.data_dir = Path(temp.name)
        db = patch.object(app, 'DB_PATH', self.data_dir / 'test.db')
        db.start()
        self.addCleanup(db.stop)
        data_dir = patch.object(app, 'DATA_DIR', self.data_dir)
        data_dir.start()
        self.addCleanup(data_dir.stop)
        (self.data_dir / 'imported_invoice_workbook.json').write_text('{"synthetic": true}', encoding='utf-8')
        app.init_db()
        self.client = app.app.test_client()
        self.confirmation = {'confirmed_reset': True, 'confirmation': 'RESET DASHBOARD'}
        with app.db_conn() as conn:
            for status in ['pending', 'accepted', 'failed', 'cancelled', 'sending']:
                conn.execute("INSERT INTO email_followups(email, client_name, subject, message, scheduled_at, mode, status, created_at) VALUES ('buyer@example.com','Test hospital','Follow-up','Hello',?,'immediate',?,?)", (app.now_iso(), status, app.now_iso()))
            conn.execute("INSERT INTO scheduled_messages(phone, scheduled_at, template_name, created_at) VALUES ('919876543210',?,'followup',?)", (app.now_iso(), app.now_iso()))
            conn.execute("INSERT INTO message_log(direction, channel, message, created_at) VALUES ('outbound','whatsapp','Test history',?)", (app.now_iso(),))

    def counts(self):
        with app.db_conn() as conn:
            return {table: conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ['email_followups', 'scheduled_messages', 'message_log']}

    def test_confirmation_required_and_wrong_inputs_preserve_history(self):
        initial = self.counts()
        for payload in [None, [], {}, {'confirmed_reset': True}, {'confirmed_reset': False, 'confirmation': 'RESET DASHBOARD'}, {'confirmed_reset': True, 'confirmation': 'reset dashboard'}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post('/api/dashboard/reset', json=payload).status_code, 400)
                self.assertEqual(self.counts(), initial)
                self.assertTrue((self.data_dir / 'imported_invoice_workbook.json').exists())

    def test_confirmed_reset_clears_all_history_and_pending_jobs(self):
        response = self.client.post('/api/dashboard/reset', json=self.confirmation)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['provided_workbook_removed'])
        self.assertFalse((self.data_dir / 'imported_invoice_workbook.json').exists())
        self.assertEqual(response.json['cleared'], {'email_followups': 5, 'scheduled_messages': 1, 'message_log': 1})
        self.assertEqual(self.counts(), {'email_followups': 0, 'scheduled_messages': 0, 'message_log': 0})
        self.assertEqual(self.client.get('/api/email/followups').json['items'], [])
        self.assertEqual(self.client.get('/api/whatsapp/scheduled').json['items'], [])
        self.assertEqual(self.client.get('/api/messages').json['items'], [])
        with patch.object(app, 'send_email') as send, patch.object(app, 'email_configured', return_value=True):
            app.process_due_emails()
            send.assert_not_called()
        repeated = self.client.post('/api/dashboard/reset', json=self.confirmation).json
        self.assertFalse(repeated['provided_workbook_removed'])
        self.assertEqual(repeated['cleared'], {'email_followups': 0, 'scheduled_messages': 0, 'message_log': 0})
        self.assertEqual(self.client.get('/api/invoice-workbook').status_code, 404)

    def test_busy_followup_activity_preserves_history_until_finished(self):
        entered, release = Event(), Event()
        def hold_lock():
            with app.messaging_lock:
                entered.set()
                release.wait(timeout=5)
        worker = Thread(target=hold_lock)
        worker.start()
        self.assertTrue(entered.wait(timeout=2))
        initial = self.counts()
        try:
            response = self.client.post('/api/dashboard/reset', json=self.confirmation)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(self.counts(), initial)
            self.assertTrue((self.data_dir / 'imported_invoice_workbook.json').exists())
        finally:
            release.set()
            worker.join(timeout=2)
        response = self.client.post('/api/dashboard/reset', json=self.confirmation)
        self.assertEqual(response.status_code, 200)
        self.assertFalse((self.data_dir / 'imported_invoice_workbook.json').exists())


if __name__ == '__main__':
    unittest.main()
