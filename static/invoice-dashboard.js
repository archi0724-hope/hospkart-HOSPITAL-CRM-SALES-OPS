let invoiceWorkbook = null;
let invoiceVisibleRows = [];
const invoiceNumber = value => value == null || String(value).trim() === '' ? null : Number(String(value).replace(/[^0-9.-]/g, ''));
const invoiceKey = row => String(row['Invoice No.'] || '').trim().toLowerCase();
const invoiceClientKey = row => [row['Client / Hospital'], row['Delivery City / Location']].map(value => String(value || '').trim().toLowerCase()).join('|');
function invoiceSheet(name) { return invoiceWorkbook?.sheets.find(sheet => sheet.name === name)?.rows || []; }
function isInvoiceWorkbook(workbook) { return workbook.sheets.some(sheet => sheet.name === 'Client Summary' && sheet.rows.some(row => invoiceKey(row) && row['Client / Hospital'])); }
function uniqueInvoices(rows) { const seen = new Map(); rows.forEach(row => { if (invoiceKey(row) && !seen.has(invoiceKey(row))) seen.set(invoiceKey(row), row); }); return [...seen.values()]; }
function invoiceDate(value) { const date = new Date(value); return Number.isNaN(date.getTime()) ? '' : `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`; }
function invoiceClientRecords(workbook) {
  const rows = workbook.sheets.find(sheet => sheet.name === 'Client Summary')?.rows || [], groups = new Map();
  uniqueInvoices(rows).filter(row => !/cancel/i.test(row['Invoice Status'] || '')).forEach(row => {
    const key = invoiceClientKey(row); if (!groups.has(key)) groups.set(key, []); groups.get(key).push(row);
  });
  return [...groups.values()].map((invoices, index) => {
    const row = invoices[0], total = invoices.reduce((sum, entry) => sum + (invoiceNumber(entry['Invoice Total (₹)']) || 0), 0);
    return {id: `HK-S${String(index+1).padStart(4,'0')}`, name: String(row['Client / Hospital']), city: String(row['Delivery City / Location'] || ''), district: '', state: '', type: invoices.length > 1 ? 'Repeat Client' : 'Previously Served Client', contact: '', mobile: String(invoices.find(entry => entry['Client Phone'])?.['Client Phone'] || ''), email: '', requirement: String(row['Next Requirement'] || ''), product: [...new Set(invoices.map(entry => entry['Items Purchased']).filter(Boolean))].join('; '), status: 'Feedback Pending', quote: 0, order: total, last: '', next: invoiceDate(row['Follow-up Date']), executive: '', remark: String(row['Notes'] || ''), priority: 'Medium', sourceData: {...row, 'Invoice count': invoices.length, 'Invoice numbers': invoices.map(entry => entry['Invoice No.']).join('; '), 'Recorded invoice value (₹)': total}, sourceInvoices: clone(invoices)};
  });
}
function installInvoiceWorkbook(workbook, filename, backup = true) {
  const snapshot = {...workbook, filename};
  // Write the large snapshot first: quota errors must leave existing records intact.
  const previous = localStorage.getItem('hk_v2_invoice_workbook');
  localStorage.setItem('hk_v2_invoice_workbook', JSON.stringify(snapshot));
  try { if (backup) createBackup('Before invoice workbook import'); }
  catch(error) { if(previous === null) localStorage.removeItem('hk_v2_invoice_workbook'); else localStorage.setItem('hk_v2_invoice_workbook',previous); throw error; }
  invoiceWorkbook = snapshot;
  segmentData.served = invoiceClientRecords(snapshot);
  const merged = mergeImportedClients(clone(segmentData.served));
  clients = merged.rows; persist(); persistSegments(); populateFilters(); filtered = [...clients]; renderAll(); renderInvoiceDashboard();
}
async function loadInvoiceWorkbook(force = false) {
  const version = dashboardDataVersion;
  try {
    const saved = localStorage.getItem('hk_v2_invoice_workbook');
    if (!force && saved !== null) { invoiceWorkbook = JSON.parse(saved); renderInvoiceDashboard(); return; }
    if (!force && localStorage.getItem('hk_v2_reset_revision')) return;
    const response = await fetch('/api/invoice-workbook'); const result = await response.json();
    if (!response.ok || !result.ok || dashboardResetting || version !== dashboardDataVersion) return;
    if (isInvoiceWorkbook(result.workbook)) { installInvoiceWorkbook(result.workbook, result.filename); if(force) navigate('dashboard'); }
  } catch (error) { toast('Invoice workbook could not load: ' + error.message); }
}
function invoiceBarChart(rows, field, amountField, title) {
  const groups = new Map(); rows.forEach(row => { const key = String(row[field] || 'Unspecified'); groups.set(key, (groups.get(key) || 0) + (invoiceNumber(row[amountField]) || 0)); });
  const sorted = [...groups].sort((a,b) => field === 'month' ? a[0].localeCompare(b[0]) : b[1]-a[1]), maximum = Math.max(1,...sorted.map(entry => entry[1]));
  return `<div class="card"><div class="card-head"><h2>${escapeHtml(title)}</h2></div><div class="card-body invoice-bars">${sorted.length ? sorted.map(([label,value]) => `<div><div class="invoice-bar-label"><span>${escapeHtml(label)}</span><strong>${money(value)}</strong></div><div class="invoice-bar-track"><div style="width:${Math.max(0,value/maximum*100)}%"></div></div></div>`).join('') : '<p>No matching values.</p>'}</div></div>`;
}
function renderInvoiceDashboard() {
  if(typeof renderImportRemoval==='function')renderImportRemoval();
  const panel = document.getElementById('invoiceDashboard'); if (!panel) return;
  panel.classList.toggle('hidden', !invoiceWorkbook);
  const demo = document.getElementById('demoDisclosure'); if(demo) demo.classList.toggle('hidden', !!invoiceWorkbook);
  document.querySelectorAll('#page-dashboard > :not(#invoiceDashboard)').forEach(node => node.classList.toggle('hidden', !!invoiceWorkbook));
  if (!invoiceWorkbook) return;
  const sheetSelect=document.getElementById('invoiceDetailSheet'),selected=sheetSelect.value;
  sheetSelect.replaceChildren();
  invoiceWorkbook.sheets.forEach(sheet=>{const option=document.createElement('option');option.value=sheet.name;option.textContent=sheet.name;sheetSelect.appendChild(option);});
  if(invoiceWorkbook.sheets.some(sheet=>sheet.name===selected))sheetSelect.value=selected;
  else if(invoiceWorkbook.sheets.some(sheet=>sheet.name==='Client Summary'))sheetSelect.value='Client Summary';
  const hasSheet=name=>invoiceWorkbook.sheets.some(sheet=>sheet.name===name),hasInvoiceSource=hasSheet('Client Summary')||hasSheet('Client Call List');
  const all = uniqueInvoices(hasSheet('Client Summary')?invoiceSheet('Client Summary'):invoiceSheet('Client Call List')).filter(row => !/cancel/i.test(row['Invoice Status'] || ''));
  for (const [id,field] of [['invoiceCity','Delivery City / Location'],['invoiceStatus','Invoice Status']]) {
    const select = document.getElementById(id), value = select.value;
    select.innerHTML = '<option value="">All '+(id==='invoiceCity'?'locations':'payment statuses')+'</option>' + [...new Set(all.map(row => row[field]).filter(Boolean))].sort().map(option => `<option>${escapeHtml(option)}</option>`).join(''); select.value = value;
  }
  const query = document.getElementById('invoiceSearch').value.trim().toLowerCase(), city = document.getElementById('invoiceCity').value, status = document.getElementById('invoiceStatus').value, start = document.getElementById('invoiceFrom').value, end = document.getElementById('invoiceTo').value;
  const match = row => (!query || Object.values(row).join(' ').toLowerCase().includes(query)) && (!city || row['Delivery City / Location'] === city) && (!status || row['Invoice Status'] === status) && (!start || invoiceDate(row['Invoice Date']) >= start) && (!end || (invoiceDate(row['Invoice Date']) && invoiceDate(row['Invoice Date']) <= end));
  const summary = all.filter(match), keys = new Set(summary.map(invoiceKey)), items = invoiceSheet('Client Call List').filter(row => keys.has(invoiceKey(row))), cancelled = invoiceSheet('Cancelled Invoices').filter(match), clients = new Set(summary.map(invoiceClientKey)), values = summary.map(row => invoiceNumber(row['Invoice Total (₹)'])), total = values.reduce((sum,value) => sum + (value || 0),0), counts = new Map();
  summary.forEach(row => counts.set(invoiceClientKey(row), (counts.get(invoiceClientKey(row)) || 0)+1));
  document.getElementById('invoiceFile').textContent = invoiceWorkbook.filename || 'Imported invoice workbook';
  document.getElementById('invoiceMetrics').innerHTML = [['Served clients', hasInvoiceSource?clients.size:'Unavailable'], ['Non-cancelled invoices',hasInvoiceSource?summary.length:'Unavailable'], ['Invoice value incl. GST', values.some(value => value !== null) ? money(total) : 'Unavailable'], ['Purchased item rows',hasSheet('Client Call List')?items.length:'Unavailable'], ['Repeat clients',hasInvoiceSource?[...counts.values()].filter(count => count > 1).length:'Unavailable'], ['Cancelled invoices',hasSheet('Cancelled Invoices')?uniqueInvoices(cancelled).length:'Unavailable']].map(([label,value]) => `<div class="summary-box"><b>${value}</b><span>${label}</span></div>`).join('');
  const feedbackCount = summary.filter(row => String(row['Client Feedback'] || '').trim()).length, missingPhone = summary.filter(row => !String(row['Client Phone'] || '').trim()).length, followups = summary.filter(row => String(row['Follow-up Date'] || '').trim()).length;
  document.getElementById('invoiceCoverage').textContent = `Feedback recorded: ${feedbackCount} / ${summary.length} invoices · Missing phone: ${missingPhone} invoices · Follow-up dates: ${followups} invoices. Invoice status describes payment; it does not confirm delivery. Invoice totals are counted once per invoice. Category values use item totals and may differ from invoice totals due to invoice adjustments.`;
  if(!hasSheet('Client Summary'))document.getElementById('invoiceCoverage').textContent = (hasSheet('Client Call List')?'Client Summary removed. Invoice analysis uses one invoice total from each invoice in Client Call List. ':'Invoice source worksheets removed. Invoice analysis is unavailable. ')+document.getElementById('invoiceCoverage').textContent;
  if(!hasSheet('Client Call List'))document.getElementById('invoiceCoverage').textContent += ' Client Call List removed; product category analysis is unavailable.';
  if(!invoiceWorkbook.sheets.length)document.getElementById('invoiceCoverage').textContent='All worksheets have been removed from this workbook. Import Excel or restore a checkpoint to load data.';
  document.getElementById('invoiceCharts').innerHTML = invoiceBarChart(items,'Category','Item Total incl. GST (₹)','Product category · item value incl. GST') + invoiceBarChart(summary,'Delivery City / Location','Invoice Total (₹)','Location · invoice value incl. GST') + invoiceBarChart(summary,'Invoice Status','Invoice Total (₹)','Payment status · invoice value incl. GST') + invoiceBarChart(summary.map(row => ({...row,month:invoiceDate(row['Invoice Date']).slice(0,7)||'Unknown date'})),'month','Invoice Total (₹)','Invoice month · value incl. GST');
  const sheetName = document.getElementById('invoiceDetailSheet').value;
  invoiceVisibleRows = sheetName === 'Client Summary' ? summary : sheetName === 'Client Call List' ? items : sheetName === 'Cancelled Invoices' ? cancelled : invoiceSheet(sheetName).filter(row => !query || Object.values(row).join(' ').toLowerCase().includes(query));
  const columns = [...new Set(invoiceSheet(sheetName).flatMap(row => Object.keys(row)))];
  document.getElementById('invoiceDetailCount').textContent = `${invoiceVisibleRows.length} rows · ${columns.length} original columns` + (['Categorized Items','Verification Summary','Read Me'].includes(sheetName) ? ' · workbook reference; search applies' : ' · current filters');
  document.getElementById('invoiceDetailHead').innerHTML = '<tr>'+columns.map(column => `<th>${escapeHtml(column)}</th>`).join('')+'</tr>';
  document.getElementById('invoiceDetailRows').innerHTML = invoiceVisibleRows.length ? invoiceVisibleRows.map(row => '<tr>'+columns.map(column => `<td>${escapeHtml(row[column] ?? '')}</td>`).join('')+'</tr>').join('') : `<tr><td colspan="${Math.max(1,columns.length)}" class="empty-state">No matching records.</td></tr>`;
}
function clearInvoiceFilters() { ['invoiceSearch','invoiceCity','invoiceStatus','invoiceFrom','invoiceTo'].forEach(id => document.getElementById(id).value=''); renderInvoiceDashboard(); }
function exportInvoiceDetails() {
  const sheet = document.getElementById('invoiceDetailSheet').value, columns = [...new Set(invoiceSheet(sheet).flatMap(row => Object.keys(row)))];
  const html = '<html><head><meta charset="UTF-8"></head><body><table><tr>'+columns.map(column => `<th>${escapeHtml(column)}</th>`).join('')+'</tr>'+invoiceVisibleRows.map(row => '<tr>'+columns.map(column => `<td>${escapeHtml(row[column] ?? '')}</td>`).join('')+'</tr>').join('')+'</table></body></html>';
  const url = URL.createObjectURL(new Blob([html], {type:'application/vnd.ms-excel;charset=utf-8'})), link = document.createElement('a'); link.href=url; link.download='HOSPkart_'+sheet.replaceAll(' ','_')+'.xls'; link.click(); setTimeout(() => URL.revokeObjectURL(url),1000);
}
