let pendingImportRemoval = null;
let importRemovalSubmitting = false;
const importSectionTitles = {served:'Already Served', doctors:'Doctors', potential:'Potential Leads'};

function renderImportRemoval() {
  const body = document.getElementById('importRemovalRows'); if (!body) return;
  const targets = [];
  if (invoiceWorkbook) {
    targets.push({scope:'workbook',name:invoiceWorkbook.filename || 'Imported workbook',label:invoiceWorkbook.filename || 'Imported workbook',count:invoiceWorkbook.sheets.reduce((sum,sheet)=>sum+sheet.rows.length,0)});
    invoiceWorkbook.sheets.forEach(sheet => targets.push({scope:'worksheet',name:sheet.name,label:sheet.name,count:sheet.rows.length}));
  }
  Object.entries(importSectionTitles).forEach(([name,label])=>{if(segmentData[name]?.length)targets.push({scope:'segment',name,label,count:segmentData[name].length});});
  body.replaceChildren();
  targets.forEach(target => {
    const row = document.createElement('tr');
    [target.label, target.scope==='workbook'?'Whole imported workbook':target.scope==='worksheet'?'One worksheet':'One imported section',String(target.count)].forEach(value=>{const cell=document.createElement('td');cell.textContent=value;row.appendChild(cell);});
    const cell = document.createElement('td'), button = document.createElement('button');
    button.className='btn danger'; button.textContent='Remove'; button.addEventListener('click',()=>openImportRemoval(target)); cell.appendChild(button);row.appendChild(cell);body.appendChild(row);
  });
  if(!targets.length)body.innerHTML='<tr><td colspan="4" class="empty-state">No imported worksheets or sections to remove.</td></tr>';
}
function openImportRemoval(target) {
  if(dashboardResetting||importRemovalSubmitting)return;
  pendingImportRemoval={...target,version:dashboardDataVersion,workbook:invoiceWorkbook};
  document.getElementById('importRemovalForm').reset();
  document.getElementById('importRemovalName').textContent=target.label;
  document.getElementById('importRemovalPhrase').textContent='REMOVE '+target.name;
  document.getElementById('importRemovalError').textContent='';
  document.getElementById('importRemovalDialog').showModal();
  document.getElementById('importRemovalPassword').focus();
}
function closeImportRemoval(){if(importRemovalSubmitting)return;document.getElementById('importRemovalPassword').value='';pendingImportRemoval=null;document.getElementById('importRemovalDialog').close();}
async function removeSelectedImport(event) {
  event.preventDefault(); const target=pendingImportRemoval;
  if(!target||dashboardResetting||importRemovalSubmitting)return;
  const error=document.getElementById('importRemovalError'), button=document.getElementById('importRemovalSubmit');
  importRemovalSubmitting=true;button.disabled=true;error.textContent='';
  try {
    const response=await fetch('/api/admin/remove-import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scope:target.scope,name:target.name,password:document.getElementById('importRemovalPassword').value,confirmation:document.getElementById('importRemovalConfirmation').value})});
    document.getElementById('importRemovalPassword').value='';
    const result=await response.json();if(!response.ok||!result.ok)throw new Error(result.error||'Removal was not authorized.');
    if(result.authorized_scope!==target.scope||result.authorized_name!==target.name)throw new Error('Removal scope did not match.');
    if(dashboardResetting||target.version!==dashboardDataVersion||target.workbook!==invoiceWorkbook)throw new Error('Dashboard data changed. Select the import again.');
    const updatedWorkbook=clone(invoiceWorkbook), updatedSegments=clone(segmentData);
    let nextWorkbook=updatedWorkbook;
    if(target.scope==='worksheet') {
      if(!updatedWorkbook?.sheets.some(sheet=>sheet.name===target.name))throw new Error('That worksheet is no longer available.');
      updatedWorkbook.sheets=updatedWorkbook.sheets.filter(sheet=>sheet.name!==target.name);
      if(updatedWorkbook.sheet_previews)delete updatedWorkbook.sheet_previews[target.name];
    } else if(target.scope==='workbook')nextWorkbook=null;
    else updatedSegments[target.name]=[];
    // A removal is transactional across the browser keys, including its backup.
    const keys=['hk_v2_invoice_workbook','hk_v2_segments','hk_v2_backups'], previous=new Map(keys.map(key=>[key,localStorage.getItem(key)])), oldBackups=backups;
    try {
      createBackup('Before removing '+target.label);
      localStorage.setItem('hk_v2_invoice_workbook',JSON.stringify(nextWorkbook));
      localStorage.setItem('hk_v2_segments',JSON.stringify(updatedSegments));
    } catch(failure) {
      previous.forEach((value,key)=>{if(value===null)localStorage.removeItem(key);else localStorage.setItem(key,value);});backups=oldBackups;throw failure;
    }
    invoiceWorkbook=nextWorkbook;segmentData=updatedSegments;dashboardDataVersion++;
    importRemovalSubmitting=false;closeImportRemoval();renderAll();renderImportRemoval();
    toast(target.label+' removed. Other imports and saved client history are kept. A backup is available.');
  } catch(failure){error.textContent=failure.message;}
  finally{importRemovalSubmitting=false;button.disabled=false;}
}
