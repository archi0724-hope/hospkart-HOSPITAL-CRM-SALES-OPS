"""Shared CRM workspace stored transactionally in the existing SQLite database.

The browser keeps only a recovery/cache copy. Revisions prevent stale clients
from replacing newer uploads, edits, or spreadsheet imports.
"""
import json
import secrets
import sqlite3
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

SECTIONS = ('rghs', 'leads', 'served', 'doctors', 'potential')
MAX_REQUEST = 64 * 1024 * 1024


def empty_values():
    return {
        'hk_v2_clients': [], 'hk_v2_calls': [], 'hk_v2_feedback': [],
        'hk_v2_segments': {'served': [], 'doctors': [], 'potential': []},
        **{'hk_v2_' + section: [] for section in SECTIONS},
        'hk_v2_invoice_workbook': None, 'hk_v2_backups': [],
        'hk_v2_reset_revision': '',
    }


class WorkspaceError(ValueError):
    def __init__(self, message, status=400, workspace=None):
        super().__init__(message)
        self.status, self.workspace = status, workspace


def init_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS crm_workspace (
        id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL,
        initialized INTEGER NOT NULL, data TEXT NOT NULL, updated_at TEXT
    )''')
    conn.execute('INSERT OR IGNORE INTO crm_workspace(id,revision,initialized,data) VALUES(1,0,0,?)',
                 (json.dumps(empty_values()),))


def read(conn):
    row = conn.execute('SELECT * FROM crm_workspace WHERE id=1').fetchone()
    return {'revision': row['revision'], 'initialized': bool(row['initialized']),
            'values': json.loads(row['data']), 'updated_at': row['updated_at']}


def record_array(value, named=False):
    return isinstance(value, list) and all(isinstance(row, dict) and
        (not named or isinstance(row.get('id'), str) and isinstance(row.get('name'), str)) for row in value)


def valid_workbook(value):
    return value is None or (isinstance(value, dict) and isinstance(value.get('sheets'), list) and
        all(isinstance(sheet, dict) and isinstance(sheet.get('name'), str) and record_array(sheet.get('rows'))
            for sheet in value['sheets']) and
        len({sheet['name'] for sheet in value['sheets']}) == len(value['sheets']))


def validate_patch(values):
    allowed = empty_values()
    if not isinstance(values, dict) or not values or any(key not in allowed for key in values):
        raise WorkspaceError('Provide recognized CRM workspace fields to save.')
    for key, value in values.items():
        if key == 'hk_v2_invoice_workbook':
            valid = valid_workbook(value)
        elif key == 'hk_v2_reset_revision':
            valid = isinstance(value, str) and len(value) <= 128
        elif key == 'hk_v2_segments':
            valid = isinstance(value, dict) and set(value) <= {'served', 'doctors', 'potential'} and all(record_array(rows, True) for rows in value.values())
        elif key == 'hk_v2_backups':
            valid = record_array(value) and len(value) <= 10 and all(
                record_array(item.get('clients'), True) and record_array(item.get('calls')) and
                record_array(item.get('feedback')) and valid_workbook(item.get('invoiceWorkbook')) and
                (item.get('sections') is None or isinstance(item['sections'], dict) and
                 all(record_array(item['sections'].get(section, []), True) for section in SECTIONS)) and
                (item.get('segments') is None or isinstance(item['segments'], dict) and
                 all(record_array(item['segments'].get(section, []), True) for section in ('served', 'doctors', 'potential')))
                for item in value)
        else:
            valid = record_array(value, key not in ('hk_v2_calls', 'hk_v2_feedback'))
        if not valid:
            raise WorkspaceError('Invalid saved data in ' + key + '. No records were changed.')
    try:
        json.dumps(values, allow_nan=False)
    except (ValueError, TypeError):
        raise WorkspaceError('The CRM data contains unsupported values. No records were changed.') from None


def write(conn, current, values, *, initialized=True):
    patch = dict(values)
    # Keep the legacy section aliases consistent with their independent stores.
    segments = {**current['values']['hk_v2_segments'], **patch.get('hk_v2_segments', {})}
    for section in ('served', 'doctors', 'potential'):
        key = 'hk_v2_' + section
        if key in patch:
            if section in patch.get('hk_v2_segments', {}) and patch[key] != patch['hk_v2_segments'][section]:
                raise WorkspaceError('The imported section does not match its saved workspace data.')
            segments[section] = patch[key]
        elif section in patch.get('hk_v2_segments', {}):
            patch[key] = segments[section]
    patch['hk_v2_segments'] = segments
    merged = {**current['values'], **patch}
    if merged != current['values'] or initialized != current['initialized']:
        now = datetime.now(timezone.utc).isoformat(timespec='seconds')
        conn.execute('UPDATE crm_workspace SET data=?,revision=revision+1,initialized=?,updated_at=? WHERE id=1',
                     (json.dumps(merged, ensure_ascii=False, allow_nan=False), int(initialized), now))
    return read(conn)


def save(conn, values, expected_revision, initialize_only=False):
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
        raise WorkspaceError('A current workspace revision is required.')
    validate_patch(values)
    conn.execute('BEGIN IMMEDIATE')
    current = read(conn)
    if expected_revision != current['revision'] or initialize_only and current['initialized']:
        raise WorkspaceError('Another user saved newer CRM data. Your changes were not applied. Review the refreshed records and retry; your unsaved copy is available to download.', 409, current)
    return write(conn, current, values)


def reset(conn, expected_revision=None):
    current = read(conn)
    if expected_revision is not None and (isinstance(expected_revision, bool) or not isinstance(expected_revision, int)):
        raise WorkspaceError('A valid shared workspace revision is required.')
    if expected_revision is not None and expected_revision != current['revision']:
        raise WorkspaceError('The shared dashboard changed. Review the latest records before resetting.', 409, current)
    values = empty_values()
    values['hk_v2_reset_revision'] = secrets.token_urlsafe(16)
    return write(conn, current, values)


def merge_sheet_leads(conn, incoming):
    """Called inside the sheet import transaction so every browser sees one result."""
    if not incoming:
        return
    current = read(conn)
    leads = current['values']['hk_v2_leads']
    positions = {row['id']: index for index, row in enumerate(leads)}
    defaults = dict(type='New Prospect', city='', district='', state='', contact='', mobile='', email='',
                    requirement='', product='', quote=0, order=0, last='', next='', executive='Unassigned',
                    remark='', priority='Medium')
    for row in incoming:
        index = positions.get(row['id'])
        if index is None:
            positions[row['id']] = len(leads)
            leads.append({**defaults, **row})
        else:
            leads[index] = {**leads[index], **row}
    # read again because current['values'] was modified to build the next lead list.
    write(conn, read(conn), {'hk_v2_leads': leads})


def register(app, db_conn):
    routes = Blueprint('shared_workspace', __name__, url_prefix='/api/workspace')

    @routes.before_request
    def check_request():
        if request.method == 'POST':
            if (request.headers.get('Origin') and request.headers['Origin'].rstrip('/') != request.host_url.rstrip('/')) or request.headers.get('Sec-Fetch-Site') == 'cross-site':
                raise WorkspaceError('Use the CRM dashboard on this server to save shared records.', 403)
            if not request.is_json or request.headers.get('X-CRM-Request') != '1':
                raise WorkspaceError('Send a JSON request from the CRM dashboard.', 403)
            if request.content_length and request.content_length > MAX_REQUEST:
                raise WorkspaceError('This save exceeds 64 MB. Use a smaller import or fewer saved checkpoints.', 413)

    @routes.after_request
    def private_response(response):
        response.headers['Cache-Control'] = 'no-store, private'
        return response

    @routes.errorhandler(WorkspaceError)
    def error_response(error):
        return jsonify(ok=False, error=str(error), workspace=error.workspace), error.status

    @routes.errorhandler(sqlite3.Error)
    def database_error(error):
        return jsonify(ok=False, error='The shared database could not save this operation. The last saved records are retained. Check disk space and database access, then retry.'), 503

    @routes.get('')
    def get_workspace():
        with db_conn() as conn:
            version = conn.execute('SELECT revision,initialized FROM crm_workspace WHERE id=1').fetchone()
            if request.args.get('revision') == str(version['revision']):
                return jsonify(ok=True, unchanged=True, revision=version['revision'], initialized=bool(version['initialized']))
            current = read(conn)
        return jsonify(ok=True, workspace=current)

    @routes.post('')
    def save_workspace():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise WorkspaceError('Provide a CRM workspace save request.')
        if not isinstance(body.get('initialize_only', False), bool):
            raise WorkspaceError('Invalid migration request.')
        with db_conn() as conn:
            current = save(conn, body.get('values'), body.get('revision'), body.get('initialize_only', False))
        return jsonify(ok=True, workspace=current)

    app.register_blueprint(routes)
    app.register_error_handler(WorkspaceError, error_response)
