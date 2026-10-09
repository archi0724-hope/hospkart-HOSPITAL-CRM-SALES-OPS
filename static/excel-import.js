let excelMappingResolver = null;
let excelMappingWorkbook = null;

function excelColumnNames(row) {
  const seen = new Set();
  return row.map((value, index) => {
    const base = value != null && String(value).trim() ? String(value).trim() : `Column ${index + 1}`;
    let name = base, suffix = 2;
    while (seen.has(name)) name = `${base} (${suffix++})`;
    seen.add(name);
    return name;
  });
}

function detectHtmlExcelHeader(rows) {
  const names = new Set(clientNameAliases.map(normalizeImportHeader));
  const common = new Set(['city', 'district', 'state', 'mobile', 'mobilenumber', 'phone', 'email', 'address', 'status', 'contactperson', 'remarks', 'srno', 'sno']);
  const candidates = [], fallback = [];
  rows.slice(0, 50).forEach((row, index) => {
    const headers = [...new Set(row.map(normalizeImportHeader))];
    const known = headers.some(header => names.has(header));
    const score = headers.filter(header => common.has(header)).length * 100 + headers.filter(Boolean).length;
    if (known) candidates.push({index, score});
    if (headers.some(header => common.has(header))) fallback.push({index, score});
  });
  return (candidates.length ? candidates : fallback).sort((a, b) => b.score - a.score || a.index - b.index)[0]?.index ?? Math.max(0, rows.findIndex(row => row.some(value => String(value || '').trim())));
}

async function readExcelWorkbook(file, headerRows = {}) {
  if (/\.xls(?:html)?$|\.html?$/i.test(file.name)) {
    const text = await file.text();
    if (text.trimStart().startsWith('<')) {
      const document = new DOMParser().parseFromString(text, 'text/html');
      const titles = [...document.querySelectorAll('h2')].map(title => title.textContent.trim());
      const used = new Set(), sheet_previews = {};
      const sheets = [...document.querySelectorAll('table')].map((table, index) => {
        const raw = [...table.querySelectorAll('tr')].map(row => [...row.querySelectorAll('th,td')].map(cell => cell.textContent.trim()));
        const base = titles[index] || (index ? `Table ${index + 1}` : 'Clients');
        let name = base, suffix = 2;
        while (used.has(name)) name = `${base} (${suffix++})`;
        used.add(name);
        const header = headerRows[name] ?? detectHtmlExcelHeader(raw);
        const columns = excelColumnNames(raw[header] || []);
        sheet_previews[name] = {rows: raw.slice(0, 50), header_row: header};
        return {name, rows: raw.slice(header + 1).filter(row => row.some(Boolean)).map(row => Object.fromEntries(columns.map((column, cell) => [column, row[cell] ?? ''])))};
      });
      return {sheets, sheet_previews};
    }
  }
  const form = new FormData();
  form.append('file', file);
  form.append('header_rows', JSON.stringify(headerRows));
  const response = await fetch('/api/import-excel', {method: 'POST', body: form});
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.error || 'Could not read the Excel file.');
  return {sheets: Object.entries(result.sheets).map(([name, rows]) => ({name, rows})), sheet_previews: result.sheet_previews || {}};
}

function refreshExcelMappingSheet() {
  const name = document.getElementById('excelMapSheet').value;
  const preview = excelMappingWorkbook.sheet_previews[name];
  const select = document.getElementById('excelMapHeader');
  select.replaceChildren();
  preview.rows.forEach((row, index) => {
    const option = document.createElement('option');
    option.value = String(index);
    option.textContent = `Row ${index + 1}: ${row.filter(value => value != null && String(value).trim()).map(String).join(' · ').slice(0, 130) || '(empty)'}`;
    select.appendChild(option);
  });
  select.value = String(preview.header_row);
  if (!select.value) select.value = '0';
  refreshExcelMappingHeader();
}

