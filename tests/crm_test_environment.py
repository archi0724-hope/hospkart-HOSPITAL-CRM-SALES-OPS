"""Keep tests off a developer's configured production PostgreSQL database."""
import os
import tempfile

_TEST_DATA = tempfile.TemporaryDirectory(prefix="hospkart-tests-")
os.environ["CRM_DATA_DIR"] = _TEST_DATA.name

os.environ['DATABASE_URL'] = ''
os.environ['SCHEDULER_ENABLED'] = 'false'

import app  # noqa: E402


# Legacy business-logic tests run as a provisioned synthetic administrator.
# Authorization tests use a plain FlaskClient to exercise real anonymous/login flows.
import time
import secrets
from flask.testing import FlaskClient
from werkzeug.security import generate_password_hash
import admin_access
from urllib.parse import urlsplit
_TEST_HASH = generate_password_hash('isolated-test-admin-password')


class AdminTestClient(FlaskClient):
    def open(self, *args, **kwargs):
        path = args[0] if args and isinstance(args[0], str) else kwargs.get('path', '')
        if path.startswith('/api/') and not path.startswith('/api/admin/'):
            token = secrets.token_urlsafe(32)
            with app.database.connect(app.DB_PATH, app.DATABASE_URL) as conn:
                conn.execute('INSERT INTO crm_admin_users VALUES (?,?,1) ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash,enabled=1', ('test-admin', _TEST_HASH))
                conn.execute('INSERT INTO crm_admin_sessions VALUES (?,?,?,?)', (admin_access.digest(token), 'test-admin', admin_access.digest(_TEST_HASH), time.time()+3600))
            self.set_cookie(admin_access.COOKIE, token, domain=urlsplit(kwargs.get('base_url', 'http://localhost')).hostname)
        return super().open(*args, **kwargs)


app.app.test_client_class = AdminTestClient


def login_browser_admin(context, address):
    """Real login for isolated browser fixtures; never patch authorization."""
    username = 'browser-test-admin'
    with app.database.connect(app.DB_PATH, app.DATABASE_URL) as conn:
        conn.execute('INSERT INTO crm_admin_users VALUES (?,?,1) ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash,enabled=1', (username, _TEST_HASH))
        # _TEST_HASH is the synthetic backend account hash, so use its password.
    response = context.request.post(address.rstrip('/') + '/api/admin/login', data={
        'username': username, 'password': 'isolated-test-admin-password'})
    assert response.ok, response.text()
