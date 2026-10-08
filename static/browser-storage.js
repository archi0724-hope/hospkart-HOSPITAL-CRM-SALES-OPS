let browserStorageProblem=false;
function browserStorageNotice(message) {
  browserStorageProblem=true;
  const notice=document.getElementById('browserStorageNotice');
  if(notice){notice.textContent=message;notice.classList.remove('hidden');}
}
function validRecordArray(value, named=false) {
  return Array.isArray(value)&&value.every(row=>row&&typeof row==='object'&&!Array.isArray(row)&&(!named||(typeof row.id==='string'&&typeof row.name==='string')));
}
function readDashboardValue(key,fallback) {
  let raw;
  try {raw=localStorage.getItem(key);}catch(error){browserStorageNotice('Browser storage is blocked. Enable site storage to save or import records.');return clone(fallback);}
  if(raw===null)return clone(fallback);
  try {
    const value=JSON.parse(raw);
    if(Array.isArray(fallback)&&!validRecordArray(value,key==='hk_v2_clients'))throw new Error('Invalid saved records');
    if(!Array.isArray(fallback)&&(!value||typeof value!=='object'||Array.isArray(value)))throw new Error('Invalid saved sections');
    if(key==='hk_v2_segments'&&!['served','doctors','potential'].every(section=>value[section]===undefined||validRecordArray(value[section],true)))throw new Error('Invalid section records');
    if(key==='hk_v2_backups'&&!value.every(backup=>validRecordArray(backup.clients,true)&&validRecordArray(backup.calls)&&validRecordArray(backup.feedback)))throw new Error('Invalid checkpoints');
    return value;
  }catch(error){browserStorageNotice('Saved browser data could not be read. Restore a JSON checkpoint in Data & backups. The unreadable data has been kept.');return Array.isArray(fallback)?[]:clone(fallback);}
}
function writeDashboardValues(values,originalOverrides={}) {
  const originals=new Map();
  try {
    Object.keys(values).forEach(key=>originals.set(key,Object.prototype.hasOwnProperty.call(originalOverrides,key)?originalOverrides[key]:localStorage.getItem(key)));
    Object.entries(values).forEach(([key,value])=>localStorage.setItem(key,JSON.stringify(value)));
  }catch(error){
    // Free changed keys before restoring them so rollback also works at quota.
    try{originals.forEach((_,key)=>localStorage.removeItem(key));originals.forEach((value,key)=>{if(value!==null)localStorage.setItem(key,value);});}catch(rollbackError){browserStorageNotice('Browser storage is unavailable. Download a checkpoint before closing this page.');}
    if(error.name==='QuotaExceededError')throw new Error('Browser storage is full. Download a checkpoint and remove an unused import before trying again. No new import was saved.');
    throw new Error('Browser storage is blocked. Enable site storage before saving changes.');
  }
}
function saveBackupList(snapshots) {
  const retained=snapshots.slice(0,10);
  while(retained.length){
    try{localStorage.setItem('hk_v2_backups',JSON.stringify(retained));return retained;}
    catch(error){if(error.name!=='QuotaExceededError'||retained.length===1)throw error;retained.pop();}
  }
  return retained;
}
function validInvoiceSnapshot(value) {
  return value===null||(value&&typeof value==='object'&&Array.isArray(value.sheets)&&value.sheets.every(sheet=>sheet&&typeof sheet.name==='string'&&validRecordArray(sheet.rows))&&new Set(value.sheets.map(sheet=>sheet.name)).size===value.sheets.length);
}
function validateCheckpoint(snapshot) {
  if(!snapshot||!validRecordArray(snapshot.clients,true)||!validRecordArray(snapshot.calls)||!validRecordArray(snapshot.feedback))throw new Error('Choose a complete HOSPkart JSON checkpoint.');
  const segments=snapshot.segments||{served:[],doctors:[],potential:[]};
  if(!['served','doctors','potential'].every(key=>validRecordArray(segments[key],true))||!validInvoiceSnapshot(snapshot.invoiceWorkbook||null))throw new Error('The checkpoint contains invalid imported records.');
  return {...snapshot,segments,invoiceWorkbook:snapshot.invoiceWorkbook||null};
}
function applyDashboardCheckpoint(input,reason) {
  const snapshot=validateCheckpoint(input),oldBackups=backups,oldBackupRaw=localStorage.getItem('hk_v2_backups');
  try{
    if(reason)createBackup(reason);
    writeDashboardValues({hk_v2_clients:snapshot.clients,hk_v2_calls:snapshot.calls,hk_v2_feedback:snapshot.feedback,hk_v2_segments:snapshot.segments,hk_v2_invoice_workbook:snapshot.invoiceWorkbook,hk_v2_backups:backups},{hk_v2_backups:oldBackupRaw});
  }catch(error){backups=oldBackups;throw error;}
  clients=clone(snapshot.clients);calls=clone(snapshot.calls);feedback=clone(snapshot.feedback);segmentData=clone(snapshot.segments);invoiceWorkbook=clone(snapshot.invoiceWorkbook);
  populateFilters();filtered=[...clients];renderAll();
}
async function importJsonCheckpoint(input) {
  const file=input.files?.[0];if(!file)return;
  const version=dashboardDataVersion;
  try{
    if(file.size>16*1024*1024)throw new Error('JSON checkpoints must be 16 MB or smaller.');
    const snapshot=validateCheckpoint(JSON.parse(await file.text()));
    if(dashboardResetting||version!==dashboardDataVersion)return;
    if(!await askImportConfirmation(`Restore ${snapshot.clients.length} clients, ${snapshot.calls.length} call notes, and ${snapshot.invoiceWorkbook?.sheets.length||0} workbook sheets from ${file.name}? Current data will first be backed up.`))return;
    if(dashboardResetting||version!==dashboardDataVersion)return;
    applyDashboardCheckpoint(snapshot,'Before JSON checkpoint restore');
    toast('Checkpoint restored. All imported sheets and saved CRM records are available in this browser.');
  }catch(error){toast('Checkpoint restore failed: '+error.message);}finally{input.value='';}
}
