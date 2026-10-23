// Sheet imports are saved in SQLite first, then merged into the existing lead store.
let sheetState = null;
let sheetInspection = null;
let sheetPreviewToken = null;
let sheetPreviewReportData = null;
let sheetBusy = false;
let sheetAppliedRevision = null;
let sheetPollTimer = null;
let sheetExportView = 'leads';
const sheetElement = id => document.getElementById(id);
const sheetEscape = value => escapeHtml(String(value ?? ''));

async function sheetRequest(path, data) {
  const response = await fetch('/api/spreadsheet/' + path, {
    method: data === undefined ? 'GET' : 'POST',
    headers: data === undefined ? {} : {'Content-Type': 'application/json', 'X-CRM-Request': '1'},
    body: data === undefined ? undefined : JSON.stringify(data),
    signal: AbortSignal.timeout(90000)
  });
  const result = await response.json().catch(() => ({error: 'The server returned an unreadable response.'}));
  if (!response.ok || !result.ok) throw new Error(result.error || 'Spreadsheet request failed.');
  return result;
}

function setSheetBusy(busy) {
  sheetBusy = busy;
  document.querySelectorAll('[data-sheet-action]').forEach(button => { button.disabled = busy; });
  sheetElement('sheetSyncButton').disabled = busy || !sheetState?.connection;
  sheetElement('sheetImportButton').disabled = busy || !sheetPreviewToken;
  sheetElement('sheetConnectPanel').querySelectorAll('input,select').forEach(field => {field.disabled = busy;});
}

async function runSheetAction(action) {
  if (sheetBusy || dashboardResetting) return;
  setSheetBusy(true);
  sheetElement('sheetSetupMessage').textContent = 'Working…';
  sheetElement('sheetConnectionError').textContent = '';
  try {
    await action();
    sheetElement('sheetSetupMessage').textContent = '';
  } catch (error) {
    const message = error.name === 'TimeoutError' ? 'The request timed out. Check connection status before retrying.' : error.message;
    sheetElement('sheetSetupMessage').textContent = message;
    sheetElement('sheetConnectionError').textContent = message;
  } finally {
    setSheetBusy(false);
  }
}

function openSpreadsheetConnection() {
  navigate('leads');
  sheetElement('sheetConnectPanel').open = true;
  sheetElement('sheetConnectPanel').scrollIntoView({behavior: 'smooth', block: 'start'});
  sheetElement('sheetLinkInput').focus();
}

function invalidateSheetPreview() {
  sheetPreviewToken = null;
  sheetPreviewReportData = null;
  sheetElement('sheetPreviewStep').classList.add('hidden');
  sheetElement('sheetImportButton').disabled = true;
}
function invalidateSheetMapping() {
  invalidateSheetPreview();
  sheetElement('sheetMappingStep').classList.add('hidden');
  sheetElement('sheetMappings').replaceChildren();
}
function invalidateSheetInspection() {
  sheetInspection = null;
  invalidateSheetMapping();
  sheetElement('sheetTabStep').classList.add('hidden');
}

function inspectSpreadsheet() {
  return runSheetAction(async () => {
    invalidateSheetInspection();
    sheetInspection = await sheetRequest('inspect', {link: sheetElement('sheetLinkInput').value});
    const saved = sheetState?.connection;
    for (const [kind, id] of [['leads', 'sheetLeadsTab'], ['queries', 'sheetQueriesTab']]) {
      const select = sheetElement(id);
      select.replaceChildren(...sheetInspection.tabs.map(tab => new Option(tab.name, tab.name)));
      const chosen = saved?.id === sheetInspection.id ? saved.tabs[kind] : sheetInspection.tabs.find(tab => tab.name.toLowerCase() === kind)?.name;
      select.value = chosen || sheetInspection.tabs[kind === 'leads' ? 0 : Math.min(1, sheetInspection.tabs.length - 1)].name;
    }
    if (saved?.id === sheetInspection.id) sheetElement('sheetAutoMinutes').value = String(saved.auto_minutes);
    sheetElement('sheetTabStep').classList.remove('hidden');
  });
}

