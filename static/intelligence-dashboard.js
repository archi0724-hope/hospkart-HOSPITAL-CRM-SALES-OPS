let intelligenceSnapshot = null;
let intelligenceRefreshTimer = null;
const workspaceCommands = [
  {label:'Dashboard overview', detail:'All workspaces, pipeline and intelligence', view:'dashboard', symbol:'◈'},
  {label:'Hospitals & clients', detail:'Hospital and customer records', view:'clients', symbol:'▦'},
  {label:'Leads & queries', detail:'Lead board, queries and complaints', view:'leads', symbol:'◎'},
  {label:'Calling & follow-up', detail:'Saved follow-up queues and calling notes', view:'calling', symbol:'◷'},
  {label:'Quotations', detail:'Review your quotation pipeline', view:'quotes', symbol:'₹'},
  {label:'Orders', detail:'Confirmed orders and delivery status', view:'orders', symbol:'✓'},
  {label:'RGHS data', detail:'Your RGHS workspace', view:'rghs', symbol:'▦'},
  {label:'Already served', detail:'Service entries and invoice records', view:'served', symbol:'✓'},
  {label:'Doctors', detail:'Doctor contacts and requirements', view:'doctors', symbol:'+'},
  {label:'Potential leads', detail:'Follow-up opportunities', view:'potential', symbol:'↗'},
  {label:'Feedback', detail:'Customer feedback and ratings', view:'feedback', symbol:'☆'},
  {label:'WhatsApp automation', detail:'Messaging controls and delivery status', view:'whatsapp', symbol:'◌'},
  {label:'Email follow-ups', detail:'Saved email schedules', view:'email', symbol:'✉'},
  {label:'Reports & export', detail:'Review reports and download data', view:'reports', symbol:'↗'},
  {label:'Data & backups', detail:'Imports, checkpoints and recovery', view:'data', symbol:'▤'},
  {label:'Ask QuoteSaarthi', detail:'A brief based on the latest saved CRM', prompt:'Summarize CRM dashboard', symbol:'✦'}
];
function askIntelligence(message) {
  toggleChat(true);
  if (quoteSaarthiSubmitting) {toast('QuoteSaarthi is finishing your current answer.'); return;}
  quickChat(message);
}
function openWorkspaceCommands() {
  const dialog = document.getElementById('workspaceCommandDialog');
  if (!dialog.open) dialog.showModal();
  document.getElementById('workspaceCommandInput').value = '';
  renderWorkspaceCommands();
  document.getElementById('workspaceCommandInput').focus();
}
function renderWorkspaceCommands() {
  const query = document.getElementById('workspaceCommandInput').value.trim();
  const matches = workspaceCommands.filter(item => (item.label + ' ' + item.detail).toLowerCase().includes(query.toLowerCase()));
  const root = document.getElementById('workspaceCommandResults');
  root.replaceChildren();
  const options = query ? [...matches, {label:'Ask QuoteSaarthi', detail:query, prompt:query, symbol:'✦'}] : matches;
  for (const item of options) {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'workspace-command-option';
    const icon = document.createElement('span'); icon.className = 'command-option-icon'; icon.textContent = item.symbol; icon.setAttribute('aria-hidden','true');
    const copy = document.createElement('span');
    const title = document.createElement('strong'); title.textContent = item.label;
    const detail = document.createElement('small'); detail.textContent = item.detail;
    copy.append(title,detail);
    const arrow = document.createElement('span'); arrow.textContent = '↗'; arrow.setAttribute('aria-hidden','true');
    button.append(icon,copy,arrow);
    button.addEventListener('click', () => {
      document.getElementById('workspaceCommandDialog').close();
      if (item.view) navigate(item.view); else askIntelligence(item.prompt);
    });
    root.append(button);
  }
}
function workspaceCommandKeydown(event) {
  if (event.key === 'Escape') {event.preventDefault(); event.stopPropagation(); document.getElementById('workspaceCommandDialog').close(); return;}
  if (event.key === 'Enter') {event.preventDefault(); document.querySelector('#workspaceCommandResults button')?.click();}
  if (event.key === 'ArrowDown') {event.preventDefault(); document.querySelector('#workspaceCommandResults button')?.focus();}
}
function renderIntelligence(snapshot, unavailable = false) {
  const source = document.getElementById('intelligenceSource');
  const dot = document.getElementById('intelligenceSourceDot');
  if (!source) return;
  if (!snapshot || unavailable) {
    for (const id of ['intelligenceOverdue','intelligenceToday','intelligenceComplaints']) document.getElementById(id).textContent = '—';
    source.textContent = 'Saved CRM insights unavailable'; dot.classList.remove('connected');
    document.getElementById('intelligenceBrief').textContent = 'The latest data could not be checked. Refresh insights to retry; your saved records are retained.';
    document.getElementById('intelligenceScope').textContent = 'No current insight snapshot available. Values have not been assumed.';
    return;
  }
  intelligenceSnapshot = snapshot;
  const counts = snapshot.followup_counts;
  const pending = Object.entries(snapshot.complaint_status_counts).reduce((sum,[status,count]) => sum + (['Resolved','Closed'].includes(status) ? 0 : count),0);
  document.getElementById('intelligenceOverdue').textContent = counts.overdue.toLocaleString('en-IN');
  document.getElementById('intelligenceToday').textContent = counts.due_today.toLocaleString('en-IN');
  document.getElementById('intelligenceComplaints').textContent = pending.toLocaleString('en-IN');
  source.textContent = 'Saved CRM connected · revision ' + snapshot.revision; dot.classList.add('connected');
  const issues = snapshot.checks?.issues?.length || 0;
  let brief = counts.overdue ? counts.overdue + ' overdue follow-ups need review. Start with the follow-up queue.' : counts.due_today ? counts.due_today + ' follow-ups are due today. Review your scheduled conversations.' : snapshot.workspace_records ? 'No overdue or due-today follow-ups are recorded. Explore your pipeline or ask for a CRM brief.' : 'Your workspace is ready. Import a workbook or add your first hospital to get started.';
  if (pending) brief += ' ' + pending + ' complaints are still open.';
  if (issues) brief += ' Review ' + issues + ' data-check issue categories.';
  document.getElementById('intelligenceBrief').textContent = brief;
  const checked = new Date(snapshot.checked_at).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit'});
  document.getElementById('intelligenceScope').textContent = 'All saved workspaces · checked ' + checked + ' IST · independent of filters · follow-ups include closed records with saved dates.';
}
async function refreshIntelligence(force = false) {
  if (!force && document.hidden) return;
  const button = document.getElementById('intelligenceRefresh');
  if (button) button.disabled = true;
  try {await refreshQuoteSaarthiKnowledge();}
  finally {if (button) button.disabled = false;}
}
window.addEventListener('quotesaarthi:knowledge', event => renderIntelligence(event.detail));
window.addEventListener('quotesaarthi:unavailable', () => renderIntelligence(null,true));
window.addEventListener('crm:workspace-saved', () => {
  clearTimeout(intelligenceRefreshTimer);
  intelligenceRefreshTimer = setTimeout(() => refreshIntelligence(),450);
});
document.addEventListener('keydown', event => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k' && !document.querySelector('dialog[open],.drawer.open')) {
    event.preventDefault(); openWorkspaceCommands();
  }
});
document.addEventListener('visibilitychange', () => {if (!document.hidden) refreshIntelligence();});
document.addEventListener('DOMContentLoaded', () => {
  refreshIntelligence(true);
  setInterval(() => {if (document.getElementById('page-dashboard').classList.contains('active')) refreshIntelligence();},60000);
});
