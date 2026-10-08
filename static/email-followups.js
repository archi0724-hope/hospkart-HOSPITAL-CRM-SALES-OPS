let emailSubmitting = false;
let emailSenderReady = false;

function emailFollowupButton(client, purpose = 'auto') {
  return `<button type="button" class="action-link email-followup-link" data-client-id="${escapeHtml(client.id)}" data-purpose="${escapeHtml(purpose)}" title="Prepare an email follow-up for ${escapeHtml(client.name)}" onclick="event.stopPropagation();openEmailForClient(this.dataset.clientId,this.dataset.purpose)">✉ Email follow-up</button>`;
}

function emailFollowupDraft(client, purpose = 'auto') {
  const delivered = ['Delivered', 'Feedback Pending', 'Completed / Served'].includes(client.status);
  if (purpose === 'auto') purpose = delivered ? 'feedback' : isWon(client) ? 'order' : ['Quotation Shared', 'Follow-up Required', 'Negotiation'].includes(client.status) && client.quote > 0 ? 'quotation' : 'requirement';
  if (purpose === 'feedback' && !delivered) purpose = 'order';
  const topic = client.product || client.requirement || 'your requirements';
  const drafts = {
    quotation: {subject: `HOSPkart quotation follow-up — ${client.name}`, message: `We are following up on the quotation for ${topic}. Please let us know if you need any clarification or would like to discuss your requirements further.`},
    order: {subject: `HOSPkart order follow-up — ${client.name}`, message: `We are following up regarding your order for ${topic}. Please let us know if you need an update or any assistance from our team.`},
    feedback: {subject: `HOSPkart feedback follow-up — ${client.name}`, message: `We would appreciate your feedback on ${topic} and your experience with HOSPkart. Please share any comments about the product, delivery, or service, and let us know if you need support.`},
    requirement: {subject: `HOSPkart requirement follow-up — ${client.name}`, message: `We are following up regarding ${topic}. Please share any updated requirements or specifications so our team can assist you.`}
  };
  const draft = drafts[purpose] || drafts.requirement;
  return {subject: draft.subject, message: `Dear ${client.contact || 'Purchase Team'},\n\n${draft.message}\n\nRegards,\nHOSPkart Team`};
}

function openEmailForClient(id, purpose = 'auto') {
  const client = clients.find(item => item.id === id);
  if (!client) { toast('Select a customer before preparing an email follow-up.'); return; }
  if (emailSubmitting) { toast('Please wait for the current email request to finish.'); return; }
  document.querySelectorAll('.drawer.open').forEach(drawer => drawer.classList.remove('open'));
  toggleChat(false);
  navigate('email');
  document.getElementById('emailScope').value = 'one';
  document.getElementById('emailClient').value = id;
  prefillEmailClient();
  const draft = emailFollowupDraft(client, purpose);
  document.getElementById('emailSubject').value = draft.subject.slice(0, 200);
  document.getElementById('emailMessage').value = draft.message;
  const proposedDate = /^\d{4}-\d{2}-\d{2}$/.test(client.next || '') ? client.next + 'T10:00' : '';
  document.getElementById('emailAt').value = proposedDate && Date.parse(proposedDate + '+05:30') > Date.now() ? proposedDate : '';
  document.getElementById('emailResult').textContent = client.email ? 'Review this customer’s message, then send now or choose a schedule.' : 'Add this customer’s email address before sending. Save it in Hospitals & Clients to keep it for future follow-ups.';
  updateEmailRecipients();
  document.getElementById(client.email ? 'emailSubject' : 'emailTo').focus({preventScroll: true});
}

function openEmailDueFollowups() {
  if (emailSubmitting) { toast('Please wait for the current email request to finish.'); return; }
  toggleChat(false);
  navigate('email');
  document.getElementById('emailScope').value = 'due';
  document.getElementById('emailSubject').value = 'HOSPkart follow-up for {{name}}';
  document.getElementById('emailMessage').value = 'Dear {{contact}},\n\nWe are following up on your requirements for {{name}}. Please let us know if you need any further information or assistance from HOSPkart.\n\nRegards,\nHOSPkart Team';
  document.getElementById('emailAt').value = '';
  document.getElementById('emailRecipientsConfirmed').checked = false;
  document.getElementById('emailResult').textContent = 'Review customers whose follow-up dates are today or overdue, then send now or schedule.';
  updateEmailRecipients();
}

