let sharedDriveLinks=[];
let driveImportBusy=false;
let driveLinksPoll=null;
let driveStorageInfo={engine:'sqlite',durable:false};
let excelImportTarget='clients';
function openExcelImport(target='clients'){
  if(driveImportBusy||dashboardResetting)return;
  excelImportTarget=target;
  document.getElementById('excelDriveSourceMessage').textContent='';
  document.getElementById('excelImportSourceDialog').showModal();
}
function chooseComputerExcelImport(){
  const fields={clients:'excelImportFile',rghs:'rghsImportFile',served:'servedImportFile',doctors:'doctorImportFile',potential:'potentialImportFile'};
  document.getElementById('excelImportSourceDialog').close();
  document.getElementById(fields[excelImportTarget]||'excelImportFile').click();
}
async function submitExcelDriveLink(event){
  event.preventDefault();
  const button=document.getElementById('excelDriveSourceSubmit');if(button.disabled)return;button.disabled=true;
  const message=document.getElementById('excelDriveSourceMessage');message.textContent='Saving the source link…';
  try{
    const link=document.getElementById('excelDriveSourceLink').value;
    const response=await driveRequest('/save',{link,label:document.getElementById('excelDriveSourceLabel').value,target:excelImportTarget});
    sharedDriveLinks=(await response.json()).links;renderDriveImportLinks();
    // The saved list is ordered by creation, so select by parsed source file identity.
    const input=new URL(link),identifier=input.pathname.match(/\/d\/([^/]+)/)?.[1]||input.searchParams.get('id');
    const item=sharedDriveLinks.find(row=>row.target===excelImportTarget&&row.link.includes('/d/'+identifier+'/'));
    if(!item)throw new Error('The source link was saved. Choose it from the shared Drive list.');
    document.getElementById('excelImportSourceDialog').close();openDriveImport(excelImportTarget);
    const savedCopy=!!item.copy_saved_at&&confirm('A saved workbook copy is available from '+new Date(item.copy_saved_at).toLocaleString()+'. Import that copy? Choose Cancel to try the latest file directly from Google Drive.');
    await importSharedDriveLink(item,savedCopy);
  }catch(error){message.textContent=error.message;}finally{button.disabled=false;}
}
const driveTargetLabels={clients:'Hospitals & Clients / invoices',rghs:'RGHS Data',served:'Already Served',doctors:'Doctors',potential:'Potential Leads',leads:'Leads & Queries'};

async function driveRequest(path='',data){
  const response=await fetch('/api/drive-import'+path,{method:data===undefined?'GET':'POST',cache:'no-store',
    headers:data===undefined?{}:{'Content-Type':'application/json','X-CRM-Request':'1'},
    body:data===undefined?undefined:JSON.stringify(data),signal:AbortSignal.timeout(90000)});
  if(!response.ok){const result=await response.json().catch(()=>({}));throw new Error(result.error||'Drive request failed. Saved records were kept.');}
  return response;
}

function renderDriveImportLinks(){
  const root=document.getElementById('driveImportRows');root.replaceChildren();
  for(const item of sharedDriveLinks){
    const row=document.createElement('tr'),name=document.createElement('td'),target=document.createElement('td'),actions=document.createElement('td');
    name.textContent=item.label;target.textContent=item.target==='folder'?'CRM source folder':driveTargetLabels[item.target]||item.target;
    if(item.copy_saved_at){const note=document.createElement('div');note.className='mini-help';note.textContent='Saved copy: '+new Date(item.copy_saved_at).toLocaleString();name.append(note);}
    const open=document.createElement('a');open.className='btn small';open.textContent=item.target==='folder'?'Open Drive folder':'Open Drive file';open.href=item.link;open.target='_blank';open.rel='noopener noreferrer';actions.append(open);
    const action=(label,callback)=>{const button=document.createElement('button');button.type='button';button.className='btn small';button.textContent=label;button.disabled=driveImportBusy;button.addEventListener('click',callback);actions.append(' ',button);};
    action('Copy Drive link',()=>copyDriveText(item.link));
    if(item.target!=='folder')action(item.target==='leads'?'Connect for sync':'Preview / import',()=>importSharedDriveLink(item));
    if(item.target!=='folder'&&item.target!=='leads'&&item.copy_saved_at)action('Import saved copy',()=>importSharedDriveLink(item,true));
    if(item.target!=='folder'&&item.target!=='leads')action('Attach workbook copy',()=>chooseDriveWorkbookCopy(item));
    action('Remove link',()=>removeDriveImportLink(item));
    row.append(name,target,actions);root.append(row);
  }
  if(!sharedDriveLinks.length){const row=root.insertRow(),cell=row.insertCell();cell.colSpan=3;cell.textContent='No shared Drive links saved yet.';}
}

async function refreshDriveImportLinks(){
  if(driveImportBusy)return;
  const response=await driveRequest();const state=await response.json();sharedDriveLinks=state.links;driveStorageInfo=state.storage||driveStorageInfo;renderDriveImportLinks();renderDriveServerNote();
}

