'use strict';
(()=>{
 let lifetime=new AbortController();
 window.GatearrPage={
  get signal(){return lifetime.signal;},
  listen(target,type,listener,options={}){target.addEventListener(type,listener,{...(typeof options==='boolean'?{capture:options}:options),signal:lifetime.signal});},
  reset(){lifetime.abort();lifetime=new AbortController();delete this.beforeLeave;}
 };
 function bind(){document.querySelectorAll('.user-tabs,.admin-tabs,.studio-pages').forEach(nav=>nav.classList.add('local-capsule'));}
 bind();document.addEventListener('gatearr:navigated',bind);
})();

// Presentation-only disclosure; existing photo endpoints and validation are retained.
document.addEventListener('click',event=>{
 const button=event.target.closest('[data-photo-toggle]');if(!button)return;
 const form=document.getElementById(button.getAttribute('aria-controls'));if(!form)return;
 form.hidden=!form.hidden;button.setAttribute('aria-expanded',String(!form.hidden));
 if(!form.hidden)form.querySelector('.upload-picker')?.focus();
});
document.addEventListener('invalid',event=>{
 for(let parent=event.target.parentElement;parent;parent=parent.parentElement)if(parent.matches('details'))parent.open=true;
},true);
