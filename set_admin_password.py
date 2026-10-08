"""Configure the local dashboard's admin removal password without exposing it."""
from getpass import getpass
from pathlib import Path
import os

from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv


def main():
    base = Path(__file__).resolve().parent
    load_dotenv(base / '.env')
    path = Path(os.getenv('CRM_DATA_DIR', str(base / 'data'))).expanduser().resolve() / 'admin_password.hash'
    if path.exists():
        current = getpass('Current admin password: ')
        if not check_password_hash(path.read_text(encoding='utf-8').strip(), current):
            raise SystemExit('Incorrect password. The admin password was not changed.')
    password = getpass('New admin password (at least 12 characters): ')
    if len(password) < 12:
        raise SystemExit('Use at least 12 characters. No changes were made.')
    if password != getpass('Confirm new admin password: '):
        raise SystemExit('Passwords do not match. No changes were made.')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_password_hash(password), encoding='utf-8')
    print('Admin password configured. Use Remove in Data & backups. No restart needed.')


if __name__ == '__main__':
    main()