function personalizeEmail(text, client) {
  const fields = {...client, contact: client.contact || 'Purchase Team'};
  return text.replace(/\{\{(name|contact|product|requirement)\}\}/g, (_, key) => fields[key] || '');
}

function emailRecipientSelection() {
  const scope = document.getElementById('emailScope').value;
  const today = new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit'}).format(new Date());
  let candidates = clients;
  if (scope === 'due') candidates = clients.filter(client => client.next && client.next <= today && client.status !== 'Lost / Cancelled');
  if (scope === 'one') {
    const selected = clients.find(client => client.id === document.getElementById('emailClient').value);
    candidates = selected ? [{...selected, email: document.getElementById('emailTo').value.trim()}] : [];
  }
  const seen = new Set(), recipients = [], skipped = [];
  candidates.forEach(client => {
    const email = String(client.email || '').trim();
    const local = email.split('@')[0];
    if (email.length > 254 || !/^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$/.test(email) || local.startsWith('.') || local.endsWith('.') || local.includes('..')) {
      skipped.push({name: client.name, reason: 'missing or invalid email'});
    } else if (seen.has(email.toLowerCase())) {
      skipped.push({name: client.name, reason: 'duplicate email'});
    } else {
      seen.add(email.toLowerCase());
      recipients.push({...client, email});
    }
  });
  return {recipients, skipped};
}

function updateEmailRecipients() {
  document.getElementById('emailSingleFields').classList.toggle('hidden', document.getElementById('emailScope').value !== 'one');
  const {recipients, skipped} = emailRecipientSelection();
  document.getElementById('emailRecipientCount').textContent = `${recipients.length} recipients`;
  document.getElementById('emailSkipped').textContent = skipped.length ? `${skipped.length} skipped: ${skipped.map(row => `${row.name} (${row.reason})`).join('; ')}` : 'Customers without a valid email address are skipped. Duplicate addresses receive one email per batch.';
  document.getElementById('emailRecipientRows').innerHTML = recipients.length ? recipients.map(client => `<tr><td>${escapeHtml(client.name)}</td><td>${escapeHtml(client.email)}</td></tr>`).join('') : '<tr><td colspan="2" class="empty-state">No customers with valid email addresses. Add email addresses in Hospitals &amp; Clients.</td></tr>';
  const first = recipients[0];
  document.getElementById('emailPreviewSubject').textContent = first ? personalizeEmail(document.getElementById('emailSubject').value, first) : '';
  document.getElementById('emailPreviewMessage').textContent = first ? personalizeEmail(document.getElementById('emailMessage').value, first) : '';
  document.getElementById('emailSendButton').disabled = emailSubmitting || !emailSenderReady || !recipients.length;
  document.getElementById('emailScheduleButton').disabled = emailSubmitting || !emailSenderReady || !recipients.length;
}

function prefillEmailClient() {
  const selected = clients.find(client => client.id === document.getElementById('emailClient').value);
  document.getElementById('emailTo').value = selected?.email || '';
  document.getElementById('emailRecipientsConfirmed').checked = false;
  updateEmailRecipients();
}

async function emailApi(path, options) {
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.error || 'Email request failed.');
  return result;
}

async function refreshEmailPage() {
  const select = document.getElementById('emailClient'), previous = select.value;
  select.innerHTML = '<option value="">Select a customer</option>' + clients.map(client => `<option value="${escapeHtml(client.id)}">${escapeHtml(client.name)}</option>`).join('');
  select.value = previous;
  updateEmailRecipients();
  try {
    const health = await emailApi('/api/health');
    emailSenderReady = health.email_configured;
    document.getElementById('emailHealth').textContent = !emailSenderReady ? 'Email sender setup required. Configure the sender account in the private .env file using the README email setup instructions, then restart the server.' : `Email sender configured. Send now queues individual emails for sending within 15 seconds. Scheduled sending is ${health.email_automation_enabled ? 'enabled' : 'paused'}. The local server must remain running.`;
  } catch (error) {
    emailSenderReady = false;
    document.getElementById('emailHealth').textContent = error.message;
  }
  updateEmailRecipients();
  await loadEmailHistory();
}

