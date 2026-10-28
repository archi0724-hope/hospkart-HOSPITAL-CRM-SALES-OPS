"""Read-only CRM knowledge and factual replies, rebuilt from saved data per request."""
import json
import re
from collections import Counter
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import shared_workspace

WORKSPACES = {'clients': 'Hospitals & Clients', 'rghs': 'RGHS Data', 'served': 'Already Served',
              'doctors': 'Doctors', 'potential': 'HOSPkart Potential Leads', 'leads': 'Leads & Queries'}
CLOSED = {'Completed / Served', 'Lost / Cancelled', 'Delivered', 'Not Interested', 'Demand Fulfilled', 'Order Finalized'}
RECORD_FIELDS = ('id', 'name', 'city', 'status', 'contact', 'requirement', 'product', 'next', 'executive', 'priority')


def matches(message):
    return bool(re.search(r'\b(?:crm|dashboard|leads?|queries|complaints?|follow[- ]?ups?|overdue|feedback message|rghs|clients?|hospitals|doctors|workspace|worksheet|saved records|knowledge|crm tests)\b|\binvoice\s+(?:summary|count|analysis|total)\b|\b(?:find|lookup|search|details)\b.*\bhospital\b|\bmessage\b.*\bsent\b', message, re.I))


def safe(value, limit=220):
    return re.sub(r'[\x00-\x1f\x7f]', ' ', str(value or ''))[:limit]


def record_summary(row, scope):
    return {**{key: safe(row.get(key)) for key in RECORD_FIELDS}, 'workspaceScope': scope, 'workspaceLabel': WORKSPACES[scope]}


def build_knowledge(conn, now=None):
    # One SQLite read transaction: counts and related queries describe one saved snapshot.
    workspace = shared_workspace.read(conn, omit_backups=True)
    values = workspace['values']
    today = (now or datetime.now(ZoneInfo('Asia/Kolkata'))).date().isoformat()
    records, workspaces, issues = [], {}, []
    for scope, label in WORKSPACES.items():
        rows = values['hk_v2_' + scope]
        ids = [str(row.get('id', '')) for row in rows]
        missing = sum(not identifier for identifier in ids)
        duplicate = sum(count - 1 for identifier, count in Counter(ids).items() if identifier and count > 1)
        if missing: issues.append({'scope': scope, 'reason': 'Missing record IDs', 'count': missing})
        if duplicate: issues.append({'scope': scope, 'reason': 'Duplicate record IDs', 'count': duplicate})
        workspaces[scope] = {'label': label, 'records': len(rows),
            'distinct_clients': len({(str(row.get('name', '')).strip().casefold(), str(row.get('city', '')).strip().casefold()) for row in rows if row.get('name') or row.get('city')}),
            'active_records': sum(row.get('status') not in CLOSED for row in rows),
            'status_counts': dict(Counter(str(row.get('status') or 'Unspecified') for row in rows))}
        records.extend(record_summary(row, scope) for row in rows)
    followups = []
    invalid_dates = 0
    for row in records:
        if not row['next']: continue
        try:
            try:
                normalized = date.fromisoformat(row['next'])
            except ValueError:
                timestamp = datetime.fromisoformat(row['next'].replace('Z', '+00:00'))
                normalized = (timestamp.astimezone(ZoneInfo('Asia/Kolkata')) if timestamp.tzinfo else timestamp).date()
        except ValueError:
            invalid_dates += 1
            continue
        followups.append({**row, 'next': normalized.isoformat()})
    followups.sort(key=lambda row: (row['next'], row['workspaceScope'], row['id']))
    if invalid_dates: issues.append({'scope': 'followups', 'reason': 'Invalid follow-up dates excluded from date queues', 'count': invalid_dates})
    queries = [json.loads(row['data']) for row in conn.execute('SELECT data FROM sheet_queries ORDER BY id')]
    linked_leads = {row.get('lead_id') for row in queries}
    query_ids = {row.get('id') for row in queries}
    queries.extend({'id': 'CRM-Q:' + row['id'], 'lead_id': row['id'],
        'subject': row['product'] or row['requirement'] or 'Client query',
        'details': row['requirement'], 'status': 'Open', 'executive': row['executive']}
        for row in records if row['workspaceScope'] == 'leads' and row['status'] == 'Query Received'
        and row['id'] not in linked_leads and 'CRM-Q:' + row['id'] not in query_ids)
    lead_ids = {row['id'] for row in records if row['workspaceScope'] == 'leads'}
    orphan_queries = sum(row.get('lead_id') not in lead_ids for row in queries)
    if orphan_queries: issues.append({'scope': 'queries', 'reason': 'Queries whose lead is absent from Leads & Queries', 'count': orphan_queries})
    complaints = values['hk_v2_complaints']
    complaint_counts = dict(Counter(row.get('status', 'Unspecified') for row in complaints))
    workbook = values.get('hk_v2_invoice_workbook')
    sheets = {sheet['name']: sheet['rows'] for sheet in (workbook or {}).get('sheets', [])}
    invoice_analysis = None
    source = 'Client Summary' if 'Client Summary' in sheets else 'Client Call List' if 'Client Call List' in sheets else None
    if source:
        distinct = {}
        for row in sheets[source]:
            key = str(row.get('Invoice No.') or '').strip().casefold()
            if key and key not in distinct: distinct[key] = row
        invoices = [row for row in distinct.values() if not re.search('cancel', str(row.get('Invoice Status', '')), re.I)]
        total, bad_amounts = Decimal('0'), 0
        for row in invoices:
            raw = row.get('Invoice Total (₹)')
            try:
                amount = Decimal(re.sub(r'[^0-9.\-]', '', str(raw)))
                if not amount.is_finite(): raise InvalidOperation
                total += amount
            except InvalidOperation:
                bad_amounts += 1
        if bad_amounts: issues.append({'scope': 'invoices', 'reason': 'Missing or invalid invoice totals; invoice value unavailable', 'count': bad_amounts})
        invoice_analysis = {'invoice_count': len(invoices),
            'distinct_clients': len({(str(row.get('Client / Hospital') or '').strip().casefold(), str(row.get('Delivery City / Location') or '').strip().casefold()) for row in invoices}),
            'invoice_value': str(total.quantize(Decimal('0.01'))) if not bad_amounts else None,
            'served_entries': workspaces['served']['records'], 'source_sheet': source}
    connection = conn.execute('SELECT settings,last_success,last_error FROM sheet_connection WHERE id=1').fetchone()
    sheet = None
    if connection:
        settings = json.loads(connection['settings'])
        sheet = {'name': settings['name'], 'last_success': connection['last_success'], 'last_error': connection['last_error']}
    checked_at = (now or datetime.now(ZoneInfo('Asia/Kolkata'))).isoformat(timespec='seconds')
    return {'source': 'Shared CRM database', 'revision': workspace['revision'], 'updated_at': workspace['updated_at'],
        'checked_at': checked_at, 'today': today, 'scope': 'All saved records; browser filters are not applied.',
        'workspaces': workspaces, 'records': records, 'workspace_records': len(records),
        'queries': queries, 'query_status_counts': dict(Counter(row.get('status') or 'Unspecified' for row in queries)),
        'complaints': complaints, 'complaint_status_counts': complaint_counts,
        'followups': followups, 'followup_counts': {'scheduled': len(followups),
            'overdue': sum(row['next'] < today for row in followups), 'due_today': sum(row['next'] == today for row in followups)},
        'invoice_analysis': invoice_analysis, 'sheet': sheet,
        'checks': {'passed': not issues, 'issues': issues, 'checked_at': checked_at}}


