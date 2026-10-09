const workColors = {
  red: 'Untouched', green: 'Outreach completed', yellow: 'Call not connected', blue: 'Queries and follow-ups / orders'
};
const blueWorkStages = ['Query Received', 'Quotation Shared', 'Follow-up Required', 'Negotiation', 'PO / Order Confirmed', 'Demand Fulfilled', 'Order Finalized', 'Delivered', 'Feedback Pending', 'Completed / Served'];
let duplicateWorkRecords = new Set();

function findWorkRecord(id, scope = 'clients') {
  const records=scope==='clients'?clients:scope==='leads'?sectionRecords.leads:scope==='rghs'?sectionRecords.rghs:segmentData[scope]||[];
  return records.find(record => record.id === id);
}

function automaticWorkColor(record, scope = 'clients') {
  if (blueWorkStages.includes(record.status) || Number(record.order) > 0 || record.workQueryReceived) return 'blue';
  const history = calls.map((entry, index) => ({entry, index})).filter(({entry}) => entry.clientId === record.id && (entry.recordScope || 'clients') === scope).sort((a, b) => b.entry.date.localeCompare(a.entry.date) || b.index - a.index);
  const latest = history[0]?.entry;
  const callTime = latest ? Date.parse(latest.workOccurredAt || latest.date + 'T00:00:00+05:30') : 0;
  const emailTime = Math.max(Date.parse(record.workEmailAcceptedAt || '') || 0, Date.parse(record.workOutreachAt || '') || 0);
  if (emailTime && emailTime >= callTime) return 'green';
  if (latest) return latest.connected === 'Yes' ? 'green' : 'yellow';
  if (record.workOutreachCompleted || record.status === 'Contacted') return 'green';
  return 'red';
}

function workColor(record, scope = 'clients') {
  return Object.hasOwn(workColors, record.workColor) ? record.workColor : automaticWorkColor(record, scope);
}

function workRowAttributes(record, scope = 'clients') {
  return `class="work-${workColor(record, scope)}${isDuplicateRecord(record, scope) ? ' duplicate-record' : ''}" data-work-record="${escapeHtml(record.id)}" data-work-scope="${escapeHtml(scope)}"`;
}

function isDuplicateRecord(record, scope = 'clients') {
  return duplicateWorkRecords.has(`${scope}:${record.id}`);
}

function duplicateNameKey(value) {
  return String(value || '').normalize('NFKC').trim().toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
}

function refreshDuplicateWorkRecords() {
  duplicateWorkRecords = new Set();
  const groups = new Map();
  for (const record of workspaceRecords()) {
    const name = duplicateNameKey(record.name);
    if (!name) continue;
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name).push(record);
  }
  for (const group of groups.values()) {
    if (group.length < 2) continue;
    for (const record of group) duplicateWorkRecords.add(`${record.workspaceScope}:${record.id}`);
  }
}

function copyToPotentialLead(record, scope, sourceKeys) {
  if (!record || !['clients', 'leads', 'rghs'].includes(scope) || workColor(record, scope) !== 'green') return false;
  if (['Not Interested', 'Lost / Cancelled'].includes(record.status)) return false;
  const sourceKey = `${scope}:${record.id}`;
  if (sourceKeys.has(sourceKey)) return false;
  const nextNo = Math.max(0, ...segmentData.potential.map(item => Number((item.id.match(/\d+/) || ['0'])[0]))) + 1;
  const sourceData = {
    ...(record.sourceData || {}),
    'Lead Status': record.status || '',
    'Query / Requirement': record.requirement || '',
    'Product Name': record.product || '',
    'City': record.city || '',
    'Contact Person': record.contact || '',
    'Mobile Number': record.mobile || '',
    'Email': record.email || '',
    'Assigned Executive': record.executive || '',
    'Latest Remark': record.remark || '',
    'Source Workspace': scope
  };
  segmentData.potential.push({
    ...clone(record),
    id: 'HK-P' + String(nextNo).padStart(4, '0'),
    sourceWorkspace: scope,
    sourceRecordId: record.id,
    workColor: 'green',
    sourceData
  });
  sourceKeys.add(sourceKey);
  return true;
}

async function routeGreenPotentialLeads(scope) {
  const sources = scope ? [[scope, findWorkRecordForScope(scope)]] : [
    ['clients', clients], ['leads', sectionRecords.leads], ['rghs', sectionRecords.rghs]
  ];
  const sourceKeys = new Set(segmentData.potential.map(item => `${item.sourceWorkspace}:${item.sourceRecordId}`));
  let changed = false;
  for (const [sourceScope, records] of sources) {
    for (const record of Array.isArray(records) ? records : records ? [records] : []) {
      changed = copyToPotentialLead(record, sourceScope, sourceKeys) || changed;
    }
  }
  if (changed) await persistSegments();
}

function findWorkRecordForScope(scope) {
  return scope === 'clients' ? clients : scope === 'leads' ? sectionRecords.leads : scope === 'rghs' ? sectionRecords.rghs : [];
}

function workColorOptions(record, scope = 'clients') {
  return `<option value=""${record.workColor ? '' : ' selected'}>—</option>` + Object.entries(workColors).map(([color, label]) => `<option value="${color}"${record.workColor === color ? ' selected' : ''}>${color[0].toUpperCase() + color.slice(1)} — ${label}</option>`).join('');
}

