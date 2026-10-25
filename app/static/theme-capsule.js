'use strict';
const themeOverrides=['accent','button_hover','bg','surface','text','muted','ink','logo-filter','default-brand-logo','landscape-image'];
let themeReload=0;
async function reloadTheme(){
 const previous=[...document.querySelectorAll('link[rel=stylesheet]')].find(link=>new URL(link.href).pathname==='/theme.css');
 if(!previous)return;
 const id=++themeReload,next=previous.cloneNode();next.media='not all';next.href='/theme.css?appearance='+Date.now()+'-'+id;
 await new Promise((resolve,reject)=>{next.onload=resolve;next.onerror=()=>{next.remove();reject(Error('Theme unavailable'));};previous.after(next);});
 let scene;
 function read(rules){for(const rule of rules){if(rule.cssRules){if(!rule.conditionText||matchMedia(rule.conditionText).matches)read(rule.cssRules);}else if(rule.style?.getPropertyValue('--landscape-image'))scene=rule.style.getPropertyValue('--landscape-image');}}
 read(next.sheet.cssRules);
 const source=scene?.match(/^url\(["']?(.*?)["']?\)$/)?.[1];
 if(source){const image=new Image();image.src=source;try{await image.decode();}catch{next.remove();throw Error('Background unavailable');}}
 if(id!==themeReload){next.remove();return;}
 next.media=previous.media||'all';previous.remove();
 for(const key of themeOverrides)document.documentElement.style.removeProperty('--'+key);
 document.documentElement.style.removeProperty('color-scheme');document.body.style.removeProperty('background');
 document.dispatchEvent(new CustomEvent('gatearr:themeapplied'));
}
window.GatearrTheme={pending:null,reload(){const work=reloadTheme();this.pending=work;work.finally(()=>{if(this.pending===work)this.pending=null;}).catch(()=>{});return work;}};
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
   await window.GatearrTheme.reload();
   document.dispatchEvent(new CustomEvent('gatearr:themechange',{detail:{mode:button.value}}));
  }catch{select(previous);let notice=capsule.querySelector('[role=alert]');if(!notice){notice=document.createElement('span');notice.setAttribute('role','alert');capsule.append(notice);}notice.textContent=document.body.dataset.failed;}
  finally{pending=false;}
 });
}

}
bindCapsules();document.addEventListener('gatearr:headerupdated',bindCapsules);
