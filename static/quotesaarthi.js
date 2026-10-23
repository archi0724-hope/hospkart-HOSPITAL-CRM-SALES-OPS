let quoteSaarthiSession=null;
let quoteSaarthiSubmitting=false;
let quoteKnowledgeLoading=false;
async function refreshQuoteSaarthiKnowledge() {
  if(quoteKnowledgeLoading)return;
  quoteKnowledgeLoading=true;
  const status=document.getElementById('quoteKnowledgeStatus');
  if(status)status.textContent='Checking saved CRM data…';
  try {
    const response=await fetch('/api/quotesaarthi/knowledge',{cache:'no-store',signal:AbortSignal.timeout(20000)});
    const result=await response.json();
    if(!response.ok||!result.ok)throw new Error(result.error||'CRM knowledge unavailable.');
    if(status)status.textContent='Live CRM · '+result.workspace_records+' records · revision '+result.revision+' · '+(result.checks.passed?'data checks passed':result.checks.issues.length+' data issues to review');
  }catch(error){if(status)status.textContent='Live CRM unavailable. Retry the knowledge check.';}
  finally{quoteKnowledgeLoading=false;}
}
try{quoteSaarthiSession=sessionStorage.getItem('hk_quotesaarthi_session');}catch(_){}
function rememberQuoteSaarthiSession(value){
  quoteSaarthiSession=value;
  try{if(value)sessionStorage.setItem('hk_quotesaarthi_session',value);else sessionStorage.removeItem('hk_quotesaarthi_session');}catch(_){}
}
function resetQuoteSaarthiConversation(){
  if(quoteSaarthiSubmitting)return;
  rememberQuoteSaarthiSession(null);
  document.getElementById('chatBody').replaceChildren();
  addChatMessage('Namaste! Ask me about saved CRM leads, queries, complaints, follow-ups, or product prices and draft quotations. CRM answers refresh from the shared database automatically.');
}
async function quoteSaarthiRequest(message,context,mode){
  const selected=context?.selected_client;
  const references={selected_client:selected?{id:selected.id,workspaceScope:selected.workspaceScope}:null,current_view:context?.current_view};
  const response=await fetch('/api/quotesaarthi/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,context:references,mode,session_id:quoteSaarthiSession})});
  const result=await response.json();
  if(result.conversation_expired)rememberQuoteSaarthiSession(null);
  if(!response.ok||!result.ok)throw new Error(result.error||'QuoteSaarthi request failed.');
  if(result.session_id)rememberQuoteSaarthiSession(result.session_id);
  if(result.knowledge)refreshQuoteSaarthiKnowledge();
  return result;
}
function renderQuoteSaarthiExports(message,exports){
  if(!exports?.length)return;
  const token=quoteSaarthiSession;
  const controls=document.createElement('div');controls.className='quotation-downloads';
  for(const file of exports){
    const button=document.createElement('button');button.className='btn';button.type='button';button.textContent='Download '+file.format.toUpperCase();
    button.addEventListener('click',async()=>{
      button.disabled=true;
      try{
        const response=await fetch('/api/quotesaarthi/download/'+encodeURIComponent(file.name),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:token})});
        if(!response.ok)throw new Error('Export is unavailable. Generate the draft again in this conversation.');
        const blob=await response.blob(),url=URL.createObjectURL(blob),link=document.createElement('a');
        link.href=url;link.download=file.name;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
      }catch(error){toast(error.message);}finally{button.disabled=false;}
    });
    controls.appendChild(button);
  }
  message.appendChild(controls);
}
