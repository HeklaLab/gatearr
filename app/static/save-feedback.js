'use strict';
(() => {
 const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms)),busy=new WeakMap();
 function start(button){if(!button||busy.has(button))return;const mark=document.createElement('span');mark.className='button-feedback is-loading';mark.setAttribute('aria-hidden','true');button.append(mark);button.setAttribute('aria-busy','true');busy.set(button,{mark,at:performance.now()});}
 async function finish(button,success){const state=busy.get(button);if(!state)return;await wait(Math.max(0,500-(performance.now()-state.at)));state.mark.className='button-feedback '+(success?'is-success':'is-error');state.mark.textContent=success?'✓':'!';button.removeAttribute('aria-busy');await wait(success?700:1600);state.mark.remove();busy.delete(button);}
 document.addEventListener('submit',async event=>{
  if(event.defaultPrevented)return;const form=event.target,button=event.submitter||form.querySelector('button:not([type=button])');if(!button||form.method.toLowerCase()!=='post')return;
  const action=new URL(form.action,location.href);if(action.origin!==location.origin)return;
  if(busy.has(button)){event.preventDefault();return;}
  const native=!action.pathname.startsWith('/admin/')&&!['/account/preferences','/account/language','/language'].includes(action.pathname)||action.pathname.startsWith('/admin/setup/')||['preview','test'].includes(button.value)||action.pathname.includes('smtp-test');
  if(native){start(button);return;}
  event.preventDefault();const data=new FormData(form,button);start(button);button.disabled=true;
  try{
   const response=await fetch(action.href,{method:'POST',body:data,credentials:'same-origin',redirect:'follow'});
   if(response.redirected&&new URL(response.url).pathname==='/login'){location.assign(response.url);return;}
   if(!response.ok){const html=await response.text(),doc=new DOMParser().parseFromString(html,'text/html');const text=doc.querySelector('main .card p,main .lead,[role=alert]')?.textContent||`HTTP ${response.status}`;let notice=form.querySelector('.save-error');if(!notice){notice=document.createElement('p');notice.className='save-error';notice.setAttribute('role','alert');form.append(notice);}notice.textContent=text;await finish(button,false);return;}
   await finish(button,true);location.assign(response.redirected?response.url:location.href);
  }catch{await finish(button,false);}finally{button.disabled=false;}
 });
 document.addEventListener('click',event=>{const button=event.target.closest('[data-command=publish],[data-action=publish]');if(button)start(button);},true);
 window.addEventListener('gatearr:feedback',async event=>{for(const button of document.querySelectorAll('[data-command=publish],[data-action=publish]'))if(busy.has(button))await finish(button,event.detail.success);});
 window.addEventListener('pageshow',()=>{for(const button of document.querySelectorAll('button[aria-busy]')){button.removeAttribute('aria-busy');button.querySelector('.button-feedback')?.remove();busy.delete(button);}});
})();
