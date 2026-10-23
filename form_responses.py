"""Convert read-only Google Form response rows into stable CRM entities."""
import hashlib
import re
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FIELDS = [
    ('response_id', 'Response ID (optional)'), ('timestamp', 'Submission timestamp'),
    ('submission_type', 'Type of submission'), ('name', 'Customer full name'),
    ('company', 'Hospital or organization'), ('mobile', 'Customer phone'),
    ('email', 'Customer email'), ('executive', 'Lead generator / owner'),
    ('created_date', 'Date of lead generation'), ('product', 'Products or services'),
    ('details', 'Lead or query details'), ('priority', 'Urgency level'),
]
REQUIRED = ('timestamp', 'submission_type', 'name', 'details')
LEAD_TYPES = ('New Sales Lead', 'New Lead')
QUERY_TYPES = ('Product Inquiry', 'Customer Query', 'Existing Customer Query', 'Query', 'Service Inquiry', 'Service Request')


def parse_date(value, locale, timezone_name, date_only=False):
    if not value:
        return ''
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        pattern = '%m/%d/%Y' if locale == 'en_US' else '%d/%m/%Y'
        parsed = None
        for suffix in (' %H:%M:%S', ' %H:%M', ' %I:%M:%S %p', ' %I:%M %p', ''):
            try:
                parsed = datetime.strptime(value, pattern + suffix)
                break
            except ValueError:
                continue
        if parsed is None:
            raise ValueError('Invalid response date. Use an ISO date or the spreadsheet locale date format.')
    if date_only:
        return parsed.date().isoformat()
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=ZoneInfo(timezone_name))).isoformat()


def convert(rows, settings, validate_rows, sheet_error):
    headers = [str(value).strip() for value in (rows[0] if rows else [])]
    mapping = settings.get('response_mapping')
    if not isinstance(mapping, dict) or any(key not in dict(FIELDS) or not isinstance(value, str) for key, value in mapping.items()):
        raise sheet_error('Invalid form response column mapping.')
    if any(not mapping.get(field) for field in REQUIRED):
        raise sheet_error('Map submission timestamp, type, customer name and details before importing form responses.')
    used = [value for value in mapping.values() if value]
    if len(used) != len(set(used)):
        raise sheet_error('Map each form response column to only one field.')
    for value in used:
        if headers.count(value) != 1:
            raise sheet_error('Missing or duplicate column: ' + value + '. Update the response mapping.')
    if len(rows) > 20001 or len(headers) > 200:
        raise sheet_error('Response worksheet exceeds 20,000 rows or 200 columns.')
    locale, timezone_name = settings.get('source_locale', 'en_US'), settings.get('source_timezone', 'Asia/Kolkata')
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise sheet_error('Unsupported spreadsheet time zone.') from None
    mapped = {key: headers.index(value) for key, value in mapping.items() if value}
    prepared, errors, warnings = [], [], []
    duplicates = Counter()
    for number, row in enumerate(rows[1:], 2):
        if not any(str(value).strip() for value in row):
            continue
        data = {key: str(row[index]).strip() if index < len(row) and row[index] is not None else '' for key, index in mapped.items()}
        try:
            if any(len(value) > 10000 for value in data.values()):
                raise ValueError('A cell exceeds 10,000 characters.')
            if not data.get('timestamp'):
                raise ValueError('Missing submission timestamp, type, customer name or details.')
            timestamp = parse_date(data['timestamp'], locale, timezone_name)
            identity = data.get('response_id') if mapping.get('response_id') else timestamp
            if not identity:
                raise ValueError('Missing stable Response ID.')
            digest = hashlib.sha256((settings['id'] + '\0' + settings['response_tab'] + '\0' + identity).encode()).hexdigest()
            duplicates[digest] += 1
            if any(not data.get(key) for key in REQUIRED):
                raise ValueError('Missing submission timestamp, type, customer name or details.')
            if data.get('submission_type') not in LEAD_TYPES + QUERY_TYPES:
                raise ValueError('Unsupported submission type: ' + data['submission_type'] + '. Review the response before importing.')
            prepared.append((number, data, timestamp, digest))
        except ValueError as exc:
            errors.append({'kind': 'leads', 'row': number, 'id': '', 'reason': str(exc)})
    result = {'leads': [], 'queries': []}
    for number, data, timestamp, digest in prepared:
        identifier = 'FORM-L:' + digest
        query = data['submission_type'] in QUERY_TYPES
        if duplicates[digest] > 1:
            for kind in (('leads', 'queries') if query else ('leads',)):
                errors.append({'kind': kind, 'row': number, 'id': identifier, 'reason': 'Duplicate Response ID or submission timestamp; every occurrence is rejected. Map a unique immutable Response ID when timestamps collide.'})
            continue
        try:
            email = data.get('email', '')
            if email.lower() in ('not provided', 'no mail provided', 'n/a', 'na', 'none', '-', 'no email'):
                email = ''
                warnings.append({'row': number, 'reason': 'Email placeholder omitted; no email address was supplied.'})
            lead = {'id': identifier, 'name': data.get('company') or data['name'], 'contact': data['name'],
                    'company': data.get('company', ''), 'mobile': data.get('mobile', ''), 'email': email,
                    'executive': data.get('executive') or 'Unassigned', 'source': 'Google Form',
                    'created_date': parse_date(data.get('created_date'), locale, timezone_name, True) or timestamp,
                    'product': data.get('product', ''), 'requirement': data['details'],
                    'priority': data.get('priority') or 'Medium'}
            if lead['priority'] not in ('Low', 'Medium', 'High', 'Urgent'):
                raise ValueError('Unknown urgency level. Use Low, Medium, High or Urgent.')
            fields = list(lead)
            accepted, rejected = validate_rows('leads', [fields, [lead[key] for key in fields]], {key: key for key in fields})
            if rejected:
                raise ValueError(rejected[0]['reason'])
            result['leads'].append({'row': number, 'data': accepted[0]['data']})
            if query:
                result['queries'].append({'row': number, 'data': {'id': 'FORM-Q:' + digest, 'lead_id': identifier,
                    'subject': data.get('product') or data['submission_type'], 'details': data['details'],
                    'executive': lead['executive'], 'created_date': timestamp}})
        except ValueError as exc:
            errors.append({'kind': 'leads', 'row': number, 'id': identifier, 'reason': str(exc)})
            if query:
                errors.append({'kind': 'queries', 'row': number, 'id': 'FORM-Q:' + digest, 'reason': 'Related response lead was rejected.'})
    return result, errors, warnings


def parse_form_link(link, sheet_error):
    if not link:
        return ''
    if not isinstance(link, str) or not re.fullmatch(r'https://docs\.google\.com/forms/d/(?:e/)?[A-Za-z0-9_-]{10,200}/viewform(?:\?[^#\s]*)?(?:#[^\s]*)?', link) or len(link) > 2048:
        raise sheet_error('Use the full Google Forms respondent link ending in /viewform.')
    return link
