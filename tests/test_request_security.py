"""Public-origin validation through actual Flask request contexts and routes."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from request_security import crm_request_origin_allowed


class RequestOriginTests(unittest.TestCase):
    def allowed(self, origin, base='http://crm.example.test', **headers):
        if origin is not None:
            headers['Origin'] = origin
        with app.app.test_request_context('/api/workspace', base_url=base, headers=headers):
            from flask import request
            return crm_request_origin_allowed(request)

    def test_direct_localhost_and_loopback_requests(self):
        for host in ('localhost', '127.0.0.1', '[::1]'):
            address = 'http://' + host + ':5000'
            self.assertTrue(self.allowed(address, address))

    def test_preserved_public_host_works_with_https_termination(self):
        self.assertTrue(self.allowed('https://crm.example.test'))
        self.assertTrue(self.allowed('https://crm.example.test:443'))
        self.assertTrue(self.allowed('https://CRM.EXAMPLE.TEST', 'http://crm.example.test:443'))
        self.assertTrue(self.allowed('https://crm.example.test:8443', 'http://crm.example.test:8443'))

    def test_default_http_port_is_normalized(self):
        self.assertTrue(self.allowed('http://crm.example.test:80'))

    def test_wrong_hosts_ports_and_https_downgrade_remain_rejected(self):
        for origin, base in (
            ('https://attacker.example.test', 'http://crm.example.test'),
            ('https://crm.example.test:8443', 'http://crm.example.test'),
            ('http://crm.example.test', 'https://crm.example.test'),
            ('http://localhost:5000', 'http://127.0.0.1:5000'),
        ):
            with self.subTest(origin=origin, base=base):
                self.assertFalse(self.allowed(origin, base))

    def test_malformed_null_and_non_origin_values_are_rejected(self):
        for origin in ('null', 'file://', 'https://user@crm.example.test', 'https://crm.example.test/path',
                       'https://crm.example.test?query=1', 'https://crm.example.test#fragment',
                       'https://crm.example.test:bad', 'https://[broken'):
            with self.subTest(origin=origin):
                self.assertFalse(self.allowed(origin))

    def test_cross_site_signal_and_untrusted_forwarded_host_are_not_bypassed(self):
        self.assertFalse(self.allowed('https://crm.example.test', **{'Sec-Fetch-Site': 'cross-site'}))
        self.assertFalse(self.allowed('https://attacker.example.test', **{'X-Forwarded-Host': 'attacker.example.test', 'X-Forwarded-Proto': 'https'}))

    def test_actual_shared_migration_accepts_tls_proxy_but_blocks_other_sites(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(app, 'DB_PATH', Path(temp) / 'test.db'):
            app.init_db(); client = app.app.test_client()
            body = {'revision': 0, 'initialize_only': True,
                    'values': {'hk_v2_clients': [{'id': '0001', 'name': 'Preserved Hospital'}]}}
            result = client.post('/api/workspace', base_url='http://crm.example.test', json=body,
                                 headers={'Origin': 'https://crm.example.test', 'X-CRM-Request': '1'})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json['workspace']['values']['hk_v2_clients'][0]['id'], '0001')
            result = client.post('/api/workspace', base_url='http://crm.example.test', json=body,
                                 headers={'Origin': 'https://attacker.example.test', 'X-CRM-Request': '1'})
            self.assertEqual(result.status_code, 403)
            self.assertEqual(client.get('/api/workspace').json['workspace']['revision'], 1)


if __name__ == '__main__':
    unittest.main()
