let complaints = [];
let complaintSaving = false;
const complaintStatuses = ['Open', 'In Progress', 'Resolved', 'Closed'];
const complaintField = id => document.getElementById(id);
const complaintText = value => escapeHtml(String(value ?? ''));
const complaintFinished = row => ['Resolved', 'Closed'].includes(row.status);

function complaintDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('en-IN', {timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'short'}) + ' IST';
}

function renderComplaints() {
  if (!complaintField('complaintRows')) return;
  complaintField('complaintTotal').textContent = complaints.length;
  complaintField('complaintPending').textContent = complaints.filter(row => !complaintFinished(row)).length;
  complaintField('complaintResolved').textContent = complaints.filter(complaintFinished).length;
  complaintField('complaintUrgent').textContent = complaints.filter(row => !complaintFinished(row) && ['High', 'Urgent'].includes(row.priority)).length;
  const ownerSelect = complaintField('complaintOwnerFilter'), selectedOwner = ownerSelect.value;
  const owners = [...new Set(complaints.map(row => row.assigned_owner).filter(Boolean))].sort();
  if (selectedOwner && !owners.includes(selectedOwner)) owners.push(selectedOwner);
  ownerSelect.replaceChildren(new Option('All owners', ''), ...owners.map(owner => new Option(owner, owner)));
  ownerSelect.value = selectedOwner;
  const search = complaintField('complaintSearch').value.toLowerCase().trim();
  const status = complaintField('complaintStatusFilter').value, priority = complaintField('complaintPriorityFilter').value;
  const rows = complaints.filter(row => (!status || row.status === status) && (!priority || row.priority === priority) &&
    (!selectedOwner || row.assigned_owner === selectedOwner) && (!search || [row.id, row.customer_name, row.subject, row.details, row.record_id, row.resolution].join(' ').toLowerCase().includes(search)))
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  complaintField('complaintResultCount').textContent = 'Showing ' + rows.length + ' of ' + complaints.length + ' complaints. Updates are shared with all CRM users.';
  const body = complaintField('complaintRows');
  body.innerHTML = rows.map(row => '<tr><td><strong>' + complaintText(row.id) + '</strong><div>' + complaintText(row.customer_name) + '</div><div class="tiny">' + complaintText(row.record_id ? row.record_scope + ' · ' + row.record_id : 'No linked record') + '</div></td><td><strong>' + complaintText(row.subject) + '</strong><div class="complaint-notes">' + complaintText(row.details) + '</div></td><td>' + complaintText(row.priority) + '</td><td><span class="complaint-status complaint-status-' + row.status.toLowerCase().replaceAll(' ', '-') + '">' + complaintText(row.status) + '</span></td><td>' + complaintText(row.assigned_owner || 'Unassigned') + '</td><td>' + complaintText(complaintDate(row.created_at)) + '<div class="tiny">Updated: ' + complaintText(complaintDate(row.updated_at)) + '</div></td><td><div class="complaint-notes">' + complaintText(row.resolution || 'Pending resolution') + '</div>' + (row.resolved_at ? '<div class="tiny">Resolved: ' + complaintText(complaintDate(row.resolved_at)) + '</div>' : '') + '</td><td><button class="action-link" type="button" data-complaint-index="' + complaints.indexOf(row) + '">View / Update</button><button class="btn small" type="button" data-complaint-action="' + complaints.indexOf(row) + '">' + (complaintFinished(row) ? 'Reopen' : 'Resolve') + '</button></td></tr>').join('') || '<tr><td colspan="8" class="empty-state">No complaints match these filters. Use + Add Complaint to record an issue.</td></tr>';
  body.querySelectorAll('[data-complaint-index]').forEach(button => {
    button.onclick = () => openComplaintEditor(complaints[Number(button.dataset.complaintIndex)].id);
  });
  body.querySelectorAll('[data-complaint-action]').forEach(button => {
    button.onclick = () => {
      const row = complaints[Number(button.dataset.complaintAction)];
      openComplaintEditor(row.id, complaintFinished(row) ? 'Open' : 'Resolved');
    };
  });
}

function openComplaintsSection() {
  navigate('leads');
  complaintField('complaintsSection').scrollIntoView({behavior: 'smooth', block: 'start'});
}