function workStatusControl(record, scope = 'clients') {
  const color = workColor(record, scope), id = escapeHtml(record.id), source = escapeHtml(scope);
  return `<div class="work-controls" onclick="event.stopPropagation()"><span class="work-tag work-${color}">${workColors[color]}</span><select class="work-color-select" aria-label="Work color for ${escapeHtml(record.name)}" data-work-id="${id}" data-work-scope="${source}" onchange="changeWorkColor(this)">${workColorOptions(record, scope)}</select><button type="button" class="action-link" data-work-id="${id}" data-work-scope="${source}" onclick="openWorkStatusEditor(this.dataset.workId,this.dataset.workScope)">Remarks / color</button></div>${color === 'blue' && !String(record.remark || '').trim() ? '<div class="work-missing-remark">Add a remark for this order or query.</div>' : ''}`;
}

async function saveWorkRecords(scope) {
  await routeGreenPotentialLeads(scope);
  if (scope === 'clients') await persist();
  else if (scope === 'leads') await persistLeads();
  else if (scope === 'rghs') await persistRghs();
  else await persistSegments();
}

async function changeWorkColor(select) {
  if (dashboardResetting) return;
  const {workId: id, workScope: scope} = select.dataset, record = findWorkRecord(id, scope);
  if (!record) return;
  const chosen = select.value;
  if ((chosen === 'blue' || (!chosen && automaticWorkColor(record, scope) === 'blue')) && !String(record.remark || '').trim()) {
    select.value = record.workColor || '';
    openWorkStatusEditor(id, scope, chosen);
    return;
  }
  record.workColor = chosen;
  record.workColorUpdatedAt = new Date().toISOString();
  await saveWorkRecords(scope);
  renderAll();
  toast(chosen ? `Work color changed to ${chosen}.` : 'Automatic work colors restored.');
}

function openWorkStatusEditor(id, scope = 'clients', selected) {
  const record = findWorkRecord(id, scope);
  if (!record) return;
  document.getElementById('workRecordId').value = id;
  document.getElementById('workRecordScope').value = scope;
  document.getElementById('workRecordName').textContent = record.name;
  document.getElementById('workRecordColor').innerHTML = workColorOptions(record, scope);
  if (selected !== undefined) document.getElementById('workRecordColor').value = selected;
  document.getElementById('workRecordRemark').value = record.remark || '';
  updateWorkRemarkRequirement();
  document.getElementById('workStatusDrawer').classList.add('open');
  document.getElementById('workRecordRemark').focus();
}

function updateWorkRemarkRequirement() {
  const record = findWorkRecord(document.getElementById('workRecordId').value, document.getElementById('workRecordScope').value);
  const scope = document.getElementById('workRecordScope').value;
  const chosen = document.getElementById('workRecordColor').value;
  const required = chosen === 'blue' || (!chosen && record && automaticWorkColor(record, scope) === 'blue');
  document.getElementById('workRecordRemark').required = required;
  document.getElementById('workRemarkLabel').textContent = required ? 'Remarks (required for query / follow-up / order)' : 'Remarks';
}

async function saveWorkStatus(event) {
  event.preventDefault();
  if (dashboardResetting) return;
  const scope = document.getElementById('workRecordScope').value;
  const record = findWorkRecord(document.getElementById('workRecordId').value, scope);
  if (!record) return;
  updateWorkRemarkRequirement();
  const remark = document.getElementById('workRecordRemark').value.trim();
  if (document.getElementById('workRecordRemark').required && !remark) { toast('Add a remark describing the query, follow-up, or order.'); return; }
  record.workColor = document.getElementById('workRecordColor').value;
  record.remark = remark;
  record.workColorUpdatedAt = new Date().toISOString();
  if (record.sourceData) {
    Object.keys(record.sourceData).filter(key => ['remarks', 'remark', 'latestremark'].includes(normalizeImportHeader(key))).forEach(key => {record.sourceData[key] = remark;});
  }
  await saveWorkRecords(scope);
  closeDrawer('workStatusDrawer');
  renderAll();
  toast('Work color and remarks saved.');
}

function recordWorkStage(record) {
  if (blueWorkStages.includes(record.status) || Number(record.order) > 0) record.workQueryReceived = true;
}

function workCallOccurredAt(date) {
  return date + 'T' + new Date().toLocaleTimeString('en-GB', {timeZone: 'Asia/Kolkata', hour12: false}) + '+05:30';
}

async function markWorkOutreach(record, scope = recordScopeForId(record?.id)) {
  if (!record) return;
  record.workOutreachCompleted = true;
  record.workOutreachAt = new Date().toISOString();
  await persistScope(scope);
  renderAll();
}

async function syncEmailWorkStatus(items) {
  if (dashboardResetting) return;
  let changed = false;
  items.filter(job => job.status === 'accepted' && job.sent_at).forEach(job => {
    const matches = clients.filter(client => String(client.email || '').trim().toLowerCase() === job.email.toLowerCase());
    const matching = matches.filter(client => client.name === job.client_name);
    const targets = matching.length ? matching : matches.length === 1 ? matches : [];
    targets.forEach(client => {
      if (Date.parse(job.sent_at) > (Date.parse(client.workEmailAcceptedAt || '') || 0)) {
        client.workEmailAcceptedAt = job.sent_at;
        changed = true;
      }
    });
  });
  if (changed) { await routeGreenPotentialLeads('clients'); await persist(); if (currentView !== 'email') renderAll(); }
}

async function refreshWorkEmailStatus() {
  const version = dashboardDataVersion;
  if (dashboardResetting) return;
  try {
    const response = await fetch('/api/email/followups');
    const data = await response.json();
    if (dashboardResetting || version !== dashboardDataVersion) return;
    if (response.ok && data.ok) await syncEmailWorkStatus(data.items);
  } catch (_) { /* Offline dashboards keep their saved colors. */ }
}

setInterval(() => { if (!document.hidden && currentView !== 'email') refreshWorkEmailStatus(); }, 15000);
