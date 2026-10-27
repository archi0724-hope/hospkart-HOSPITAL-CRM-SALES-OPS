"""Named administrator sessions and transaction-bound activity history."""
import hashlib
import json
import re
import secrets
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps

from flask import g, has_request_context, jsonify, request, render_template
from werkzeug.security import check_password_hash, generate_password_hash
from request_security import crm_request_origin_allowed

COOKIE = 'hospkart_admin'
SYSTEM_ACTOR = ContextVar('crm_system_actor', default=None)
READ_POSTS = {'/api/chat', '/api/quotesaarthi/chat', '/api/spreadsheet/export', '/api/drive-import/download'}
TRACKED = {'crm_workspace', 'sheet_connection', 'sheet_source_preferences', 'sheet_leads', 'sheet_queries',
           'shared_drive_links', 'drive_workbook_copies', 'email_followups', 'scheduled_messages', 'message_log'}


def init_schema(conn):
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS crm_admin_users (
        username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS crm_admin_sessions (
        token_hash TEXT PRIMARY KEY, username TEXT NOT NULL, credential_hash TEXT NOT NULL, expires REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS crm_login_attempts (id TEXT PRIMARY KEY, peer TEXT NOT NULL, attempted REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS crm_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, actor TEXT NOT NULL,
        action TEXT NOT NULL, target TEXT NOT NULL, details TEXT NOT NULL, outcome TEXT NOT NULL);
    ''')


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def add_event(conn, actor, action, target, details, outcome='saved'):
    conn.execute('INSERT INTO crm_activity(created_at,actor,action,target,details,outcome) VALUES (?,?,?,?,?,?)',
        (datetime.now(timezone.utc).isoformat(timespec='seconds'), actor, action, target,
         json.dumps(details, ensure_ascii=False), outcome))


def system_task(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        token = SYSTEM_ACTOR.set('System: ' + function.__name__)
        try:
            return function(*args, **kwargs)
        finally:
            SYSTEM_ACTOR.reset(token)
    return wrapped


def record_map(rows):
    return {str(row.get('id', index)): row for index, row in enumerate(rows) if isinstance(row, dict)}


def workspace_changes(before, after):
    result = {}
    for key, value in after.items():
        old = before.get(key)
        if old == value or key == 'hk_v2_segments':
            continue
        if isinstance(value, list) and isinstance(old, list):
            previous, current = record_map(old), record_map(value)
            added, removed = current.keys() - previous.keys(), previous.keys() - current.keys()
            edited = [identifier for identifier in current.keys() & previous.keys() if current[identifier] != previous[identifier]]
            fields = sorted({field for identifier in edited for field in set(current[identifier]) | set(previous[identifier])
                             if current[identifier].get(field) != previous[identifier].get(field)})
            result[key] = {'added': len(added), 'edited': len(edited), 'removed': len(removed),
                           'record_ids': sorted(set(added) | set(removed) | set(edited))[:50], 'fields': fields[:50]}
        elif key == 'hk_v2_invoice_workbook':
            result[key] = {'before_file': old.get('filename') if old else None,
                           'after_file': value.get('filename') if value else None,
                           'before_sheets': [s['name'] for s in (old or {}).get('sheets', [])],
                           'after_sheets': [s['name'] for s in (value or {}).get('sheets', [])]}
        else:
            result[key] = {'changed': True}
    return result


class AuditedConnection:
    def __init__(self, conn, actor, target):
        self.conn, self.actor, self.target = conn, actor, target
        self.events = []

    def __getattr__(self, name):
        return getattr(self.conn, name)

    def execute(self, statement, parameters=None):
        match = re.match(r'\s*(INSERT(?:\s+OR\s+\w+)?\s+INTO|UPDATE|DELETE\s+FROM)\s+(\w+)', statement, re.I)
        table = match[2].lower() if match else None
        before = None
        if table == 'crm_workspace' and statement.lstrip().upper().startswith('UPDATE'):
            row = self.conn.execute('SELECT data FROM crm_workspace WHERE id=1').fetchone()
            before = json.loads(row['data']) if row else {}
        cursor = self.conn.execute(statement) if parameters is None else self.conn.execute(statement, parameters)
        if table in TRACKED and cursor.rowcount > 0:
            details = {'table': table, 'rows': cursor.rowcount}
            if before is not None:
                row = self.conn.execute('SELECT data FROM crm_workspace WHERE id=1').fetchone()
                details['changes'] = workspace_changes(before, json.loads(row['data']))
            action = 'remove' if match[1].upper().startswith('DELETE') else 'upload / add' if match[1].upper().startswith('INSERT') else 'change'
            self.events.append((action, details))
        return cursor

    def executemany(self, statement, parameters):
        for params in parameters:
            self.execute(statement, params)

    def flush(self):
        if self.events:
            add_event(self.conn, self.actor, 'data change', self.target, {'operations': [
                {'action': action, **details} for action, details in self.events]})


def credential(conn, username, shared_hash):
    user = conn.execute('SELECT password_hash,enabled FROM crm_admin_users WHERE username=?', (username,)).fetchone()
    if user:
        return user['password_hash'] if user['enabled'] else ''
    return shared_hash() if username == 'admin' else ''


def resolve_actor(conn, shared_hash):
    token = request.cookies.get(COOKIE, '')
    if not token or len(token) > 200:
        return None
    session = conn.execute('SELECT * FROM crm_admin_sessions WHERE token_hash=? AND expires>?', (digest(token), time.time())).fetchone()
    if not session:
        return None
    current = credential(conn, session['username'], shared_hash)
    if not current or digest(current) != session['credential_hash']:
        return None
    return session['username']


def register(app, db_conn, shared_hash):
    @app.get('/admin')
    def admin_page():
        return render_template('admin_page.html'), 200, {'Cache-Control': 'no-store, private'}

    @app.before_request
    def guard():
        g.admin_actor = None
        if request.path.startswith('/static/') or request.path == '/':
            return
        with db_conn() as conn:
            g.admin_actor = resolve_actor(conn, shared_hash)
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'} and request.path.startswith('/api/'):
            if not crm_request_origin_allowed(request):
                return jsonify(ok=False, error='Use the CRM dashboard on this server.'), 403
            # JSON-only login/logout prevents form-based login CSRF; route guards
            # continue to validate headers/content types on existing endpoints.
            if request.path in {'/api/admin/login', '/api/admin/logout', '/api/admin/remove-import'} or request.path in READ_POSTS or request.path.startswith('/api/quotesaarthi/download/'):
                return
            if not g.admin_actor:
                with db_conn() as conn:
                    add_event(conn, 'Viewer (not signed in)', 'blocked write', request.path, {}, 'denied')
                return jsonify(ok=False, error='Admin sign-in required. Only an administrator can upload, edit or delete shared data.'), 403

    @app.after_request
    def record_upload(response):
        if request.path == '/api/import-excel' and request.method == 'POST' and response.status_code < 400 and getattr(g, 'admin_actor', None):
            uploaded = request.files.get('file')
            filename = (uploaded.filename or '')[:180] if uploaded else ''
            with db_conn() as conn:
                add_event(conn, g.admin_actor, 'upload preview', request.path, {'filename': filename, 'note': 'Parsed for preview; record changes are logged separately when saved.'})
        if request.path.startswith('/api/admin/'):
            response.headers['Cache-Control'] = 'no-store, private'
        return response

    @app.get('/api/admin/session')
    def session_status():
        with db_conn() as conn:
            configured = bool(shared_hash() or conn.execute('SELECT 1 FROM crm_admin_users WHERE enabled=1').fetchone())
        return jsonify(ok=True, admin=bool(g.admin_actor), username=g.admin_actor, configured=configured)

    @app.post('/api/admin/login')
    def login():
        if not request.is_json:
            return jsonify(ok=False, error='Send a JSON login request.'), 400
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(ok=False, error='Enter your administrator username and password.'), 400
        username, password = data.get('username', ''), data.get('password', '')
        if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_.@-]{1,100}', username) or not isinstance(password, str) or len(password) > 1024:
            return jsonify(ok=False, error='Invalid administrator credentials.'), 403
        now, peer = time.time(), request.remote_addr or 'unknown'
        with db_conn() as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('DELETE FROM crm_login_attempts WHERE attempted<?', (now - 60,))
            failures = conn.execute('SELECT COUNT(*) FROM crm_login_attempts WHERE peer=?', (peer,)).fetchone()[0]
            if failures >= 5:
                return jsonify(ok=False, error='Too many failed sign-ins. Try again in one minute.'), 429
            password_hash = credential(conn, username, shared_hash)
            if not password_hash or not check_password_hash(password_hash, password):
                conn.execute('INSERT INTO crm_login_attempts VALUES (?,?,?)', (secrets.token_urlsafe(18), peer, now))
                add_event(conn, 'Unauthenticated', 'sign-in failed', '/api/admin/login', {}, 'denied')
                return jsonify(ok=False, error='Invalid administrator credentials.'), 403
            token = secrets.token_urlsafe(32)
            conn.execute('DELETE FROM crm_admin_sessions WHERE expires<?', (now,))
            conn.execute('INSERT INTO crm_admin_sessions VALUES (?,?,?,?)', (digest(token), username, digest(password_hash), now + 3600))
            add_event(conn, username, 'sign-in', '/api/admin/login', {})
        response = jsonify(ok=True, username=username)
        # HTTPS may terminate at a proxy while preserving the public HTTPS Origin.
        secure = request.is_secure or request.headers.get('Origin', '').startswith('https://')
        response.set_cookie(COOKIE, token, max_age=3600, httponly=True, secure=secure, samesite='Strict', path='/')
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.post('/api/admin/logout')
    def logout():
        if not request.is_json:
            return jsonify(ok=False, error='Send a JSON sign-out request.'), 400
        with db_conn() as conn:
            conn.execute('DELETE FROM crm_admin_sessions WHERE token_hash=?', (digest(request.cookies.get(COOKIE, '')),))
            if g.admin_actor:
                add_event(conn, g.admin_actor, 'sign-out', request.path, {})
        response = jsonify(ok=True)
        response.delete_cookie(COOKIE, path='/')
        return response

    @app.get('/api/admin/activity')
    def activity():
        if not g.admin_actor:
            return jsonify(ok=False, error='Admin sign-in required to view activity history.'), 403
        try:
            before = int(request.args.get('before', '0'))
        except ValueError:
            return jsonify(ok=False, error='Invalid history cursor.'), 400
        with db_conn() as conn:
            rows = conn.execute('SELECT * FROM crm_activity WHERE (?=0 OR id<?) ORDER BY id DESC LIMIT 101', (before, before)).fetchall()
        events = [{**dict(row), 'details': json.loads(row['details'])} for row in rows[:100]]
        response = jsonify(ok=True, events=events, next_before=events[-1]['id'] if len(rows) > 100 else None)
        response.headers['Cache-Control'] = 'no-store, private'
        return response
