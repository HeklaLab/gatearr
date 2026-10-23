'use strict';
(() => {
 const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms)),busy=new WeakMap(),forms=new WeakSet();
 function start(button,spinOnly=false){if(!button||busy.has(button))return;const mark=document.createElement('span');mark.className='button-feedback is-loading';mark.setAttribute('aria-hidden','true');button.append(mark);button.classList.add('is-saving');button.setAttribute('aria-busy','true');if(spinOnly){busy.set(button,{mark,at:performance.now()});return;}const label=document.createElement('span');label.hidden=true;for(const child of [...button.childNodes])if(child!==mark)label.append(child);button.prepend(label);const text=document.createElement('span');text.textContent=button.dataset.feedback==='test'?button.dataset.testing:(document.body.dataset.saving||'Saving…');button.insertBefore(text,mark);busy.set(button,{mark,label,text,at:performance.now()});}
 async function finish(button,success){const state=busy.get(button);if(!state)return;await wait(Math.max(0,500-(performance.now()-state.at)));state.mark.className='button-feedback '+(success?'is-success':'is-error');state.mark.textContent=success?'✓':'!';state.text.textContent=success?(button.dataset.feedback==='test'?button.dataset.tested:(document.body.dataset.saved||'Saved')):(document.body.dataset.failed||'Failed');button.classList.remove('is-saving');button.classList.toggle('is-saved',success);button.removeAttribute('aria-busy');await wait(success?700:1600);state.mark.remove();state.text.remove();state.label.replaceWith(...state.label.childNodes);button.classList.remove('is-saved');busy.delete(button);}
 document.addEventListener('submit',async event=>{
  if(event.defaultPrevented)return;const form=event.target,button=event.submitter||form.querySelector('button:not([type=button])');if(!button||form.method.toLowerCase()!=='post')return;
  const action=new URL(button.getAttribute('formaction')||form.getAttribute('action')||location.href,location.href);if(action.origin!==location.origin)return;
  if(busy.has(button)||forms.has(form)){event.preventDefault();return;}
  const native=!action.pathname.startsWith('/admin/')&&!['/account/preferences','/account/language','/language'].includes(action.pathname)||action.pathname.endsWith('/assist')||action.pathname.startsWith('/admin/setup/')||['preview','test'].includes(button.value)||action.pathname.includes('smtp-test')||action.pathname==='/admin/updates/check';
  if(native&&(!form.dataset.dynamic||(['preview','test'].includes(button.value)&&action.pathname!=='/admin/security/captcha'))){start(button,true);return;}
  event.preventDefault();const data=new FormData(form,button);start(button);button.disabled=true;forms.add(form);const locked=[...form.elements].filter(e=>!e.disabled&&/^(INPUT|SELECT|TEXTAREA)$/.test(e.tagName));locked.forEach(e=>e.disabled=true);form.querySelector('.save-error')?.remove();
  try{
   const response=await fetch(action.href,{method:'POST',body:data,credentials:'same-origin',redirect:'follow'});
   if(response.redirected&&new URL(response.url).pathname==='/login'){location.assign(response.url);return;}
   if(!response.ok){const html=await response.text(),doc=new DOMParser().parseFromString(html,'text/html');const text=doc.querySelector('main .card p,main .lead,[role=alert]')?.textContent||`HTTP ${response.status}`;let notice=form.querySelector('.save-error');if(!notice){notice=document.createElement('p');notice.className='save-error';notice.setAttribute('role','alert');form.append(notice);}notice.textContent=text;document.dispatchEvent(new CustomEvent('gatearr:savefailed',{detail:{form,action}}));await finish(button,false);return;}
   const doc=new DOMParser().parseFromString(await response.text(),'text/html');let successful=true;if(button.dataset.feedback==='test'){const service=data.get('service')||'smtp';const results=[...doc.querySelectorAll('[data-connection]')];successful=action.pathname==='/admin/security/captcha'?doc.querySelector('[data-cap-health]')?.dataset.capHealth==='true':service==='all'?results.length>0&&results.every(result=>result.dataset.connectionOk==='true'):results.some(result=>result.dataset.connection===service&&result.dataset.connectionOk==='true');}
   await finish(button,successful);
   if(form.dataset.dynamic){
    if(form.dataset.dynamic==='connections'){
     for(const current of document.querySelectorAll('#connection-overview,[id^="connection-result-"]')){const updated=doc.getElementById(current.id);if(updated)current.replaceChildren(...updated.childNodes);}
     for(const panel of document.querySelectorAll('.integration-detail')){const updated=doc.getElementById(panel.id)?.querySelector(':scope > summary .connection-indicator'),indicator=panel.querySelector(':scope > summary .connection-indicator');if(updated&&indicator)indicator.replaceWith(updated);}
     form.querySelectorAll('input[type=password]').forEach(input=>input.value='');
    }else if(form.dataset.dynamic==='mail'){
     const stamp=doc.querySelector('#mail-editor-form input[name=source_hash]');if(stamp)form.elements.source_hash.value=stamp.value;
    }else{
     const region=form.closest('[data-save-region]'),updated=region?.id&&doc.getElementById(region.id);
     if(updated){const opened=[...region.querySelectorAll('details')].map(d=>d.open);region.replaceChildren(...updated.childNodes);region.querySelectorAll('details').forEach((d,i)=>d.open=opened[i]??d.open);}
    }
    document.dispatchEvent(new CustomEvent('gatearr:saved',{detail:{form,doc,action,data,success:successful}}));
   }else location.assign(response.redirected?response.url:location.href);
  }catch{document.dispatchEvent(new CustomEvent('gatearr:savefailed',{detail:{form,action}}));await finish(button,false);}finally{button.disabled=false;locked.forEach(e=>e.disabled=false);forms.delete(form);}
 });
 document.addEventListener('click',event=>{const button=event.target.closest('[data-command=publish],[data-action=publish]');if(button)start(button);},true);
 window.addEventListener('gatearr:feedback',async event=>{for(const button of document.querySelectorAll('[data-command=publish],[data-action=publish]'))if(busy.has(button))await finish(button,event.detail.success);});
 window.addEventListener('pageshow',()=>{for(const button of document.querySelectorAll('button[aria-busy]')){const state=busy.get(button);button.removeAttribute('aria-busy');button.classList.remove('is-saving','is-saved');button.querySelector('.button-feedback')?.remove();if(state?.label){state.text.remove();state.label.replaceWith(...state.label.childNodes);}busy.delete(button);}});
})();