async function submitEmailFollowups(action) {
  if (dashboardResetting) { toast('Wait for the reset to finish.'); return; }
  if (emailSubmitting) return;
  const {recipients} = emailRecipientSelection();
  const subject = document.getElementById('emailSubject').value.trim(), message = document.getElementById('emailMessage').value.trim();
  const scheduledAt = document.getElementById('emailAt').value;
  if (!recipients.length || !subject || !message) { toast('Choose recipients and enter a subject and message.'); return; }
  if (!document.getElementById('emailRecipientsConfirmed').checked) { toast('Review and confirm the email recipients first.'); return; }
  if (action === 'schedule' && (!scheduledAt || Date.parse(scheduledAt + '+05:30') <= Date.now())) { toast('Choose a future date and time in India time.'); return; }
  if (!confirm(`${action === 'send' ? 'Queue emails now' : 'Schedule emails for ' + scheduledAt.replace('T', ' ') + ' India time'} for ${recipients.length} customers? Each receives a separate email.`)) return;
  emailSubmitting = true;
  updateEmailRecipients();
  try {
    const result = await emailApi('/api/email/' + action, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({subject, message, scheduled_at: scheduledAt, confirmed_recipients: true, recipients: recipients.map(({name, email, contact, product, requirement}) => ({name, email, contact, product, requirement}))})
    });
    const status = `${result.queued} email follow-ups ${action === 'send' ? 'queued for sending' : 'scheduled'}.${result.skipped.length ? ' ' + result.skipped.length + ' recipients skipped.' : ''}${action === 'schedule' && !result.automation_enabled ? ' Scheduled sending is paused until enabled in the sender settings.' : ''}`;
    document.getElementById('emailResult').textContent = status;
    document.getElementById('emailRecipientsConfirmed').checked = false;
    toast(status);
    await loadEmailHistory();
  } catch (error) {
    document.getElementById('emailResult').textContent = error.message;
    toast(error.message);
  } finally {
    emailSubmitting = false;
    updateEmailRecipients();
  }
}

async function loadEmailHistory() {
  const version = dashboardDataVersion;
  if (dashboardResetting) return;
  const rows = document.getElementById('emailHistoryRows');
  try {
    const result = await emailApi('/api/email/followups');
    if (dashboardResetting || version !== dashboardDataVersion) return;
    await syncEmailWorkStatus(result.items);
    document.getElementById('emailHistorySummary').textContent = (Object.entries(result.counts).map(([status, count]) => `${count} ${status}`).join(' · ') || 'No email follow-ups yet.') + ' — Accepted means the email server accepted the message; delivery is not confirmed. Showing the latest 200.';
    rows.innerHTML = result.items.length ? result.items.map(job => `<tr><td>${escapeHtml(job.client_name || '—')}</td><td>${escapeHtml(job.email)}</td><td>${escapeHtml(job.subject)}</td><td>${escapeHtml(new Date(job.scheduled_at).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata'}))}</td><td>${escapeHtml(job.status)}</td><td>${escapeHtml(job.last_error || (job.status === 'sending' ? 'If the server restarted, check the sender outbox before scheduling again.' : '—'))}</td><td>${job.status === 'pending' ? `<button class="action-link" onclick="cancelEmailFollowup(${job.id})">Cancel</button>` : '—'}</td></tr>`).join('') : '<tr><td colspan="7" class="empty-state">No email follow-ups yet.</td></tr>';
  } catch (error) {
    if (dashboardResetting || version !== dashboardDataVersion) return;
    rows.innerHTML = `<tr><td colspan="7" class="empty-state">${escapeHtml(error.message)}</td></tr>`;
  }
}

async function cancelEmailFollowup(id) {
  try {
    const result = await emailApi('/api/email/followups/' + id, {method: 'DELETE'});
    toast(result.updated ? 'Email follow-up cancelled.' : 'This email is already being processed.');
    await loadEmailHistory();
  } catch (error) { toast(error.message); }
}

setInterval(() => { if (currentView === 'email' && !emailSubmitting) loadEmailHistory(); }, 15000);
