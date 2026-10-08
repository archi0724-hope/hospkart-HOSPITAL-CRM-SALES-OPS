// CRM records use transactional IndexedDB, rather than localStorage's small quota.
const dashboardStorage = new Map();
const dashboardKeys = ['hk_v2_clients','hk_v2_calls','hk_v2_feedback','hk_v2_segments','hk_v2_rghs','hk_v2_leads','hk_v2_served','hk_v2_doctors','hk_v2_potential','hk_v2_invoice_workbook','hk_v2_backups','hk_v2_reset_revision'];
let dashboardDatabase;
let dashboardReady = false;
let dashboardWriteQueue = Promise.resolve();
const dashboardChanges = typeof BroadcastChannel==='function'?new BroadcastChannel('hospkart-crm-changes'):null;
if(dashboardChanges)dashboardChanges.onmessage=()=>{if(dashboardReady)window.location.reload();};
function readableLegacyRecord(key,raw){
  try{
    const value=JSON.parse(raw);
    if(key==='hk_v2_invoice_workbook')return validInvoiceSnapshot(value);
    if(key==='hk_v2_segments')return value&&typeof value==='object'&&!Array.isArray(value)&&['served','doctors','potential'].every(section=>value[section]===undefined||validRecordArray(value[section],true));
    if(['hk_v2_rghs','hk_v2_leads','hk_v2_served','hk_v2_doctors','hk_v2_potential'].includes(key))return validRecordArray(value,true);
    if(key==='hk_v2_backups')return validRecordArray(value)&&value.every(backup=>validRecordArray(backup.clients,true)&&validRecordArray(backup.calls)&&validRecordArray(backup.feedback));
    if(key==='hk_v2_reset_revision')return true;
    return validRecordArray(value,key==='hk_v2_clients');
  }catch(_){return false;}
}
function databaseTransaction(values) {
  return new Promise((resolve,reject)=>{
    const transaction=dashboardDatabase.transaction('records','readwrite');
    transaction.oncomplete=resolve;
    transaction.onabort=()=>reject(transaction.error||new Error('The browser could not save these records.'));
    transaction.onerror=()=>{}; // Abort is the final outcome, including failed requests.
    try{const records=transaction.objectStore('records');Object.entries(values).forEach(([key,value])=>records.put(value,key));}
    catch(error){transaction.abort();reject(error);}
  });
}
function databaseRecords() {
  return new Promise((resolve,reject)=>{
    const transaction=dashboardDatabase.transaction('records','readonly'),records=transaction.objectStore('records'),result=new Map();
    transaction.oncomplete=()=>resolve(result);
    transaction.onabort=()=>reject(transaction.error||new Error('Saved records could not be read.'));
    for(const key of dashboardKeys){const request=records.get(key);request.onsuccess=()=>{if(request.result!==undefined)result.set(key,request.result);};}
  });
}
async function initializeDashboardStorage() {
  try{
    const legacy=new Map();
    for(const key of dashboardKeys){const raw=localStorage.getItem(key);if(raw!==null)legacy.set(key,raw);}
    dashboardDatabase=await new Promise((resolve,reject)=>{
      const request=indexedDB.open('hospkart-crm',1);
      request.onupgradeneeded=()=>request.result.createObjectStore('records');
      request.onsuccess=()=>resolve(request.result);
      request.onerror=()=>reject(request.error);
      request.onblocked=()=>reject(new Error('Close other HOSPkart tabs, then reload.'));
    });
    dashboardDatabase.onversionchange=()=>dashboardDatabase.close();
    const saved=await databaseRecords(),migrate={};
    // Existing database records take priority after a completed migration.
    legacy.forEach((raw,key)=>{if(!saved.has(key))migrate[key]=raw;});
    if(Object.keys(migrate).length){
      await databaseTransaction(migrate);
      const verified=await databaseRecords();
      if(!Object.entries(migrate).every(([key,raw])=>verified.get(key)===raw))throw new Error('Migration verification failed. Original records are kept.');
      Object.entries(migrate).forEach(([key,raw])=>saved.set(key,raw));
    }
    saved.forEach((raw,key)=>dashboardStorage.set(key,raw));
    // Keep unreadable legacy records available for recovery. Never clear the site.
    legacy.forEach((raw,key)=>{try{if(readableLegacyRecord(key,raw)&&saved.get(key)===raw&&localStorage.getItem(key)===raw)localStorage.removeItem(key);}catch(_){} });
    dashboardReady=true;
    if(navigator.storage?.persist)navigator.storage.persist().catch(()=>{});
  }catch(error){
    // Original localStorage data remains readable when migration is unavailable.
    for(const key of dashboardKeys){try{const raw=localStorage.getItem(key);if(raw!==null)dashboardStorage.set(key,raw);}catch(_){} }
    browserStorageNotice('Browser storage could not be opened. Your existing records are kept. Enable site storage and reload. '+error.message);
  }
}
function commitDashboardRecords(values) {
  const serialized=Object.fromEntries(Object.entries(values).map(([key,value])=>[key,JSON.stringify(value)]));
  const operation=dashboardWriteQueue.then(async()=>{
    if(!dashboardReady)throw new Error('Browser storage is unavailable. Your existing records have been kept.');
    await databaseTransaction(serialized);
    Object.entries(serialized).forEach(([key,raw])=>dashboardStorage.set(key,raw));
    dashboardChanges?.postMessage('saved');
  });
  dashboardWriteQueue=operation.catch(()=>{});
  return operation.catch(error=>{
    browserStorageNotice('Changes could not be saved. Download a JSON checkpoint before closing this page. '+error.message);
    throw error;
  });
}
