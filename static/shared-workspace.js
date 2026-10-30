// All dashboard workspaces, uploaded sheets and checkpoints share one SQLite state.
const sharedWorkspaceEnabled = true;
let sharedWorkspaceRevision = 0;
let sharedWorkspaceInitialized = false;
let sharedWorkspaceExternalEpoch = 0;
let sharedWorkspaceSaving = 0;
let sharedWorkspacePolling = false;
let sharedWorkspaceTimer = null;
let browserWorkspaceRecovery = null;

async function workspaceRequest(data, conditional = false, cachedVersion = null) {
  const query = cachedVersion ? '?'+new URLSearchParams({revision:cachedVersion.revision,updated_at:cachedVersion.updated_at}) : conditional ? '?revision='+sharedWorkspaceRevision : '';
  const response = await fetch('/api/workspace' + query, {
    method: data === undefined ? 'GET' : 'POST', cache: 'no-store',
    headers: data === undefined ? {} : {'Content-Type': 'application/json', 'X-CRM-Request': '1'},
    body: data === undefined ? undefined : JSON.stringify(data), signal: AbortSignal.timeout(30000)
  });
  const result = await response.json().catch(() => ({error: 'The database server returned an unreadable response.'}));
  if (!response.ok || !result.ok) {
    const error = new Error(result.error || 'The shared database could not be reached.');
    error.status = response.status; error.workspace = result.workspace; throw error;
  }
  return result;
}

function workspaceStatus(message) {
  const status = document.getElementById('sharedDatabaseStatus');
  if (status) status.textContent = message;
}

function parsedBrowserValues() {
  return Object.fromEntries([...dashboardStorage].filter(([key]) => dashboardKeys.includes(key)).map(([key, raw]) => {
    if (!readableLegacyRecord(key, raw)) throw new Error('Some saved browser data is unreadable. Its original copy has been retained.');
    return [key, JSON.parse(raw)];
  }));
}

function completeBrowserValues(values) {
  const result = {...values};
  result.hk_v2_clients ||= []; result.hk_v2_calls ||= []; result.hk_v2_feedback ||= [];
  result.hk_v2_complaints ||= [];
  result.hk_v2_backups ||= []; result.hk_v2_segments ||= {served: [], doctors: [], potential: []};
  const legacy = {
    rghs: result.hk_v2_clients.filter(row => /rghs/i.test(JSON.stringify(row))).map((row, index) => ({...row, id: 'HK-R' + String(index + 1).padStart(4, '0')})),
    leads: result.hk_v2_clients.filter(row => !['Completed / Served', 'Lost / Cancelled', 'Delivered'].includes(row.status)).map((row, index) => ({...row, id: 'HK-L' + String(index + 1).padStart(4, '0')}))
  };
  for (const scope of ['rghs', 'leads', 'served', 'doctors', 'potential']) result['hk_v2_' + scope] ||= legacy[scope] || result.hk_v2_segments[scope] || [];
  result.hk_v2_segments = Object.fromEntries(['served', 'doctors', 'potential'].map(scope => [scope, result['hk_v2_' + scope]]));
  result.hk_v2_invoice_workbook ??= null; result.hk_v2_reset_revision ||= '';
  return result;
}

function hasBrowserBusinessData(values) {
  return ['clients', 'calls', 'feedback', 'complaints', 'rghs', 'leads', 'served', 'doctors', 'potential', 'backups'].some(key => values['hk_v2_' + key]?.length) || !!values.hk_v2_invoice_workbook || !!values.hk_v2_reset_revision;
}

function browserValuesCheckpoint(values) {
  if (values.__raw_browser_records) throw new Error('Some preserved records are unreadable. Download the raw recovery file before repairing them.');
  const complete = completeBrowserValues(values);
  return {id: 'browser-recovery-' + Date.now(), createdAt: new Date().toISOString(), reason: 'Preserved browser records',
    clients: complete.hk_v2_clients, calls: complete.hk_v2_calls, feedback: complete.hk_v2_feedback,
    complaints: complete.hk_v2_complaints,
    segments: complete.hk_v2_segments, sections: Object.fromEntries(['rghs', 'leads', 'served', 'doctors', 'potential'].map(scope => [scope, complete['hk_v2_' + scope]])),
    invoiceWorkbook: complete.hk_v2_invoice_workbook};
}

async function preserveBrowserWorkspace(values, reason, visible = true) {
  browserWorkspaceRecovery = {values, reason, visible, createdAt: new Date().toISOString()};
  if (browserCacheReady) {
    try {await databaseTransaction({hk_browser_recovery_v1: JSON.stringify(browserWorkspaceRecovery)});}
    catch (_) { browserCacheReady = false; /* Keep the original IndexedDB records untouched. */ }
  }
  const notice = document.getElementById('sharedRecoveryNotice');
  if (notice) {notice.classList.toggle('hidden', !visible); document.getElementById('sharedRecoveryReason').textContent = reason;}
}

