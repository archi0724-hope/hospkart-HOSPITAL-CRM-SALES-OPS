let invoiceWorkbook = null;
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
async function installInvoiceWorkbook(workbook, filename, backup = true) {
  const snapshot = {...workbook, filename};
  if(!validInvoiceSnapshot(snapshot))throw new Error('The workbook contains invalid worksheets. Import the Excel file again.');
  const served=invoiceClientRecords(snapshot),merged=mergeImportedClients(clone(served));
  await applyDashboardCheckpoint({clients:merged.rows,calls,feedback,segments:{...segmentData,served},sections:{...sectionRecords,served},invoiceWorkbook:snapshot},backup?'Before invoice workbook import':'');
}
async function loadInvoiceWorkbook(force = false) {
  const version = dashboardDataVersion;
  try {
    const saved = (dashboardStorage.get('hk_v2_invoice_workbook')??null);
    if (!force && saved !== null) {
      const snapshot=JSON.parse(saved);
      if(!validInvoiceSnapshot(snapshot))throw new Error('Saved invoice data is unreadable. Restore a JSON checkpoint or import the Excel file again.');
      invoiceWorkbook=snapshot;renderInvoiceDashboard();return;
    }
    if (!force && dashboardStorage.get('hk_v2_reset_revision')) return;
    if(!force&&browserStorageProblem)return;
    const response = await fetch('/api/invoice-workbook'); const result = await response.json();
    if(dashboardResetting||version!==dashboardDataVersion)return;
    if(!response.ok||!result.ok){if(force)toast('No workbook is stored on this server. Use Import Excel to load your file.');return;}
    if (isInvoiceWorkbook(result.workbook)) { await installInvoiceWorkbook(result.workbook, result.filename); if(force) navigate('dashboard'); }
  } catch (error) { browserStorageNotice('Invoice workbook could not load: '+error.message);toast('Invoice workbook could not load: ' + error.message); }
}
function renderInvoiceDashboard() {
  if(typeof renderImportRemoval==='function')renderImportRemoval();
}
