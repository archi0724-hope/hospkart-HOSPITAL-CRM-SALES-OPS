"""Copy an immutable SQLite CRM backup into an empty PostgreSQL database.

Preview: python migrate_database.py --source-sqlite backup.db --connection-file private.env
Apply adds --apply. Existing initialized PostgreSQL data is never overwritten.
"""
import argparse
import json
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from dotenv import dotenv_values
os.environ['SCHEDULER_ENABLED'] = 'false'
os.environ['DATABASE_URL'] = ''  # The explicit private connection file selects the target.
import app
import database

TABLES = ('message_log', 'scheduled_messages', 'email_followups', 'crm_workspace',
          'sheet_connection', 'sheet_source_preferences', 'sheet_leads', 'sheet_queries',
          'sheet_previews', 'shared_drive_links', 'drive_workbook_copies')


def migrate(source_path, database_url, apply=False):
    source_path = Path(source_path).resolve()
    if not source_path.is_file(): raise ValueError('Choose an existing SQLite backup.')
    if not database_url: raise ValueError('A private PostgreSQL connection is required.')
    with closing(sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)) as source:
        source.execute('BEGIN')
        available = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'crm_workspace' not in available: raise ValueError('The source is not a CRM SQLite backup.')
        counts = {table: source.execute('SELECT count(*) FROM ' + table).fetchone()[0] if table in available else 0 for table in TABLES}
        if not apply: return {'applied': False, 'source_counts': counts}
        with patch.object(app, 'DATABASE_URL', database_url): app.init_db()
        with database.connect(None, database_url) as target:
            target.execute('BEGIN IMMEDIATE')
            state = target.execute('SELECT initialized FROM crm_workspace WHERE id=1').fetchone()
            if state and state['initialized']: raise ValueError('Target CRM is already initialized. Existing PostgreSQL records were kept.')
            if any(target.execute('SELECT count(*) FROM ' + table).fetchone()[0] for table in TABLES if table != 'crm_workspace'):
                raise ValueError('Target CRM contains saved data/settings. Migration requires an empty destination.')
            for table in TABLES:
                if table not in available: continue
                columns = [row[1] for row in source.execute('PRAGMA table_info(' + table + ')')]
                if not all(re.fullmatch(r'[a-z_][a-z0-9_]*', column) for column in columns):
                    raise ValueError('The backup contains unsupported column names.')
                if table == 'crm_workspace': target.execute('DELETE FROM crm_workspace')
                sql = 'INSERT INTO ' + table + ' (' + ','.join(columns) + ') VALUES (' + ','.join('?' for _ in columns) + ')'
                rows = source.execute('SELECT ' + ','.join(columns) + ' FROM ' + table)
                while batch := rows.fetchmany(100): target.executemany(sql, batch)
                if target.execute('SELECT count(*) FROM ' + table).fetchone()[0] != counts[table]:
                    raise ValueError('Migrated row counts do not match the backup. No partial data was committed.')
            for table in ('message_log', 'scheduled_messages', 'email_followups'):
                target.execute("SELECT setval(pg_get_serial_sequence('" + table + "','id'), GREATEST(COALESCE((SELECT MAX(id) FROM " + table + "),0),1), (SELECT COUNT(*)>0 FROM " + table + '))')
        return {'applied': True, 'source_counts': counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-sqlite', required=True)
    parser.add_argument('--connection-file', required=True, help='Ignored private dotenv file; credentials are never printed.')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    config = dotenv_values(args.connection_file)
    url = config.get('DIRECT_DATABASE_URL') or config.get('DATABASE_URL')
    try: print(json.dumps(migrate(args.source_sqlite, url, args.apply), indent=2))
    except Exception as exc:
        if isinstance(exc, (ValueError, sqlite3.Error)): print('Migration stopped:', str(exc))
        else: print('Migration stopped. Existing source and target data were kept; check database access.')
        raise SystemExit(1) from None


if __name__ == '__main__': main()
