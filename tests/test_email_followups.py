import os
import smtplib
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import app


class EmailFollowupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = patch.object(app, 'DB_PATH', Path(self.temp.name) / 'test.db')
        self.db.start()
        self.addCleanup(self.db.stop)
        self.env = patch.dict(os.environ, {
            'SMTP_HOST': 'smtp.test.invalid', 'SMTP_PORT': '587',
            'SMTP_SECURITY': 'starttls', 'EMAIL_FROM': 'sender@example.com',
            'SMTP_USERNAME': 'sender', 'SMTP_PASSWORD': 'test-secret',
            'EMAIL_AUTOMATION_ENABLED': 'false',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        app.init_db()
        self.client = app.app.test_client()
        self.payload = {
            'confirmed_recipients': True, 'subject': 'Follow-up for {{name}}',
            'message': 'Dear {{contact}}, please review {{product}}.',
            'recipients': [{'name': 'Hospital A', 'email': 'buyer@example.com', 'contact': 'Anu', 'product': 'Monitor'}],
        }

    def history(self):
        return self.client.get('/api/email/followups').json['items']

    def test_bulk_deduplicates_skips_and_personalizes_without_sending(self):
        self.payload['recipients'] += [
            {'email': 'BUYER@example.com'}, {'email': ''}, {'email': 'bad\r\nBcc: hidden@example.com'},
            {'name': 'Hospital B', 'email': 'other@example.com'},
        ]
        with patch.object(app, 'send_email') as send:
            response = self.client.post('/api/email/send', json=self.payload)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json['queued'], 2)
        self.assertEqual(len(response.json['skipped']), 3)
        send.assert_not_called()
        first = next(row for row in self.history() if row['email'] == 'buyer@example.com')
        self.assertEqual(first['subject'], 'Follow-up for Hospital A')
        self.assertEqual(first['message'], 'Dear Anu, please review Monitor.')

    def test_validation_and_missing_sender_do_not_queue(self):
        for change in [{'confirmed_recipients': False}, {'subject': 'Hi\nBcc: other@example.com'}, {'message': ''}, {'recipients': []}, {'recipients': [{'email': 'a..b@example.com'}]}]:
            with self.subTest(change=change):
                self.assertEqual(self.client.post('/api/email/send', json={**self.payload, **change}).status_code, 400)
        with patch.dict(os.environ, {'SMTP_HOST': ''}):
            self.assertEqual(self.client.post('/api/email/send', json=self.payload).status_code, 503)
            self.assertFalse(self.client.get('/api/health').json['email_configured'])
        self.assertEqual(self.history(), [])

    def test_personalized_header_injection_is_rejected(self):
        self.payload['recipients'][0]['name'] = 'Hospital\nBcc: hidden@example.com'
        self.assertEqual(self.client.post('/api/email/send', json=self.payload).status_code, 400)
        self.assertEqual(self.history(), [])

    def test_schedule_time_validation_and_cancellation(self):
        self.payload['scheduled_at'] = (datetime.now(app.IST) - timedelta(days=1)).isoformat()
        self.assertEqual(self.client.post('/api/email/schedule', json=self.payload).status_code, 400)
        self.payload['scheduled_at'] = (datetime.now(app.IST) + timedelta(days=1)).replace(tzinfo=None).isoformat()
        self.assertEqual(self.client.post('/api/email/schedule', json=self.payload).status_code, 202)
        row = self.history()[0]
        self.assertTrue(row['scheduled_at'].endswith('+05:30'))
        with patch.object(app, 'send_email') as send, patch.dict(os.environ, {'EMAIL_AUTOMATION_ENABLED': 'true'}):
            app.process_due_emails()
            send.assert_not_called()
        response = self.client.delete('/api/email/followups/' + str(row['id']))
        self.assertEqual(response.json['updated'], 1)
        self.assertEqual(self.history()[0]['status'], 'cancelled')

    def test_worker_claims_once_and_isolates_recipient_failure(self):
        self.payload['recipients'].append({'name': 'B', 'email': 'other@example.com'})
        self.client.post('/api/email/send', json=self.payload)
        with patch.object(app, 'send_email', side_effect=[smtplib.SMTPAuthenticationError(535, b'test-secret'), '<id@example.com>']) as send:
            app.process_due_emails()
            app.process_due_emails()
            self.assertEqual(send.call_count, 2)
        self.assertEqual({row['status'] for row in self.history()}, {'accepted', 'failed'})
        self.assertNotIn('test-secret', str(self.history()))

    def test_paused_scheduled_jobs_do_not_block_immediate_jobs(self):
        self.client.post('/api/email/send', json=self.payload)
        with app.db_conn() as conn:
            conn.execute("UPDATE email_followups SET mode='scheduled'")
        self.client.post('/api/email/send', json=self.payload)
        with patch.object(app, 'send_email', return_value='<id@example.com>') as send:
            app.process_due_emails()
            self.assertEqual(send.call_count, 1)
            self.assertEqual({row['status'] for row in self.history()}, {'pending', 'accepted'})
            with patch.dict(os.environ, {'EMAIL_AUTOMATION_ENABLED': 'true'}):
                app.process_due_emails()
            self.assertEqual(send.call_count, 2)

    def test_cancelled_and_claimed_jobs_are_not_sent(self):
        self.client.post('/api/email/send', json=self.payload)
        with app.db_conn() as conn:
            conn.execute("UPDATE email_followups SET status='sending'")
        with patch.object(app, 'send_email') as send:
            app.process_due_emails()
            send.assert_not_called()
        row = self.history()[0]
        self.assertEqual(self.client.delete('/api/email/followups/' + str(row['id'])).json['updated'], 0)

    def test_smtp_uses_tls_login_and_separate_recipient(self):
        with patch.object(app.smtplib, 'SMTP') as smtp:
            connection = smtp.return_value.__enter__.return_value
            connection.send_message.return_value = {}
            message_id = app.send_email('buyer@example.com', 'Hello', 'A follow-up')
            connection.starttls.assert_called_once()
            connection.login.assert_called_once_with('sender', 'test-secret')
            message = connection.send_message.call_args.args[0]
            self.assertEqual(message['To'], 'buyer@example.com')
            self.assertIsNone(message['Bcc'])
            self.assertEqual(message['Message-ID'], message_id)
        with patch.dict(os.environ, {'SMTP_SECURITY': 'ssl', 'SMTP_PORT': '465'}), patch.object(app.smtplib, 'SMTP_SSL') as smtp:
            connection = smtp.return_value.__enter__.return_value
            connection.send_message.return_value = {}
            app.send_email('buyer@example.com', 'Hello', 'A follow-up')
            connection.starttls.assert_not_called()
            self.assertIn('context', smtp.call_args.kwargs)

    def test_page_preserves_personalization_placeholders(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'{{name}}', response.data)
        self.assertIn(b'{{contact}}', response.data)
        response = self.client.get('/static/email-followups.js')
        self.assertEqual(response.status_code, 200)
        response.close()


if __name__ == '__main__':
    unittest.main()