const sheetColumnAliases = {
  id: ['id'], name: ['hospital / client name', 'hospital name', 'lead name'], mobile: ['mobile', 'mobile number', 'phone number'],
  executive: ['executive', 'assigned executive', 'owner'], next: ['next', 'next follow-up date', 'follow up date'],
  lead_id: ['lead id'], created_date: ['created at', 'created date'], updated_date: ['updated at', 'updated date'],
  details: ['details', 'query details', 'requirement'], last: ['last', 'last contact'], quote: ['quote'], order: ['order']
};
function loadSpreadsheetColumns() {
  return runSheetAction(async () => {
    invalidateSheetMapping();
    if (!sheetInspection) throw new Error('Check the spreadsheet link first.');
    if (!sheetState) await applySheetState(await sheetRequest('status'));
    const result = await sheetRequest('columns', {
      link: sheetElement('sheetLinkInput').value,
      tabs: [sheetElement('sheetLeadsTab').value, sheetElement('sheetQueriesTab').value]
    });
    const mappingRoot = sheetElement('sheetMappings');
    ['leads', 'queries'].forEach((kind, index) => {
      const group = document.createElement('div');
      const title = document.createElement('h3'); title.textContent = kind === 'leads' ? 'Leads columns' : 'Queries columns'; group.append(title);
      const headers = result.sheets[index].headers.filter(Boolean);
      const saved = sheetState?.connection;
      for (const [field, label] of sheetState.fields[kind]) {
        const row = document.createElement('div'); row.className = 'sheet-mapping-field';
        const name = document.createElement('label'); name.htmlFor = 'sheetMap-' + kind + '-' + field;
        name.textContent = label + (sheetState.required[kind].includes(field) ? ' *' : '');
        const select = document.createElement('select'); select.id = name.htmlFor; select.className = 'control';
        select.dataset.sheetKind = kind; select.dataset.sheetField = field;
        select.append(new Option('Do not map', ''), ...headers.map(header => new Option(header, header)));
        const old = saved?.id === sheetInspection.id ? saved.mappings[kind]?.[field] : '';
        const aliases = [label.toLowerCase(), field.toLowerCase(), ...(sheetColumnAliases[field] || [])];
        const automatic = headers.find(header => aliases.includes(header.toLowerCase()));
        select.value = headers.includes(old) ? old : automatic || '';
        select.addEventListener('change', invalidateSheetPreview);
        row.append(name, select); group.append(row);
      }
      mappingRoot.append(group);
    });
    sheetElement('sheetMappingStep').classList.remove('hidden');
  });
}

function sheetReportHtml(report, preview = false) {
  if (!report) return '';
  const counts = '<div class="sheet-report">' + Object.entries(report.counts).map(([kind, value]) =>
    '<div><strong>' + sheetEscape(kind === 'leads' ? 'Leads' : 'Queries') + '</strong><br>' +
    ['added', 'updated', 'unchanged', 'rejected'].map(key => value[key] + ' ' + key).join(' · ') + '</div>').join('') + '</div>';
  const errors = report.errors || [];
  return counts + (errors.length ? '<details><summary>' + errors.length + ' rejected rows — review issues</summary><p class="mini-help">Showing the first 200 issues. Correct the sheet and sync again.</p><button class="btn small" type="button" onclick="downloadSheetIssues(' + preview + ')">Download all validation issues</button><div class="table-wrap sheet-preview-table"><table class="data-table"><thead><tr><th>Tab</th><th>Row</th><th>ID</th><th>Reason</th></tr></thead><tbody>' + errors.slice(0, 200).map(error => '<tr><td>' + sheetEscape(error.kind) + '</td><td>' + error.row + '</td><td>' + sheetEscape(error.id) + '</td><td>' + sheetEscape(error.reason) + '</td></tr>').join('') + '</tbody></table></div></details>' : '');
}

