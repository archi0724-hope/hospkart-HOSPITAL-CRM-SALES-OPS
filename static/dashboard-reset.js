let dashboardResetting = false;
let dashboardDataVersion = 0;

async function performDashboardReset() {
  if (dashboardResetting) return;
  if (typeof importRemovalSubmitting !== 'undefined' && importRemovalSubmitting) { toast('Wait for the import removal to finish.'); return; }
  if (!document.getElementById('resetAcknowledge').checked || document.getElementById('resetPhrase').value.trim() !== 'RESET DASHBOARD') {
    toast('Confirm permanent deletion and type RESET DASHBOARD to continue.');
    updateResetButton();
    return;
  }
  if (emailSubmitting) { toast('Wait for the current email request to finish before resetting.'); return; }
  if (quoteSaarthiSubmitting) { toast('Wait for the QuoteSaarthi request to finish before resetting.'); return; }
  dashboardResetting = true;
  dashboardDataVersion++;
  const button = document.getElementById('resetConfirmButton');
  button.disabled = true;
  button.textContent = 'Resetting…';
  let completed = false;
  try {
    const response = await fetch('/api/dashboard/reset', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({confirmed_reset: true, confirmation: 'RESET DASHBOARD'})
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || 'Could not clear server history.');
    await writeDashboardValues({hk_v2_clients:[],hk_v2_calls:[],hk_v2_feedback:[],hk_v2_backups:[],hk_v2_segments:{served:[],doctors:[],potential:[]},hk_v2_rghs:[],hk_v2_leads:[],hk_v2_served:[],hk_v2_doctors:[],hk_v2_potential:[],hk_v2_invoice_workbook:null,hk_v2_reset_revision:String(Date.now())});
    invoiceWorkbook=null;renderInvoiceDashboard();
    clients = [];
    calls = [];
    feedback = [];
    backups = [];
    segmentData = {served: [], doctors: [], potential: []};
    sectionRecords = {rghs: [], leads: [], served: [], doctors: [], potential: []};
    filtered = [];
    quickMode = 'all';
    editingCallIndex = -1;
    editingFeedbackIndex = -1;
    document.querySelectorAll('.drawer.open').forEach(drawer => drawer.classList.remove('open'));
    document.querySelectorAll('form').forEach(form => form.reset());
    for (const id of ['clientEditId', 'feedbackClientId', 'workRecordId', 'workRecordScope', 'leadQuickClientId', 'leadQuickNext', 'leadQuickRemark', 'clientSearch', 'servedSearch', 'doctorSearch', 'potentialSearch', 'sourceDataSearch', 'waPhone', 'waMessage', 'schedulePhone', 'scheduleAt', 'scheduleTemplate', 'scheduleParams', 'emailTo', 'emailAt']) {
      const field = document.getElementById(id);
      if (field) field.value = '';
    }
    for (const id of ['waOptIn', 'scheduleOptIn', 'emailRecipientsConfirmed']) document.getElementById(id).checked = false;
    document.getElementById('emailScope').value = 'all';
    document.getElementById('emailSubject').value = '';
    document.getElementById('emailMessage').value = '';
    document.getElementById('emailResult').textContent = '';
    document.getElementById('chatBody').replaceChildren();
    rememberQuoteSaarthiSession(null);
    addChatMessage('QuoteSaarthi: Select or add a hospital to begin a new follow-up.');
    toggleChat(false);
    closeLeadQuickEditor();
    populateFilters();
    clearFilters();
    document.getElementById('formDate').value = TODAY;
    document.getElementById('feedbackDate').value = TODAY;
    document.getElementById('resetAcknowledge').checked = false;
    document.getElementById('resetPhrase').value = '';
    completed = true;
  } catch (error) {
    toast('Reset could not finish: ' + error.message);
  } finally {
    dashboardDataVersion++;
    dashboardResetting = false;
    button.textContent = 'Clear all dashboard data';
    updateResetButton();
  }
  if (completed) {
    renderAll();
    updateEmailRecipients();
    loadScheduledMessages();
    loadEmailHistory();
    toast('Dashboard reset. All records, saved checkpoints, and follow-up history cleared. No backup was created.');
  }
}

window.addEventListener('storage', event => {
  if (event.key === 'hk_v2_reset_revision' && event.newValue) window.location.reload();
});