function refreshExcelMappingHeader() {
  const preview = excelMappingWorkbook.sheet_previews[document.getElementById('excelMapSheet').value];
  const header = Number(document.getElementById('excelMapHeader').value);
  const columns = excelColumnNames(preview.rows[header] || []);
  const select = document.getElementById('excelMapName');
  select.replaceChildren();
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = 'Choose the column containing hospital / customer names';
  select.appendChild(placeholder);
  columns.forEach((column, index) => {
    const option = document.createElement('option');
    option.value = column;
    const sample = preview.rows.slice(header + 1).map(row => row[index]).filter(value => value != null && String(value).trim()).slice(0, 2).join(' / ');
    option.textContent = `${column}${sample ? ' — ' + sample.slice(0, 80) : ''}`;
    select.appendChild(option);
  });
  document.getElementById('excelMapPreviewHead').innerHTML = '<tr>' + columns.map(column => `<th>${escapeHtml(column)}</th>`).join('') + '</tr>';
  document.getElementById('excelMapPreviewRows').innerHTML = preview.rows.slice(header + 1, header + 6).map(row => '<tr>' + columns.map((_, index) => `<td>${escapeHtml(row[index] ?? '')}</td>`).join('') + '</tr>').join('');
}

function chooseExcelMapping(workbook, fileName) {
  const sheets = Object.entries(workbook.sheet_previews).filter(([, preview]) => preview.rows.length);
  if (!sheets.length) throw new Error('The workbook has no readable worksheet rows. Choose a file containing hospital records.');
  excelMappingWorkbook = workbook;
  document.getElementById('excelMapFile').textContent = fileName;
  const select = document.getElementById('excelMapSheet');
  select.replaceChildren();
  sheets.forEach(([name]) => {
    const option = document.createElement('option');
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  });
  refreshExcelMappingSheet();
  const dialog = document.getElementById('excelMappingDialog');
  dialog.oncancel = event => { event.preventDefault(); resolveExcelMapping(null); };
  dialog.showModal();
  return new Promise(resolve => { excelMappingResolver = resolve; });
}

function saveExcelMapping(event) {
  event.preventDefault();
  const nameColumn = document.getElementById('excelMapName').value;
  if (!nameColumn) return;
  resolveExcelMapping({sheet: document.getElementById('excelMapSheet').value, headerRow: Number(document.getElementById('excelMapHeader').value), nameColumn});
}

function resolveExcelMapping(value) {
  document.getElementById('excelMappingDialog').close();
  const resolve = excelMappingResolver;
  excelMappingResolver = null;
  resolve?.(value);
}

async function excelClientSheets(file) {
  const version = dashboardDataVersion;
  const workbook = await readExcelWorkbook(file);
  if (dashboardResetting || version !== dashboardDataVersion) return null;
  if (isInvoiceWorkbook(workbook)) {
    await installInvoiceWorkbook(workbook, file.name);
    navigate('dashboard');
    toast('Invoice workbook imported. All worksheets are available under Reports & Export.');
    return null;
  }
  const recognized = workbook.sheets.filter(sheetHasClientNames);
  if (recognized.length) return {clientSheets: recognized, sheets: workbook.sheets};
  const mapping = await chooseExcelMapping(workbook, file.name);
  if (!mapping || dashboardResetting || version !== dashboardDataVersion) return null;
  const selected = await readExcelWorkbook(file, {[mapping.sheet]: mapping.headerRow});
  if (dashboardResetting || version !== dashboardDataVersion) return null;
  const sheet = selected.sheets.find(sheet => sheet.name === mapping.sheet);
  if (!sheet || !sheet.rows.some(row => String(row[mapping.nameColumn] ?? '').trim())) throw new Error('No hospital names were found below this header. Choose another header row or name column.');
  return {clientSheets: [{...sheet, nameColumn: mapping.nameColumn}], sheets: selected.sheets};
}