function downloadSheetIssues(preview) {
  const report = preview ? sheetPreviewReportData : sheetState?.connection?.report;
  const url = URL.createObjectURL(new Blob([JSON.stringify(report?.errors || [], null, 2)], {type: 'application/json'}));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'HOSPkart_Spreadsheet_Validation_' + TODAY + '.json';
  document.body.append(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function previewSpreadsheet() {
  return runSheetAction(async () => {
    invalidateSheetPreview();
    const mappings = {leads: {}, queries: {}};
    sheetElement('sheetMappings').querySelectorAll('select[data-sheet-field]').forEach(select => {
      if (select.value) mappings[select.dataset.sheetKind][select.dataset.sheetField] = select.value;
    });
    const result = await sheetRequest('preview', {
      link: sheetElement('sheetLinkInput').value,
      tabs: {leads: sheetElement('sheetLeadsTab').value, queries: sheetElement('sheetQueriesTab').value},
      mappings, auto_minutes: Number(sheetElement('sheetAutoMinutes').value)
    });
    sheetPreviewToken = result.token;
    sheetPreviewReportData = result.report;
    sheetElement('sheetPreviewReport').innerHTML = sheetReportHtml(result.report, true);
    sheetElement('sheetPreviewRows').innerHTML = ['leads', 'queries'].map(kind => {
      const fields = sheetState.fields[kind].filter(([field]) => mappings[kind][field]);
      return '<h4>' + sheetEscape(kind) + '</h4><div class="table-wrap sheet-preview-table"><table class="data-table"><thead><tr>' + fields.map(([, label]) => '<th>' + sheetEscape(label) + '</th>').join('') + '</tr></thead><tbody>' + result.preview[kind].map(row => '<tr>' + fields.map(([field]) => '<td>' + sheetEscape(row[field]) + '</td>').join('') + '</tr>').join('') + '</tbody></table></div>';
    }).join('');
    sheetElement('sheetPreviewStep').classList.remove('hidden');
  });
}

async function applySheetState(result) {
  const revision = result.connection?.revision ?? 0;
  if (revision !== sheetAppliedRevision) {
    const nextLeads = sectionRecords.leads.map(row => ({...row}));
    const index = new Map(nextLeads.map((row, position) => [row.id, position]));
    for (const row of result.leads) {
      const defaults = {type: 'New Prospect', city: '', district: '', state: '', contact: '', mobile: '', email: '',
        requirement: '', product: '', quote: 0, order: 0, last: '', next: '', executive: 'Unassigned',
        remark: '', priority: 'Medium'};
      const position = index.get(row.id);
      if (position === undefined) { index.set(row.id, nextLeads.length); nextLeads.push({...defaults, ...row}); }
      else nextLeads[position] = {...nextLeads[position], ...row};
    }
    // Commit before touching the rendered state; failed browser storage keeps prior records.
    if (JSON.stringify(nextLeads) !== JSON.stringify(sectionRecords.leads)) {
      await writeDashboardValues({hk_v2_leads: nextLeads});
      sectionRecords.leads = nextLeads;
    }
    sheetAppliedRevision = revision;
    sheetState = result;
    const selected = Object.fromEntries(['statusFilter', 'cityFilter', 'executiveFilter', 'clientTypeFilter'].map(id => [id, sheetElement(id).value]));
    populateFilters();
    Object.entries(selected).forEach(([id, value]) => {
      const field = sheetElement(id);
      if (value && !Array.from(field.options).some(option => option.value === value)) field.add(new Option(value, value));
      field.value = value;
    });
    renderAll();
  } else sheetState = result;
  renderSheetConnection();
  renderSpreadsheetRecords();
}

function renderSheetConnection() {
  const connection = sheetState?.connection;
  sheetElement('sheetStatusText').textContent = connection ? 'Connected: ' + connection.name : 'No spreadsheet connected.';
  sheetElement('sheetSyncTime').textContent = connection ? 'Last successful sync: ' + (connection.last_success ? new Date(connection.last_success).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata'}) + ' IST' : 'Not yet synced') + ' · Automatic refresh: ' + (connection.auto_minutes ? connection.auto_minutes + ' minutes' : 'Off') : '';
  sheetElement('sheetConnectionError').textContent = connection?.last_error || '';
  sheetElement('sheetSyncReport').innerHTML = sheetReportHtml(connection?.report);
  const link = sheetElement('sheetOpenLink');
  link.classList.toggle('hidden', !connection);
  if (connection) link.href = connection.link;
  sheetElement('sheetCredentialHint').textContent = sheetState?.google_configured ? 'Google access is configured on the server. Share the source spreadsheet with that service account as Viewer; the access check will verify permission.' : 'Google access is not configured. Ask the administrator to configure server credentials using the setup instructions. Your sheet can stay private.';
  sheetElement('sheetSyncButton').disabled = sheetBusy || !connection;
}

function importSpreadsheetPreview() {
  return runSheetAction(async () => {
    if (!sheetPreviewToken) throw new Error('Preview and validate the current mapping first.');
    const result = await sheetRequest('import', {token: sheetPreviewToken});
    invalidateSheetPreview();
    await applySheetState(result);
    toast('Spreadsheet imported and connection saved. Rejected rows are listed for review.');
  });
}
function syncLinkedSpreadsheet() {
  return runSheetAction(async () => {
    invalidateSheetPreview();
    await applySheetState(await sheetRequest('sync', {}));
    toast('Spreadsheet sync saved. Dashboard counts and tables updated.');
  });
}

function visibleLeadRecords() {
  const query = sheetElement('sheetLeadSearch')?.value.trim().toLowerCase() || '';
  const status = sheetElement('sheetLeadStatus')?.value || '';
  const owner = sheetElement('sheetLeadOwner')?.value || '';
  return sectionRecords.leads.filter(row => (!query || [row.id, row.name, row.company, row.mobile, row.email, row.requirement, row.product].join(' ').toLowerCase().includes(query)) && (!status || row.status === status) && (!owner || row.executive === owner));
}

function allQueryRecords() {
  const linked = sheetState?.queries || [];
  const leadIds = new Set(linked.map(row => row.lead_id));
  const ids = new Set(linked.map(row => row.id));
  const legacy = sectionRecords.leads.filter(row => row.status === 'Query Received' && !leadIds.has(row.id)).map(row => ({
    id: 'CRM-Q:' + row.id, lead_id: row.id, subject: row.product || row.requirement || 'Client query',
    details: row.requirement || row.remark || '', status: 'Open', executive: row.executive || '',
    created_date: row.created_date || '', updated_date: row.updated_date || ''
  })).filter(row => !ids.has(row.id));
  return [...linked, ...legacy];
}

function visibleQueryRecords() {
  const query = sheetElement('sheetQuerySearch')?.value.trim().toLowerCase() || '';
  const status = sheetElement('sheetQueryStatus')?.value || '';
  const owner = sheetElement('sheetQueryOwner')?.value || '';
  const lead = sheetElement('sheetQueryLead')?.value || '';
  return allQueryRecords().filter(row => (!query || [row.id, row.lead_id, row.subject, row.details].join(' ').toLowerCase().includes(query)) && (!status || row.status === status) && (!owner || row.executive === owner) && (!lead || row.lead_id === lead));
}

function updateSheetFilter(id, values, label) {
  const field = sheetElement(id), selected = field.value;
  const unique = [...new Set(values.filter(Boolean))].sort();
  if (selected && !unique.includes(selected)) unique.push(selected);
  field.replaceChildren(new Option(label, ''), ...unique.map(value => new Option(value, value)));
  field.value = selected;
}

function renderSpreadsheetRecords() {
  if (!sheetElement('sheetLeadRows')) return;
  const queries = allQueryRecords();
  updateSheetFilter('sheetLeadStatus', [...statuses, ...sectionRecords.leads.map(row => row.status)], 'All statuses');
  updateSheetFilter('sheetLeadOwner', sectionRecords.leads.map(row => row.executive), 'All owners');
  updateSheetFilter('sheetQueryStatus', queries.map(row => row.status), 'All statuses');
  updateSheetFilter('sheetQueryOwner', queries.map(row => row.executive), 'All owners');
  updateSheetFilter('sheetQueryLead', queries.map(row => row.lead_id), 'All leads');
  const leads = visibleLeadRecords(), visibleQueries = visibleQueryRecords();
  sheetElement('sheetLeadVisibleCount').textContent = 'Showing ' + leads.length + ' of ' + sectionRecords.leads.length + ' leads (all pipeline stages)';
  sheetElement('sheetQueryTotal').textContent = String(queries.length);
  sheetElement('sheetQueryVisibleCount').textContent = 'Showing ' + visibleQueries.length + ' of ' + queries.length + ' queries';
  const leadBody = sheetElement('sheetLeadRows');
  leadBody.innerHTML = leads.map(row => '<tr><td>' + sheetEscape(row.id) + '</td><td>' + sheetEscape(row.name) + '<div class="tiny">' + sheetEscape(row.company) + '</div></td><td>' + sheetEscape(row.email) + '<br>' + sheetEscape(row.mobile) + '</td><td>' + sheetEscape(row.status) + '</td><td>' + sheetEscape(row.executive) + '</td><td>' + sheetEscape(row.created_date) + '</td><td>' + sheetEscape(row.next) + '</td><td><button class="action-link" type="button">Edit record</button></td></tr>').join('') || '<tr><td colspan="8" class="empty-state">No leads match these filters.</td></tr>';
  leadBody.querySelectorAll('button').forEach((button, index) => {button.onclick = () => openLeadRecordForm(leads[index].status, leads[index].id);});
  sheetElement('sheetQueryRows').innerHTML = visibleQueries.map(row => '<tr>' + ['id', 'lead_id', 'subject', 'details', 'status', 'executive', 'created_date', 'updated_date'].map(field => '<td>' + sheetEscape(row[field]) + '</td>').join('') + '</tr>').join('') || '<tr><td colspan="8" class="empty-state">No queries match these filters.</td></tr>';
  const counts = queries.reduce((result, row) => {result[row.status || 'Unspecified'] = (result[row.status || 'Unspecified'] || 0) + 1; return result;}, Object.create(null));
  sheetElement('sheetQueryChart').innerHTML = Object.entries(counts).map(([status, count]) => '<span>' + sheetEscape(status) + ': <strong>' + count + '</strong></span>').join('');
}

function exportLeadQueryRecords() {
  if (sheetElement('sheetExportScope').value === 'all') return {leads: sectionRecords.leads, queries: allQueryRecords()};
  if (sheetExportView === 'dashboard') {
    const leads = filtered.filter(row => row.workspaceScope === 'leads');
    const ids = new Set(leads.map(row => row.id));
    return {leads, queries: allQueryRecords().filter(row => ids.has(row.lead_id))};
  }
  return {leads: visibleLeadRecords(), queries: visibleQueryRecords()};
}
function updateLeadQueryExportCount() {
  const records = exportLeadQueryRecords();
  sheetElement('sheetExportCount').textContent = records.leads.length + ' Leads · ' + records.queries.length + ' Queries';
}
function openLeadQueryExport() {
  sheetExportView = currentView === 'dashboard' ? 'dashboard' : 'leads';
  sheetElement('sheetExportError').textContent = '';
  sheetElement('sheetExportScope').value = 'all';
  updateLeadQueryExportCount();
  sheetElement('leadQueryExportDialog').showModal();
}
function exportCurrentView() {
  if (currentView === 'dashboard' || currentView === 'leads') return openLeadQueryExport();
  return exportLegacyCurrentView();
}
async function downloadLeadQueryExcel() {
  const button = sheetElement('sheetDownloadButton'); button.disabled = true;
  sheetElement('sheetExportError').textContent = '';
  try {
    const response = await fetch('/api/spreadsheet/export', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CRM-Request': '1'}, body: JSON.stringify(exportLeadQueryRecords()), signal: AbortSignal.timeout(90000)});
    if (!response.ok) { const result = await response.json(); throw new Error(result.error || 'Export failed.'); }
    const blob = await response.blob(), url = URL.createObjectURL(blob), anchor = document.createElement('a');
    anchor.href = url; anchor.download = 'HOSPkart_Leads_Queries_' + TODAY + '.xlsx';
    document.body.append(anchor); anchor.click(); anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    sheetElement('leadQueryExportDialog').close();
  } catch (error) { sheetElement('sheetExportError').textContent = error.message; }
  finally { button.disabled = false; }
}

async function initializeSpreadsheetSync() {
  try {
    await applySheetState(await sheetRequest('status'));
    const connection = sheetState?.connection;
    if (connection) sheetElement('sheetLinkInput').value = connection.link;
  } catch (error) {
    sheetElement('sheetConnectionError').textContent = 'Spreadsheet status unavailable. Existing CRM records are kept. ' + error.message;
  }
  clearInterval(sheetPollTimer);
  sheetPollTimer = setInterval(async () => {
    if (sheetBusy || dashboardResetting || document.hidden) return;
    const version = dashboardDataVersion;
    try {
      const result = await sheetRequest('status');
      if (!sheetBusy && !dashboardResetting && version === dashboardDataVersion) await applySheetState(result);
    } catch (error) { sheetElement('sheetConnectionError').textContent = 'Cannot refresh spreadsheet status. Last saved data is retained. ' + error.message; }
  }, 30000);
}
