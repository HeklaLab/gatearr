'use strict';
document.addEventListener('click',event=>{for(const menu of document.querySelectorAll('.account-menu[open]'))if(!menu.contains(event.target))menu.open=false;});
document.addEventListener('keydown',event=>{if(event.key==='Escape')for(const menu of document.querySelectorAll('.account-menu[open]')){menu.open=false;menu.querySelector('summary').focus();}});
document.addEventListener('error',event=>{if(event.target.matches?.('[data-user-avatar]'))event.target.hidden=true;},true);
document.addEventListener('gatearr:saved',event=>{if(event.detail.action.pathname==='/language')location.assign(location.pathname+location.search);if(event.detail.action.pathname.endsWith('/photo'))fetch(location.href,{credentials:'same-origin'}).then(r=>r.text()).then(html=>{const doc=new DOMParser().parseFromString(html,'text/html');const next=doc.querySelector('.topbar-modern');if(next){document.querySelector('.topbar-modern').replaceWith(next);document.dispatchEvent(new CustomEvent('gatearr:headerupdated'));}});});

document.addEventListener('change',e=>{if(e.target.matches('[data-delete-mode]')){const box=e.target.closest('form').querySelector('[data-delete-confirm]');box.hidden=e.target.value!=='users';box.disabled=box.hidden;}});