function downloadBrowserWorkspaceRecovery() {
  if (!browserWorkspaceRecovery) return;
  let contents;
  try {contents = browserValuesCheckpoint(browserWorkspaceRecovery.values);}
  catch (_) {contents = browserWorkspaceRecovery;}
  const url = URL.createObjectURL(new Blob([JSON.stringify(contents, null, 2)], {type: 'application/json'}));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'HOSPkart_Preserved_Browser_Data_' + new Date().toISOString().slice(0, 10) + '.json';
  document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function publishBrowserWorkspaceRecovery() {
  if (!browserWorkspaceRecovery || !dashboardReady) return;
  try {
    const checkpoint = validateCheckpoint(browserValuesCheckpoint(browserWorkspaceRecovery.values));
    if (!await askImportConfirmation('Restore these preserved browser records to the shared CRM for EVERY user? This replaces the current shared dashboard after saving a checkpoint. Review the downloaded copy first.')) return;
    await applyDashboardCheckpoint(checkpoint, 'Before restoring preserved browser data to shared database');
    toast('Preserved browser records saved to the shared database for all users.');
  } catch (error) {toast('Restore was not saved: ' + error.message);}
}

async function acceptWorkspaceState(state, external = false, cached = false) {
  if (!state || state.revision < sharedWorkspaceRevision) return false;
  if (external && state.revision !== sharedWorkspaceRevision) sharedWorkspaceExternalEpoch++;
  sharedWorkspaceRevision = state.revision; sharedWorkspaceInitialized = state.initialized;
  for (const key of cached ? [] : dashboardKeys) {
    if (Object.prototype.hasOwnProperty.call(state.values, key)) dashboardStorage.set(key, JSON.stringify(state.values[key]));
  }
  // Commit the version and records together so an interrupted cache write cannot
  // mark an incomplete browser copy as current.
  if (!cached) await cacheDashboardRecords(state.values, {
    hk_shared_connection_v1: window.location.origin,
    hk_shared_version_v1: JSON.stringify({revision:state.revision,updated_at:state.updated_at})
  });
  workspaceStatus('Shared database connected · All users on this CRM share saved records · Revision ' + state.revision);
  window.dispatchEvent(new CustomEvent('crm:workspace-saved',{detail:{revision:state.revision}}));
  return true;
}

async function initializeDashboardStorage() {
  await Promise.all([refreshAdminAccess(), initializeBrowserCache()]);
  let local = {}, previousSharedCache = false, savedVersion = null;
  if (browserCacheReady) {
    const transaction = dashboardDatabase.transaction('records', 'readonly');
    await new Promise(resolve => {
      const records = transaction.objectStore('records'), marker = records.get('hk_shared_connection_v1'), recovery = records.get('hk_browser_recovery_v1'), version = records.get('hk_shared_version_v1');
      marker.onsuccess = () => {previousSharedCache = marker.result === window.location.origin;};
      recovery.onsuccess = () => {try {browserWorkspaceRecovery = JSON.parse(recovery.result);} catch (_) {}};
      version.onsuccess = () => {try {savedVersion = JSON.parse(version.result);} catch (_) {}};
      transaction.oncomplete = resolve; transaction.onabort = resolve;
    });
  }
  try {local = parsedBrowserValues();}
  catch (error) {
    browserStorageNotice(error.message);
    await preserveBrowserWorkspace({__raw_browser_records: Object.fromEntries(dashboardStorage)}, 'Unreadable browser data was preserved. Download it for recovery; shared records will load separately.');
  }
  if (browserWorkspaceRecovery) await preserveBrowserWorkspace(browserWorkspaceRecovery.values, browserWorkspaceRecovery.reason, browserWorkspaceRecovery.visible !== false);
  try {
    let cachedVersion = null;
    try {
      const version = savedVersion;
      if (previousSharedCache && dashboardKeys.every(key => Object.hasOwn(local,key)) &&
          Number.isInteger(version?.revision) && typeof version.updated_at === 'string') cachedVersion = version;
    } catch (_) {}
    let result = await workspaceRequest(undefined, false, cachedVersion);
    const verifiedCache = !!(result.unchanged && cachedVersion);
    if (verifiedCache) result.workspace = {
      revision:cachedVersion.revision,updated_at:cachedVersion.updated_at,
      initialized:result.initialized,values:local
    };
    const hasLocal = hasBrowserBusinessData(local);
    if (!result.workspace.initialized && hasLocal && crmAdminSession.can_edit) {
      await preserveBrowserWorkspace(local, 'Your previous browser records were preserved before moving to the shared database.');
      try {
        result = await workspaceRequest({revision: result.workspace.revision, values: completeBrowserValues(local), initialize_only: true});
        await preserveBrowserWorkspace(local, 'Your previous browser records were successfully moved to the shared database. A recovery copy is retained.', false);
      } catch (error) {
        if (error.status === 409 && error.workspace) result = {workspace: error.workspace};
        else if (error.status === 400 || error.status === 413) browserStorageNotice('Previous browser records could not be migrated automatically. Download the preserved copy for review. ' + error.message);
        else throw error;
      }
    } else if (hasLocal && !previousSharedCache) {
      await preserveBrowserWorkspace(local, 'This browser has older local records. The shared database was loaded; download your preserved copy before deciding whether to restore it for everyone.');
    }
    await acceptWorkspaceState(result.workspace, false, verifiedCache);
    dashboardReady = true;
  } catch (error) {
    dashboardReady = false;
    if (error.status === 403) {
      workspaceStatus('Shared database responded, but this page was not permitted to save.');
      browserStorageNotice('Your browser data is preserved. Saving from ' + window.location.origin + ' was rejected by the server address check. Open the CRM using its server link; HTTPS proxies must preserve the public Host or be configured as trusted. ' + error.message);
    } else {
      workspaceStatus('Shared database unavailable · Changes cannot be saved until it reconnects.');
      browserStorageNotice('The shared database could not be reached. Your browser copy is kept for recovery and export. Reload after the connection is restored. ' + error.message);
    }
  }
}

function restoreSharedDashboardModels() {
  const selection = Object.fromEntries(['statusFilter', 'cityFilter', 'executiveFilter', 'clientTypeFilter'].map(id => [id, document.getElementById(id).value]));
  clients = load('hk_v2_clients', []); calls = load('hk_v2_calls', []); feedback = load('hk_v2_feedback', []); backups = load('hk_v2_backups', []);
  complaints = load('hk_v2_complaints', []);
  sectionRecords = Object.fromEntries(['rghs', 'leads', 'served', 'doctors', 'potential'].map(scope => [scope, load('hk_v2_' + scope, [])]));
  segmentData = Object.fromEntries(['served', 'doctors', 'potential'].map(scope => [scope, sectionRecords[scope]]));
  invoiceWorkbook = JSON.parse(dashboardStorage.get('hk_v2_invoice_workbook') || 'null');
  dashboardDataVersion++;
  populateFilters();
  for (const [id, value] of Object.entries(selection)) {
    const select = document.getElementById(id);
    if (value && !Array.from(select.options).some(option => option.value === value)) select.add(new Option(value, value));
    select.value = value;
  }
  renderAll();
}

function commitDashboardRecords(values) {
  const pending = JSON.parse(JSON.stringify(values)), epoch = sharedWorkspaceExternalEpoch;
  sharedWorkspaceSaving++;
  const operation = dashboardWriteQueue.then(async () => {
    try {
      if (!crmAdminSession.can_edit) throw new Error('Data changes are unavailable until the server reconnects.');
      if (!dashboardReady) throw new Error('The shared database is unavailable. These changes were not saved.');
      if (epoch !== sharedWorkspaceExternalEpoch) throw new Error('Shared records changed while this operation was waiting. Review the refreshed records and retry.');
      const result = await workspaceRequest({revision: sharedWorkspaceRevision, values: pending, response: 'changes'});
      await acceptWorkspaceState(result.workspace);
      dashboardChanges?.postMessage('saved');
    } catch (error) {
      let recovery = {};
      try {recovery = parsedBrowserValues();} catch (_) {}
      await preserveBrowserWorkspace({...recovery, ...pending}, 'These changes were not saved. ' + error.message);
      if (error.workspace) {
        await acceptWorkspaceState(error.workspace, true);
        restoreSharedDashboardModels();
      }
      workspaceStatus('Save failed · Last saved shared data is kept · Download your preserved unsaved copy.');
      throw error;
    }
  }).finally(() => {sharedWorkspaceSaving--;});
  dashboardWriteQueue = operation.catch(() => {});
  return operation;
}

function sharedDashboardIsBusy() {
  return sharedWorkspaceSaving || dashboardResetting || (typeof sheetBusy !== 'undefined' && sheetBusy) ||
    (typeof driveImportBusy !== 'undefined' && driveImportBusy) ||
    importRemovalSubmitting || document.querySelector('.drawer.open, dialog[open], #importConfirm:not(.hidden)') ||
    ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName);
}

async function refreshSharedWorkspace(force = false) {
  if (!dashboardReady || !force && (sharedWorkspacePolling || document.hidden || sharedDashboardIsBusy())) return;
  sharedWorkspacePolling = true;
  const startedRevision = sharedWorkspaceRevision;
  try {
    const result = await workspaceRequest(undefined, true);
    if (result.workspace && (force || !sharedDashboardIsBusy()) && result.workspace.revision > sharedWorkspaceRevision) {
      await acceptWorkspaceState(result.workspace, true);
      restoreSharedDashboardModels();
    } else if (result.unchanged || startedRevision === sharedWorkspaceRevision) {
      workspaceStatus('Shared database connected · All users on this CRM share saved records · Revision ' + sharedWorkspaceRevision);
    }
  } catch (_) {workspaceStatus('Shared database temporarily unavailable · Last saved data is kept.');}
  finally {sharedWorkspacePolling = false;}
}

function startSharedWorkspaceRefresh() {
  clearInterval(sharedWorkspaceTimer);
  sharedWorkspaceTimer = setInterval(() => refreshSharedWorkspace(), 5000);
  window.addEventListener('focus', () => refreshSharedWorkspace());
}
