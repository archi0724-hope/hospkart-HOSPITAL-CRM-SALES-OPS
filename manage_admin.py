"""Provision named administrators locally; no public user-management endpoint."""
import argparse
from getpass import getpass
import os
import re


def main():
    parser = argparse.ArgumentParser(description='Create/update or disable a named CRM administrator.')
    parser.add_argument('username')
    parser.add_argument('--disable', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.@-]{1,100}', args.username) or args.username == 'admin':
        parser.error('Use a personal username with letters, numbers, dots, @, hyphens or underscores. The shared name admin is reserved.')
    password_hash = None
    if not args.disable:
        password = getpass('New admin password (at least 12 characters): ')
        if len(password) < 12 or password != getpass('Confirm password: '):
            raise SystemExit('Passwords must match and have at least 12 characters. Nothing changed.')
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash(password)
    os.environ['SCHEDULER_ENABLED'] = 'false'
    import app
    import admin_access
    with app.db_conn() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if args.disable:
            conn.execute('UPDATE crm_admin_users SET enabled=0 WHERE username=?', (args.username,))
        else:
            conn.execute('INSERT INTO crm_admin_users(username,password_hash,enabled) VALUES (?,?,1) ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash,enabled=1', (args.username, password_hash))
        conn.execute('DELETE FROM crm_admin_sessions WHERE username=?', (args.username,))
        admin_access.add_event(conn, 'Server owner (CLI)', 'disable admin' if args.disable else 'configure admin', args.username, {})
    print('Admin account updated; previous sessions revoked. No restart needed.')


if __name__ == '__main__':
    main()
