let quoteSaarthiSession=null;
let quoteSaarthiSubmitting=false;
try{quoteSaarthiSession=sessionStorage.getItem('hk_quotesaarthi_session');}catch(_){}
function rememberQuoteSaarthiSession(value){
  quoteSaarthiSession=value;
  try{if(value)sessionStorage.setItem('hk_quotesaarthi_session',value);else sessionStorage.removeItem('hk_quotesaarthi_session');}catch(_){}
}
function resetQuoteSaarthiConversation(){
  if(quoteSaarthiSubmitting)return;
  rememberQuoteSaarthiSession(null);
  document.getElementById('chatBody').replaceChildren();
  addChatMessage('Namaste! Main QuoteSaarthi hoon. Product search, vendor comparison aur draft quotation mein help kar sakta hoon. Quote ke liye product, quantity aur confirmed GST rate batayein.');
}
async function quoteSaarthiRequest(message,context,mode){
  const response=await fetch('/api/quotesaarthi/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,context,mode,session_id:quoteSaarthiSession})});
  const result=await response.json();
  if(result.conversation_expired)rememberQuoteSaarthiSession(null);
  if(!response.ok||!result.ok)throw new Error(result.error||'QuoteSaarthi request failed.');
  if(result.session_id)rememberQuoteSaarthiSession(result.session_id);
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
