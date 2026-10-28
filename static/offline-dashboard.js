// Keep navigation available during an outage without claiming unavailable counts are zero.
function renderDashboardAvailability() {
  if (document.body.inert || typeof dashboardReady === 'undefined') return;
  let banner = document.getElementById('databaseOfflineBanner');
  document.body.classList.toggle('database-offline', !dashboardReady);
  if (dashboardReady) {if (banner) banner.remove(); return;}
  let cached = false;
  try {cached = hasBrowserBusinessData(parsedBrowserValues());} catch (_) {}
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'databaseOfflineBanner';banner.className = 'database-status-note';banner.setAttribute('role', 'status');
    const message = document.createElement('p');message.id = 'databaseOfflineMessage';banner.appendChild(message);
    const retry = document.createElement('button');retry.type = 'button';retry.className = 'btn';retry.textContent = 'Retry connection';
    retry.addEventListener('click', () => window.location.reload());banner.appendChild(retry);
    document.querySelector('main .content')?.prepend(banner);
  }
  document.getElementById('databaseOfflineMessage').textContent = cached
    ? 'Offline · Showing this browser’s saved copy, which may be out of date. Editing and sync are unavailable.'
    : 'Offline · Saved records and counts are unavailable. Editing and sync are disabled.';
  const restore = document.querySelector('#sharedRecoveryNotice button[onclick="publishBrowserWorkspaceRecovery()"]');
  if (restore) {restore.disabled = true;restore.title = 'Restore becomes available after the database reconnects.';}
  const reason = document.getElementById('sharedRecoveryReason');
  if (reason?.textContent.startsWith('These changes were not saved.')) reason.textContent = 'Unsaved changes are preserved on this device. Download a copy; restore is unavailable while offline.';
  const notice = document.getElementById('browserStorageNotice');
  if (notice?.textContent.startsWith('The shared database could not be reached.')) notice.classList.add('hidden');
  if (typeof renderIntelligence === 'function' && (!intelligenceSnapshot || intelligenceSnapshot.offline_copy)) renderIntelligence(null,true);
  if (!cached) {
    document.querySelectorAll('.kpi .value,.summary-box b,.nav-count').forEach(node => {node.textContent = '—';});
    document.querySelectorAll('.empty-state').forEach(node => {node.textContent = 'Saved records are unavailable while the database is offline.';});
  }
}
document.addEventListener('DOMContentLoaded', () => {
  const render = window.renderAll;
  if (typeof render === 'function') window.renderAll = function (...args) {const result = render.apply(this,args);renderDashboardAvailability();return result;};
  new MutationObserver(renderDashboardAvailability).observe(document.body, {attributes: true, attributeFilter: ['inert']});
  renderDashboardAvailability();
  setInterval(async () => {
    if (document.hidden || dashboardReady) return;
    try {
      const response = await fetch('/api/health', {cache: 'no-store',signal:AbortSignal.timeout(15000)});
      if (response.ok && (await response.json()).database_connected) window.location.reload();
    } catch (_) {}
  },60000);
});
