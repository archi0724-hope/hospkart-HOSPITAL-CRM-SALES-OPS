let crmAdminSession = {admin: false, username: null, configured: false};
let adminActivityCursor = null;
let adminLoginBusy = false;
const adminWriteHandlers = /\b(openExcelImport|openDriveImport|loadInvoiceWorkbook|openClientForm|openCallForm|openFeedback|openWorkStatus|openLeadRecordForm|openComplaint|addLeadFromStageEditor|publishBrowserWorkspaceRecovery|resetDashboard|prepareFullBackup|saveSpreadsheetSource|inspectSpreadsheet|loadSpreadsheetColumns|previewSpreadsheet|importSpreadsheetPreview|syncLinkedSpreadsheet|removeSelectedImport|openImportRemoval|submitEmailFollowups|sendWhatsAppApi|scheduleWhatsAppFollowup|saveDrive|removeDrive|attachDrive|importDrive|delete|remove|saveWork|saveClient|saveCall|saveFeedback|saveComplaint)\w*\s*\(/i;

async function adminApi(path, data) {
  const response = await fetch('/api/admin/' + path, {
    method: data === undefined ? 'GET' : 'POST', cache: 'no-store',
    headers: data === undefined ? {} : {'Content-Type': 'application/json'},
    body: data === undefined ? undefined : JSON.stringify(data)
  });
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.error || 'Administrator request failed.');
  return result;
}
function renderAdminAccess() {
  const label = crmAdminSession.admin ? 'Administrator: ' + crmAdminSession.username + ' · Upload, edit and delete enabled.' : 'Viewer mode · Only administrators can upload, edit or delete data.';
  document.getElementById('adminAccessStatus').textContent = label;
  document.getElementById('adminSessionLabel').textContent = label;
  document.getElementById('adminLoginForm').classList.toggle('hidden', crmAdminSession.admin);
  document.getElementById('adminSignedInTools').classList.toggle('hidden', !crmAdminSession.admin);
  document.getElementById('adminAccessButton').textContent = crmAdminSession.admin ? crmAdminSession.username + ' · Activity log' : 'Admin sign-in / Activity log';
  if (typeof updateSheetAdminControls === 'function') updateSheetAdminControls();
  if (!crmAdminSession.admin) document.getElementById('spreadsheetConnectionDialog')?.close();
  // This is a usability cue; authorization is always enforced by the server.
  document.querySelectorAll('button[onclick],input[type=file],.work-color-select,#sheetConnectPanel input,#sheetConnectPanel select').forEach(control => {
    if (!adminWriteHandlers.test(control.getAttribute('onclick') || '') && control.type !== 'file' && !control.matches('.work-color-select,#sheetConnectPanel input,#sheetConnectPanel select')) return;
    if (!crmAdminSession.admin) {
      if (!control.disabled) control.dataset.adminDisabled = '1';
      control.disabled = true;
      control.title = 'Admin sign-in required to change data';
    } else if (control.dataset.adminDisabled) {
      control.disabled = false;
      delete control.dataset.adminDisabled;
      control.removeAttribute('title');
    }
  });
}
async function refreshAdminAccess() {
  try {crmAdminSession = await adminApi('session');}
  catch (_) {crmAdminSession = {admin: false};}
  renderAdminAccess();
}
async function openAdminAccess() {
  document.getElementById('adminAccessDialog').showModal();
  await refreshAdminAccess();
  document.getElementById('adminAccessError').textContent = crmAdminSession.configured ? '' : 'No admin account is configured. Ask the server owner to run set_admin_password.py or manage_admin.py.';
  if (crmAdminSession.admin) await loadAdminActivity();
  else document.getElementById('adminLoginPassword').focus();
}
async function signInAdmin(event) {
  event.preventDefault();
  if (adminLoginBusy) return;
  adminLoginBusy = true;
  document.getElementById('adminSignInButton').disabled = true;
  const password = document.getElementById('adminLoginPassword');
  try {
    await adminApi('login', {username: document.getElementById('adminUsername').value.trim(), password: password.value});
    password.value = '';
    await refreshAdminAccess();
    document.getElementById('adminAccessError').textContent = '';
    await loadAdminActivity();
  } catch (error) {document.getElementById('adminAccessError').textContent = error.message;}
  finally {password.value = ''; adminLoginBusy = false; document.getElementById('adminSignInButton').disabled = false;}
}
async function signOutAdmin() {
  try {
    await adminApi('logout', {});
    document.getElementById('adminActivityRows').replaceChildren();
    await refreshAdminAccess();
  } catch (error) {document.getElementById('adminAccessError').textContent = error.message;}
}
function describeAdminActivity(details) {
  if (!details.operations) return [details.filename, details.note].filter(Boolean).join(' — ');
  return details.operations.map(op => {
    let text = op.action + ': ' + op.table + ' (' + op.rows + ' rows)';
    if (op.changes) text += ' — ' + Object.entries(op.changes).map(([area, change]) => {
      if ('added' in change) return area.replace('hk_v2_', '') + ': ' + change.added + ' added, ' + change.edited + ' edited, ' + change.removed + ' removed' + (change.record_ids.length ? '; IDs ' + change.record_ids.join(', ') : '') + (change.fields.length ? '; fields ' + change.fields.join(', ') : '');
      return area.replace('hk_v2_', '') + ': ' + JSON.stringify(change);
    }).join('; ');
    return text;
  }).join('\n');
}
async function loadAdminActivity(older = false) {
  const rows = document.getElementById('adminActivityRows');
  try {
    const result = await adminApi('activity' + (older && adminActivityCursor ? '?before=' + adminActivityCursor : ''));
    if (!older) rows.replaceChildren();
    for (const item of result.events) {
      const row = document.createElement('tr');
      for (const value of [new Date(item.created_at).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata'}), item.actor, item.action, item.target, describeAdminActivity(item.details), item.outcome]) {
        const cell = document.createElement('td'); cell.textContent = value; cell.style.whiteSpace = 'pre-wrap'; row.append(cell);
      }
      rows.append(row);
    }
    if (!rows.children.length) {const row = rows.insertRow(); const cell = row.insertCell(); cell.colSpan = 6; cell.textContent = 'No recorded activity yet.';}
    adminActivityCursor = result.next_before;
    document.getElementById('adminActivityMore').classList.toggle('hidden', !adminActivityCursor);
  } catch (error) {document.getElementById('adminAccessError').textContent = error.message;}
}
document.addEventListener('click', event => {
  if (crmAdminSession.admin || event.target.closest('#adminAccessDialog')) return;
  const control = event.target.closest('button,a,input[type=file]');
  if (control && (adminWriteHandlers.test(control.getAttribute('onclick') || '') || control.type === 'file')) {
    event.preventDefault(); event.stopImmediatePropagation(); openAdminAccess();
  }
}, true);
document.addEventListener('submit', event => {
  if (!crmAdminSession.admin && !event.target.closest('#adminAccessDialog') && /save|import|reset|submitEmail/i.test(event.target.getAttribute('onsubmit') || '')) {
    event.preventDefault(); event.stopImmediatePropagation(); openAdminAccess();
  }
}, true);
document.addEventListener('DOMContentLoaded', () => {
  new MutationObserver(records => {
    if (records.some(record => [...record.addedNodes].some(node => node.nodeType === 1 && (node.matches('button,input[type=file]') || node.querySelector('button,input[type=file]'))))) renderAdminAccess();
  }).observe(document.querySelector('.content'), {childList: true, subtree: true});
  setInterval(refreshAdminAccess, 60000);
});