def aggregate_ai_context(knowledge):
    """Explicit counts-only consent: no records, contacts, text or invoice amounts."""
    workspaces = {name: {key: summary[key] for key in ('records','distinct_clients','active_records')}
                  for name, summary in knowledge['workspaces'].items()}
    invoices = knowledge['invoice_analysis']
    invoice_counts = {key: invoices[key] for key in ('invoice_count','distinct_clients','served_entries')} if invoices else None
    return {'today': knowledge['today'], 'revision': knowledge['revision'],
            'metric_definitions': {'workspace_records': 'Record headcount across saved workspaces, including independent copies; not unique hospitals.',
                                   'workspace_distinct_clients': 'Distinct clients within each individual workspace; do not add these for a global unique count.'},
            'kpis': {'workspace_records': knowledge['workspace_records']}, 'workspaces': workspaces,
            'followup_counts': knowledge['followup_counts'], 'query_count': len(knowledge['queries']),
            'complaint_counts': {'total': len(knowledge['complaints']),
                                 'open': sum(n for status,n in knowledge['complaint_status_counts'].items() if str(status).casefold() not in ('resolved','closed'))},
            'invoice_counts': invoice_counts}


def public_status(knowledge):
    return {key: knowledge[key] for key in ('source', 'revision', 'updated_at', 'checked_at', 'scope', 'workspace_records', 'workspaces', 'checks')} | {
        'queries': len(knowledge['queries']), 'complaints': len(knowledge['complaints']),
        'followup_counts': knowledge['followup_counts'], 'complaint_status_counts': knowledge['complaint_status_counts'],
        'automatic_refresh': 'Latest saved database snapshot on every CRM question; no model retraining required.'}


