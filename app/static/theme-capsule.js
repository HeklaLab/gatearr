'use strict';
function bindCapsules(){for(const capsule of document.querySelectorAll('.theme-capsule:not([data-theme-bound])')){
 capsule.dataset.themeBound='true';
 const buttons=[...capsule.querySelectorAll('button')];let pending=false;
 const select=button=>buttons.forEach((b,i)=>{b.setAttribute('aria-pressed',String(b===button));if(b===button)capsule.style.setProperty('--theme-slot',i);});
 select(buttons.find(b=>b.getAttribute('aria-pressed')==='true')||buttons[2]);
 capsule.addEventListener('submit',async event=>{
  event.preventDefault();const button=event.submitter;if(!button||pending)return;pending=true;
  const previous=buttons.find(b=>b.getAttribute('aria-pressed')==='true'),data=new FormData(capsule);data.set('theme',button.value);select(button);
  try{
   const response=await fetch('/account/theme',{method:'POST',body:data,credentials:'same-origin'});if(!response.ok)throw Error();
   if(response.redirected&&new URL(response.url).pathname==='/login'){location.assign(response.url);return;}
   const sheet=[...document.querySelectorAll('link[rel=stylesheet]')].find(link=>new URL(link.href).pathname==='/theme.css');
   if(sheet)sheet.href='/theme.css?appearance='+Date.now();
   for(const key of ['accent','button_hover','bg','surface','text','muted','ink','--logo-filter','--default-brand-logo'])document.documentElement.style.removeProperty(key.startsWith('--')?key:'--'+key);
   document.documentElement.style.removeProperty('color-scheme');document.body.style.removeProperty('background');
   document.dispatchEvent(new CustomEvent('gatearr:themechange',{detail:{mode:button.value}}));
  }catch{select(previous);let notice=capsule.querySelector('[role=alert]');if(!notice){notice=document.createElement('span');notice.setAttribute('role','alert');capsule.append(notice);}notice.textContent=document.body.dataset.failed;}
  finally{pending=false;}
 });
}

}
bindCapsules();document.addEventListener('gatearr:headerupdated',bindCapsules);
