"""Validation for shared complaint records in the CRM workspace."""
import re
from datetime import datetime

STATUSES = ('Open', 'In Progress', 'Resolved', 'Closed')
PRIORITIES = ('Low', 'Medium', 'High', 'Urgent')
SCOPES = ('', 'clients', 'leads', 'rghs', 'served', 'doctors', 'potential')


def valid_complaints(rows):
    if not isinstance(rows, list) or len(rows) > 10000:
        return False
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            return False
        identifier = row.get('id')
        if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}', identifier) or identifier in seen:
            return False
        seen.add(identifier)
        for field, limit in (('subject', 200), ('customer_name', 300), ('details', 10000),
                             ('assigned_owner', 200), ('resolution', 10000), ('record_id', 128)):
            value = row.get(field, '')
            if not isinstance(value, str) or len(value) > limit:
                return False
            if field in ('subject', 'customer_name', 'details') and not value.strip():
                return False
        if row.get('status') not in STATUSES or row.get('priority') not in PRIORITIES or row.get('record_scope', '') not in SCOPES:
            return False
        if bool(row.get('record_scope')) != bool(row.get('record_id')):
            return False
        if row['status'] in ('Resolved', 'Closed') and (not row.get('resolution', '').strip() or not row.get('resolved_at')):
            return False
        for field in ('created_at', 'updated_at', 'resolved_at'):
            value = row.get(field, '')
            if not isinstance(value, str) or len(value) > 50 or not value and field != 'resolved_at':
                return False
            if value:
                try:
                    if datetime.fromisoformat(value.replace('Z', '+00:00')).tzinfo is None:
                        return False
                except ValueError:
                    return False
    return True