async function withDriveAction(action){
  if(driveImportBusy||dashboardResetting)return;
  driveImportBusy=true;document.getElementById('driveLinkSaveButton').disabled=true;renderDriveImportLinks();
  const message=document.getElementById('driveImportMessage');message.textContent='Working…';
  try{await action();}catch(error){message.textContent=error.message;}finally{driveImportBusy=false;document.getElementById('driveLinkSaveButton').disabled=false;renderDriveImportLinks();}
}

function saveDriveImportLink(event){
  event.preventDefault();return withDriveAction(async()=>{
    const response=await driveRequest('/save',{link:document.getElementById('driveImportLink').value,label:document.getElementById('driveImportLabel').value,target:document.getElementById('driveImportTarget').value});
    sharedDriveLinks=(await response.json()).links;
    document.getElementById('driveImportMessage').textContent='Drive link saved for all users on this server. Workbook rows have not been imported.';
  });
}

function removeDriveImportLink(item){
  if(!confirm('Remove this saved Drive link for all users? Imported CRM records and the source file will be kept.'))return;
  return withDriveAction(async()=>{sharedDriveLinks=(await(await driveRequest('/remove',{id:item.id})).json()).links;document.getElementById('driveImportMessage').textContent='Link removed. Imported records were kept.';});
}

function importSharedDriveLink(item,savedCopy=false){
  if(item.target==='leads'){
    openSpreadsheetConnection();document.getElementById('sheetLinkInput').value=item.link;invalidateSheetInspection();return;
  }
  return withDriveAction(async()=>{
    const version=dashboardDataVersion;
    document.getElementById('driveImportMessage').textContent=savedCopy?'Reading the saved workbook copy from the CRM database. This does not fetch newer Drive changes…':'Reading the private workbook from Google Drive…';
    const response=await driveRequest('/download',{id:item.id,saved_copy:savedCopy});
    if(dashboardResetting||version!==dashboardDataVersion)throw new Error('The dashboard changed during download. Review it before importing again.');
    const disposition=response.headers.get('Content-Disposition')||'';
    const extension=/\.xls(?:[";\s]|$)/i.test(disposition)?'.xls':'.xlsx';
    const file=new File([await response.blob()],item.label.replace(/[\\/]/g,'_')+extension,{type:response.headers.get('Content-Type')||''});
    const input={files:[file],value:''};
    if(item.target==='clients')await importExcelFile(input);else await importSegmentExcel(input,item.target);
    document.getElementById('driveImportMessage').textContent='Workbook handed to the Excel import workflow. Check its confirmation/result message; importing is separate from saving a link.';
  });
}
function chooseDriveWorkbookCopy(item){
  const input=document.createElement('input');input.type='file';input.accept='.xlsx,.xls';
  input.addEventListener('change',()=>{
    if(!input.files?.[0])return;
    return withDriveAction(async()=>{
      const body=new FormData();body.append('id',item.id);body.append('file',input.files[0]);
      const response=await fetch('/api/drive-import/save-copy',{method:'POST',headers:{'X-CRM-Request':'1'},body,signal:AbortSignal.timeout(90000)});
      const result=await response.json();if(!response.ok||!result.ok)throw new Error(result.error||'Workbook copy was not saved.');
      sharedDriveLinks=result.links;document.getElementById('driveImportMessage').textContent='Workbook copy saved for all users. This is an uploaded copy; it does not sync future Drive changes. Use Import saved copy to review and import it.';
    });
  });input.click();
}

async function copyDriveText(value){
  try{await navigator.clipboard.writeText(value);toast('Link copied.');}catch(_){window.prompt('Copy this link:',value);}
}
function copyCRMAddress(){
  if(['localhost','127.0.0.1','[::1]'].includes(location.hostname)){document.getElementById('driveImportMessage').textContent='This localhost address works only on this computer. Open the hosted CRM and use Copy this CRM link there to share across networks.';return;}
  return copyDriveText(location.origin+'/');
}
function openDriveImport(target='clients'){
  navigate('data');document.getElementById('driveImportTarget').value=target;document.getElementById('driveImportCard').scrollIntoView({behavior:'smooth',block:'start'});document.getElementById('driveImportLink').focus();
}
async function initializeDriveImportLinks(){
  renderDriveServerNote();
  try{await refreshDriveImportLinks();}catch(error){document.getElementById('driveImportMessage').textContent=error.message;}
  clearInterval(driveLinksPoll);driveLinksPoll=setInterval(()=>{if(!document.hidden&&!driveImportBusy)refreshDriveImportLinks().catch(error=>{document.getElementById('driveImportMessage').textContent=error.message;});},10000);
}
function renderDriveServerNote(){
  const local=['localhost','127.0.0.1','[::1]'].includes(location.hostname);
  document.getElementById('driveServerNote').textContent=driveStorageInfo.engine==='postgresql'?'Shared PostgreSQL database connected. Saved records and Drive links are kept outside this web server and survive web-server restarts. Users connected to this database see the same data.':local?'You are on localhost using SQLite. These links and uploads stay on this server; they are not automatically copied to Render. Save/import on the hosted CRM so everyone using its URL sees the same data.':'Everyone using '+location.origin+' sees the links and records saved on this CRM server. Persistent hosting storage is required to keep this SQLite database across restarts.';
}
