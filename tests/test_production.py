import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from threading import Thread
import os

import requests
from waitress import create_server
from werkzeug.security import generate_password_hash
from production import server_options

import app


class ProductionTests(unittest.TestCase):
    def test_all_versioned_assets_exist_and_are_served(self):
        client=app.app.test_client()
        html=client.get('/').get_data(as_text=True)
        urls=re.findall(r'(?:src|href)="(/static/[^\"]+)"',html)
        self.assertTrue(urls)
        for url in urls:
            with self.subTest(url=url):
                self.assertIn('?v=',url)
                with client.get(url) as response:
                    self.assertEqual(response.status_code,200)

    def test_no_private_workbook_is_required_to_start(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(app,'DATA_DIR',Path(temp)):
            client=app.app.test_client()
            self.assertEqual(client.get('/').status_code,200)
            self.assertEqual(client.get('/api/health').status_code,200)
            self.assertEqual(client.get('/api/invoice-workbook').status_code,404)

    def test_database_initialization_uses_wal(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(app,'DB_PATH',Path(temp)/'crm.db'):
            app.init_db()
            with app.db_conn() as connection:
                self.assertEqual(connection.execute('PRAGMA journal_mode').fetchone()[0],'wal')

    def check_proxy(self,trusted):
        with patch.dict(os.environ,{'TRUSTED_PROXY':'127.0.0.1' if trusted else '','TRUSTED_PROXY_COUNT':'1'}):
            options=server_options()
        options.update(host='127.0.0.1',port=0)
        server=create_server(app.app,**options)
        Thread(target=server.run,daemon=True).start()
        try:
            with patch.object(app,'admin_password_hash',return_value=generate_password_hash('proxy-test-password')):
                return requests.post(f'http://127.0.0.1:{server.effective_port}/api/admin/remove-import',json={'password':'proxy-test-password','scope':'worksheet','name':'Read Me','confirmation':'REMOVE Read Me'},headers={'Origin':'https://crm.example.test','X-Forwarded-Proto':'https','X-Forwarded-Host':'crm.example.test'},timeout=5).status_code
        finally:
            server.close()

    def test_https_origin_works_behind_configured_proxy(self):
        self.assertEqual(self.check_proxy(True),200)

    def test_untrusted_forwarded_headers_cannot_bypass_origin_check(self):
        self.assertEqual(self.check_proxy(False),403)


if __name__=='__main__':unittest.main()