def describe_records(rows, total=None):
    lines = [f"{safe(row.get('name'))} [{safe(row.get('id'))}] · {safe(row.get('workspaceLabel'))} · {safe(row.get('status'))} · next: {safe(row.get('next')) or 'not set'} · owner: {safe(row.get('executive')) or 'Unassigned'}" for row in rows[:12]]
    if total is not None and total > 12: lines.append(f'Showing 12 of {total} records. Use dashboard filters to review the full list.')
    return '\n'.join(lines)


def reply(message, knowledge, context=None):
    text = message.casefold()
    context = context or {}
    footer = f"\nSource: saved CRM revision {knowledge['revision']} · all saved records, independent of browser filters."
    records = knowledge['records']
    if re.search(r'\bmessage\b.*\bsent\b', text):
        return 'Chat cannot confirm delivery. Check the saved message history and provider delivery status in the WhatsApp or Email panel. A draft is not a sent message.'
    if re.search(r'\b(?:delete|remove)\b', text) and re.search(r'\b(?:worksheet|sheet|import)\b', text):
        return 'To remove one import, use Data & backups → Manage imported Excel data, choose the specific worksheet/import, and complete the admin password confirmation. Chat has not deleted anything. Use a checkpoint for recovery; a full dashboard reset is not needed.'
    if re.search(r'\b(?:why|difference|different|distinguish)\b', text) and re.search(r'\bserved\b', text):
        return f"Already Served contains {knowledge['workspaces']['served']['records']} service entries and {knowledge['workspaces']['served']['distinct_clients']} distinct name/city combinations. One hospital can have multiple service entries. Copies in other workspaces also count separately in overall headcount. Invoice totals are counted once per invoice, separately from service-entry counts." + footer
    if re.search(r'\b(?:delete|reset|remove|send|resolve|close|update|edit|change)\b', text) and not re.search(r'\b(?:draft|how|steps|help)\b', text):
        return 'Chat is read-only. Review and save changes in the dashboard. Resolve complaints under Leads & Queries → Complaints; sending messages requires the dashboard send controls.'
    if re.search(r'\b(?:draft|write|prepare)\b.*\b(?:follow[- ]?up|whatsapp|feedback|message)\b', text):
        selected = context.get('selected_client')
        selected = selected if isinstance(selected, dict) else {}
        matches = [row for row in records if row['id'] == selected.get('id') and (not selected.get('workspaceScope') or row['workspaceScope'] == selected['workspaceScope'])]
        if len(matches) != 1:
            return 'Select a hospital/client in the WhatsApp panel first. If its ID appears in multiple workspaces, select the exact workspace record.'
        row = matches[0]
        if 'feedback' in text:
            return f"Hello {safe(row['contact'] or row['name'], 100)}, this is HOSPkart. Could you please share your feedback on your experience with us? Thank you.\n\nDraft only — review before sending."
        requirement = safe(row['product'] or row['requirement'], 180)
        return f"Hello {safe(row['contact'] or row['name'], 100)}, this is HOSPkart following up" + (f" on your requirement for {requirement}" if requirement else ' on our previous discussion') + '. Please let us know if you need any further information. Thank you.\n\nDraft only — review before sending.'
    if re.search(r'\b(?:knowledge|train|training|tests?|health)\b', text):
        issues = knowledge['checks']['issues']
        result = f"Live CRM knowledge: {knowledge['workspace_records']} workspace records, {len(knowledge['queries'])} queries, {len(knowledge['complaints'])} complaints. Data checks: " + ('passed.' if not issues else f'{len(issues)} issue categories need review.')
        if issues: result += '\n' + '\n'.join(f"{item['scope']}: {item['reason']} ({item['count']})." for item in issues)
        return result + '\nNew uploads and edits are read automatically on each CRM question. No model weights are trained.' + footer
    if re.search(r'\b(?:export|spreadsheet|google form|sync|connect sheet)\b', text):
        sheet = knowledge['sheet']
        return ('Use Leads & Queries → Connect Spreadsheet: check access, choose the layout/tab, map columns, preview, then import. Use Sync Now for new responses. Export Excel offers all or filtered Leads and Queries in separate worksheets. ' +
            (f"Connected spreadsheet: {safe(sheet['name'])}. Last successful sync: {safe(sheet['last_success']) or 'not yet synced'}." + (' Sync currently reports an error; review its status panel.' if sheet['last_error'] else '') if sheet else 'No spreadsheet has been imported and connected yet. Saving links alone does not activate synchronization.')) + footer
    lookup = re.search(r'\b(?:find|lookup|search|details (?:for|of)|status (?:for|of))\s+(.+)', message, re.I)
    if lookup:
        term = lookup.group(1).strip(' \"\'?.').casefold()
        found = [row for row in records if term in (row['id'].casefold(), row['name'].casefold())]
        if not found: found = [row for row in records if term in (row['id'] + ' ' + row['name'] + ' ' + row['city']).casefold()]
        return (describe_records(found, len(found)) if found else 'No matching saved CRM record. Try the exact record ID or hospital name.') + footer
    if re.search(r'\bcomplaints?\b', text):
        rows = knowledge['complaints']
        counts = knowledge['complaint_status_counts']
        pending = sum(row.get('status') in ('Open', 'In Progress') for row in rows)
        filtered = [row for row in rows if row.get('status') in ('Resolved', 'Closed')] if re.search(r'\b(?:resolved|closed)\b', text) else [row for row in rows if row.get('status') in ('Open', 'In Progress')]
        result = f"Complaints: {len(rows)} total · {pending} pending · {counts.get('Resolved', 0) + counts.get('Closed', 0)} resolved/closed."
        for row in filtered[:12]:
            result += f"\n{safe(row.get('id'))} · {safe(row.get('customer_name'))}: {safe(row.get('subject'))} · {safe(row.get('status'))} · {safe(row.get('priority'))} · owner: {safe(row.get('assigned_owner')) or 'Unassigned'}"
            if row.get('status') in ('Resolved', 'Closed'): result += '\nResolution: ' + safe(row.get('resolution'))
        if len(filtered) > 12: result += f'\nShowing 12 of {len(filtered)} matching complaints.'
        return result + footer
    if re.search(r'\bquer(?:y|ies)\b', text) and not re.search(r'\bleads\s*(?:and|&)\s*queries\b', text):
        rows = knowledge['queries']
        result = f"Queries: {len(rows)} total. " + ' · '.join(f'{safe(status)}: {count}' for status, count in sorted(knowledge['query_status_counts'].items()))
        for row in rows[:12]: result += f"\n{safe(row.get('id'))} → Lead {safe(row.get('lead_id'))}: {safe(row.get('subject'))} · {safe(row.get('status'))} · owner: {safe(row.get('executive')) or 'Unassigned'}"
        if len(rows) > 12: result += f'\nShowing 12 of {len(rows)} queries.'
        return result + footer
    if re.search(r'\b(?:follow[- ]?ups?|overdue)\b', text) and not re.search(r'\b(?:summary|summarize|dashboard)\b', text):
        counts = knowledge['followup_counts']
        due = knowledge['followups']
        if 'overdue' in text: due = [row for row in due if row['next'] < knowledge['today']]
        elif re.search(r'\btoday\b', text): due = [row for row in due if row['next'] == knowledge['today']]
        return f"Follow-ups ({knowledge['today']}, IST): {counts['scheduled']} scheduled · {counts['overdue']} overdue · {counts['due_today']} due today. Closed-stage records with saved dates are included, as in the dashboard queue.\n" + describe_records(due, len(due)) + footer
    if re.search(r'\binvoices?\b', text):
        analysis = knowledge['invoice_analysis']
        if analysis is None: return 'Invoice analysis is unavailable: upload a workbook with Client Summary or Client Call List. No invoice totals have been assumed.' + footer
        value = 'INR ' + analysis['invoice_value'] if analysis['invoice_value'] is not None else 'unavailable (missing or invalid invoice totals)'
        return f"Invoices: {analysis['invoice_count']} distinct non-cancelled invoices · {analysis['distinct_clients']} distinct clients · invoice value: {value}.\nAlready Served: {analysis['served_entries']} service entries, counted separately. Repeated invoice item rows are counted once per invoice." + footer
    scopes = []
    for scope, pattern in {'leads': r'\bleads?\b', 'rghs': r'\brghs\b', 'served': r'\b(?:served|service entries)\b', 'doctors': r'\bdoctors?\b', 'potential': r'\bpotential\b', 'clients': r'\b(?:clients?|hospitals?)\b'}.items():
        if re.search(pattern, text): scopes.append(scope)
    if scopes and not re.search(r'\b(?:summary|summarize|dashboard|all workspaces)\b', text):
        result = []
        for scope in scopes:
            stats = knowledge['workspaces'][scope]
            result.append(f"{stats['label']}: {stats['records']} records · {stats['distinct_clients']} distinct name/city combinations · {stats['active_records']} active records.")
            result.append(' · '.join(f'{safe(status)}: {count}' for status, count in sorted(stats['status_counts'].items())))
        return '\n'.join(result) + footer
    stats = knowledge['followup_counts']
    return (f"CRM summary: {knowledge['workspace_records']} workspace records (copies across workspaces count separately; this is not a unique hospital count).\n" +
        '\n'.join(f"{value['label']}: {value['records']}" for value in knowledge['workspaces'].values()) +
        f"\nQueries: {len(knowledge['queries'])} · Complaints: {len(knowledge['complaints'])}.\nFollow-ups: {stats['overdue']} overdue · {stats['due_today']} due today.\nAsk for leads, queries, complaints, overdue follow-ups, invoice summary, or find a hospital by name/ID." + footer)