function openComplaintEditor(id = '', statusOverride = '') {
  if (complaintSaving || dashboardResetting) return;
  const row = id ? complaints.find(item => item.id === id) : null;
  if (id && !row) {toast('This complaint changed. Refresh the list and try again.'); return;}
  complaintField('complaintForm').reset();
  complaintField('complaintEditId').value = row?.id || '';
  complaintField('complaintDialogTitle').textContent = row ? 'Review / Update Complaint' : 'Add Complaint';
  complaintField('complaintReference').textContent = row ? row.id + ' · Reported ' + complaintDate(row.created_at) : 'Save an issue and track it until resolution.';
  for (const [field, key] of [['complaintCustomer', 'customer_name'], ['complaintSubject', 'subject'], ['complaintDetails', 'details'], ['complaintOwner', 'assigned_owner'], ['complaintResolution', 'resolution']]) complaintField(field).value = row?.[key] || '';
  complaintField('complaintStatus').value = statusOverride || row?.status || 'Open';
  complaintField('complaintPriority').value = row?.priority || 'Medium';
  const records = workspaceRecords(), linked = row?.record_id ? JSON.stringify({scope: row.record_scope, id: row.record_id}) : '';
  const select = complaintField('complaintRelatedRecord');
  select.replaceChildren(new Option('No linked record', ''), ...records.map(record => new Option(record.name + ' · ' + record.workspaceLabel + ' · ' + record.id, JSON.stringify({scope: record.workspaceScope, id: record.id}))));
  if (linked && !Array.from(select.options).some(option => option.value === linked)) select.add(new Option(row.customer_name + ' · ' + row.record_id + ' (record no longer active)', linked));
  select.value = linked;
  complaintField('complaintSaveError').textContent = '';
  updateComplaintResolutionRequirement();
  complaintField('complaintDialog').showModal();
  if (statusOverride === 'Resolved') complaintField('complaintResolution').focus();
  else complaintField('complaintSubject').focus();
}

function selectComplaintRecord() {
  const value = complaintField('complaintRelatedRecord').value;
  if (!value) return;
  const link = JSON.parse(value), record = workspaceRecords().find(row => row.workspaceScope === link.scope && row.id === link.id);
  if (record) complaintField('complaintCustomer').value = record.name;
}

function updateComplaintResolutionRequirement() {
  const required = ['Resolved', 'Closed'].includes(complaintField('complaintStatus').value);
  complaintField('complaintResolution').required = required;
  complaintField('complaintResolutionLabel').textContent = required ? 'Resolution notes (required to resolve or close)' : 'Resolution notes';
}

function closeComplaintEditor() {
  if (!complaintSaving) complaintField('complaintDialog').close();
}

async function saveComplaint(event) {
  event.preventDefault();
  if (complaintSaving || dashboardResetting) return;
  updateComplaintResolutionRequirement();
  if (!complaintField('complaintForm').reportValidity()) return;
  const id = complaintField('complaintEditId').value, old = complaints.find(row => row.id === id);
  const now = new Date().toISOString(), status = complaintField('complaintStatus').value;
  const linkValue = complaintField('complaintRelatedRecord').value;
  const link = linkValue ? JSON.parse(linkValue) : {scope: '', id: ''};
  const suffix = globalThis.crypto?.randomUUID?.() || Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 12);
  const row = {id: old?.id || 'CMP-' + suffix, customer_name: complaintField('complaintCustomer').value.trim(),
    subject: complaintField('complaintSubject').value.trim(), details: complaintField('complaintDetails').value.trim(),
    record_scope: link.scope, record_id: link.id, priority: complaintField('complaintPriority').value,
    assigned_owner: complaintField('complaintOwner').value.trim(), status,
    resolution: complaintField('complaintResolution').value.trim(), created_at: old?.created_at || now, updated_at: now,
    resolved_at: ['Resolved', 'Closed'].includes(status) ? old?.resolved_at || now : ''};
  if (!row.customer_name || !row.subject || !row.details || ['Resolved', 'Closed'].includes(status) && !row.resolution) {
    complaintField('complaintSaveError').textContent = 'Complete the complaint details and add resolution notes before resolving or closing it.'; return;
  }
  const next = old ? complaints.map(item => item.id === old.id ? row : item) : [...complaints, row];
  complaintSaving = true; complaintField('complaintSaveButton').disabled = true; complaintField('complaintCancelButton').disabled = true;
  complaintField('complaintSaveError').textContent = '';
  try {
    await writeDashboardValues({hk_v2_complaints: next});
    complaints = next; complaintSaving = false; closeComplaintEditor(); renderComplaints();
    toast(complaintFinished(row) ? 'Complaint saved with resolution details.' : 'Complaint saved for all CRM users.');
  } catch (error) {complaintField('complaintSaveError').textContent = 'Complaint was not saved. ' + error.message;}
  finally {complaintSaving = false; complaintField('complaintSaveButton').disabled = false; complaintField('complaintCancelButton').disabled = false;}
}

document.addEventListener('DOMContentLoaded', () => {
  complaintField('complaintDialog').addEventListener('cancel', event => {if (complaintSaving) event.preventDefault();});
});
