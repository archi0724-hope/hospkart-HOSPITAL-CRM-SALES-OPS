// Keep navigation available during an outage without claiming unavailable counts are zero.
function renderDashboardAvailability() {
  if (document.body.inert || typeof dashboardReady === 'undefined') return;
  let banner = document.getElementById('databaseOfflineBanner');
  if (dashboardReady) {if (banner) banner.remove(); return;}
  let cached = false;
  try {cached = hasBrowserBusinessData(parsedBrowserValues());} catch (_) {}
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'databaseOfflineBanner';banner.className = 'danger-warning';banner.setAttribute('role', 'status');
    const message = document.createElement('p');message.id = 'databaseOfflineMessage';banner.appendChild(message);
    const retry = document.createElement('button');retry.type = 'button';retry.className = 'btn';retry.textContent = 'Retry connection';
    retry.addEventListener('click', () => window.location.reload());banner.appendChild(retry);
    document.querySelector('main .content')?.prepend(banner);
  }
  document.getElementById('databaseOfflineMessage').textContent = cached
    ? 'Database offline · Showing this browser’s saved copy. It may be out of date. Changes and sync are unavailable.'
    : 'Database offline · Saved records and counts are unavailable. Navigation is available; changes and sync are disabled.';
  const notice = document.getElementById('browserStorageNotice');
  if (notice?.textContent.startsWith('The shared database could not be reached.')) notice.classList.add('hidden');
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
