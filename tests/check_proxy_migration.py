"""HTTPS browser -> TLS proxy -> HTTP Waitress migration regression.

All certificates, browser data and database records are temporary and synthetic.
"""
import ipaddress
import json
import os
import ssl
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from playwright.sync_api import sync_playwright
from waitress import create_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crm_test_environment import app


def certificate(root):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
            .sign(key, hashes.SHA256()))
    cert_file, key_file = root / 'test-cert.pem', root / 'test-key.pem'
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return cert_file, key_file


def check():
    reports = []
    with tempfile.TemporaryDirectory() as temp, patch.object(app, 'DB_PATH', Path(temp) / 'db.sqlite'), patch.object(app, 'DATA_DIR', Path(temp)):
        app.init_db()
        if app.scheduler.running: app.scheduler.pause()
        backend = create_server(app.app, host='127.0.0.1', port=0)
        Thread(target=backend.run, daemon=True).start()

        class Proxy(BaseHTTPRequestHandler):
            def log_message(self, *_): pass

            def forward(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                headers = {key: value for key, value in self.headers.items() if key.lower() not in ('connection', 'content-length')}
                response = requests.request(self.command, f'http://127.0.0.1:{backend.effective_port}' + self.path,
                                            headers=headers, data=body, timeout=20, allow_redirects=False)
                self.send_response(response.status_code)
                for key, value in response.headers.items():
                    if key.lower() not in ('connection', 'transfer-encoding', 'content-encoding', 'content-length'):
                        self.send_header(key, value)
                self.send_header('Content-Length', str(len(response.content)))
                self.end_headers()
                try: self.wfile.write(response.content)
                except (BrokenPipeError, ConnectionResetError, ssl.SSLError): pass

            do_GET = do_POST = forward

        cert, key = certificate(Path(temp)); context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)

        class HttpsServer(ThreadingHTTPServer):
            def get_request(self):
                connection, address = super().get_request()
                return context.wrap_socket(connection, server_side=True, do_handshake_on_connect=False), address

            def handle_error(self, connection, address):
                if isinstance(sys.exception(), (ssl.SSLError, ConnectionResetError, BrokenPipeError)):
                    return  # Browser certificate probes can close before sending HTTP.
                super().handle_error(connection, address)

        proxy = HttpsServer(('127.0.0.1', 0), Proxy)
        Thread(target=proxy.serve_forever, daemon=True).start()
        address = f'https://127.0.0.1:{proxy.server_port}/'
        try:
            with sync_playwright() as p:
                for channel in os.getenv('BROWSER_CHANNELS', 'chrome,msedge').split(','):
                    with app.db_conn() as conn: conn.execute('DELETE FROM crm_workspace')
                    app.init_db()
                    browser = p.chromium.launch(channel=None if channel == 'chromium' else channel, headless=True)
                    owner = browser.new_context(ignore_https_errors=True)
                    owner.add_init_script("if(!sessionStorage.getItem('seeded')){localStorage.setItem('hk_v2_clients',JSON.stringify([{id:'0001',name:'Preserved HTTPS Hospital',status:'New Lead',city:'Test',next:'',quote:0,order:0,remark:''}]));sessionStorage.setItem('seeded','1')}")
                    page = owner.new_page(); errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(address); page.wait_for_function('dashboardReady&&!document.body.inert')
                    assert page.evaluate('clients[0].name') == 'Preserved HTTPS Hospital'
                    assert page.locator('#sharedRecoveryNotice').is_hidden()
                    assert page.evaluate('browserWorkspaceRecovery.visible') is False
                    assert 'connected' in page.locator('#sharedDatabaseStatus').inner_text()
                    page.reload(); page.wait_for_function('dashboardReady&&!document.body.inert')
                    assert page.locator('#sharedRecoveryNotice').is_hidden()
                    peer = browser.new_context(ignore_https_errors=True); other = peer.new_page()
                    other.goto(address); other.wait_for_function('dashboardReady&&!document.body.inert')
                    assert other.evaluate('clients[0].id') == '0001'
                    peer.close(); owner.close()

                    # A rejected migration must not be mislabeled as a database outage.
                    with app.db_conn() as conn: conn.execute('DELETE FROM crm_workspace')
                    app.init_db()
                    blocked = browser.new_context(ignore_https_errors=True, accept_downloads=True)
                    blocked.add_init_script("localStorage.setItem('hk_v2_clients',JSON.stringify([{id:'kept',name:'Never Lost',status:'New Lead',quote:0,order:0,next:'',remark:''}]))")
                    page = blocked.new_page()
                    page.route('**/api/workspace', lambda route: route.fulfill(status=403, content_type='application/json',
                        body=json.dumps({'ok': False, 'error': 'Use the CRM dashboard on this server to save shared records.'})) if route.request.method == 'POST' else route.continue_())
                    page.goto(address); page.wait_for_function('!document.body.inert')
                    assert 'not permitted to save' in page.locator('#sharedDatabaseStatus').inner_text()
                    assert 'could not be reached' not in page.locator('#browserStorageNotice').inner_text()
                    assert page.locator('#sharedRecoveryNotice').is_visible()
                    assert page.evaluate('clients[0].name') == 'Never Lost'
                    blocked.close(); browser.close()
                    assert not errors, errors
                    reports.append({'browser': channel, 'https_to_http_migration': True, 'other_user_sees_migrated_records': True,
                                    'successful_migration_warning_hidden': True, 'recovery_copy_retained': True,
                                    'rejected_save_message_accurate': True, 'javascript_errors': errors})
        finally:
            proxy.shutdown(); proxy.server_close(); backend.close()
    print(json.dumps(reports, indent=2))


if __name__ == '__main__': check()
