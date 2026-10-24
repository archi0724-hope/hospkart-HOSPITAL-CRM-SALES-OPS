let sharedDriveLinks=[];
let driveImportBusy=false;
let driveLinksPoll=null;
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
    name.textContent=item.label;target.textContent=driveTargetLabels[item.target]||item.target;
    const open=document.createElement('a');open.className='btn small';open.textContent='Open Drive file';open.href=item.link;open.target='_blank';open.rel='noopener noreferrer';actions.append(open);
    const action=(label,callback)=>{const button=document.createElement('button');button.type='button';button.className='btn small';button.textContent=label;button.disabled=driveImportBusy;button.addEventListener('click',callback);actions.append(' ',button);};
    action('Copy Drive link',()=>copyDriveText(item.link));
    action(item.target==='leads'?'Connect for sync':'Preview / import',()=>importSharedDriveLink(item));
    action('Remove link',()=>removeDriveImportLink(item));
    row.append(name,target,actions);root.append(row);
  }
  if(!sharedDriveLinks.length){const row=root.insertRow(),cell=row.insertCell();cell.colSpan=3;cell.textContent='No shared Drive links saved yet.';}
}

async function refreshDriveImportLinks(){
  if(driveImportBusy)return;
  const response=await driveRequest();const state=await response.json();sharedDriveLinks=state.links;renderDriveImportLinks();
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

function importSharedDriveLink(item){
  if(item.target==='leads'){
    openSpreadsheetConnection();document.getElementById('sheetLinkInput').value=item.link;invalidateSheetInspection();return;
  }
  return withDriveAction(async()=>{
    const version=dashboardDataVersion;
    document.getElementById('driveImportMessage').textContent='Reading the private workbook from Google Drive…';
    const response=await driveRequest('/download',{id:item.id});
    if(dashboardResetting||version!==dashboardDataVersion)throw new Error('The dashboard changed during download. Review it before importing again.');
    const disposition=response.headers.get('Content-Disposition')||'';
    const extension=/\.xls(?:[";\s]|$)/i.test(disposition)?'.xls':'.xlsx';
    const file=new File([await response.blob()],item.label.replace(/[\\/]/g,'_')+extension,{type:response.headers.get('Content-Type')||''});
    const input={files:[file],value:''};
    if(item.target==='clients')await importExcelFile(input);else await importSegmentExcel(input,item.target);
    document.getElementById('driveImportMessage').textContent='Workbook handed to the Excel import workflow. Check its confirmation/result message; importing is separate from saving a link.';
  });
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
  document.getElementById('driveServerNote').textContent=['localhost','127.0.0.1','[::1]'].includes(location.hostname)?'You are on localhost. These links and uploads stay on this server; they are not automatically copied to Render. Save/import on the hosted CRM so everyone using its URL sees the same data.':'Everyone using '+location.origin+' sees the links and records saved on this CRM server.';
  try{await refreshDriveImportLinks();}catch(error){document.getElementById('driveImportMessage').textContent=error.message;}
  clearInterval(driveLinksPoll);driveLinksPoll=setInterval(()=>{if(!document.hidden&&!driveImportBusy)refreshDriveImportLinks().catch(error=>{document.getElementById('driveImportMessage').textContent=error.message;});},10000);
}
