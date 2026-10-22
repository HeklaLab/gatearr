'use strict';
(()=>{
 const groupForm=document.getElementById('group-editor');
 const groupTabs=document.querySelector('[data-group-tabs]');
 if(groupForm&&groupTabs){
  const selectTab=key=>{
   if(!['members','emby','seerr','access'].includes(key))key='members';
   groupForm.querySelector('[name=active_tab]').value=key;
   for(const panel of groupForm.querySelectorAll('[data-group-panel]'))panel.hidden=panel.dataset.groupPanel!==key;
   for(const link of groupTabs.querySelectorAll('[data-group-tab]')){
    if(link.dataset.groupTab===key)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');
   }
  };
  groupForm.addEventListener('invalid',event=>{
   const panel=event.target.closest('[data-group-panel]');if(panel)selectTab(panel.dataset.groupPanel);
  },true);
  groupTabs.addEventListener('click',event=>{
   const link=event.target.closest('[data-group-tab]');
   if(!link||event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
   event.preventDefault();selectTab(link.dataset.groupTab);
   const url=new URL(location.href);url.searchParams.set('tab',link.dataset.groupTab);history.pushState(null,'',url);
  });
  window.addEventListener('popstate',()=>selectTab(new URL(location.href).searchParams.get('tab')||'members'));
 }

 for(const time of document.querySelectorAll('time[data-timestamp]'))time.textContent=new Date(Number(time.dataset.timestamp)*1000).toLocaleString(document.documentElement.lang);
 for(const editor of document.querySelectorAll('[data-schedules]')){
  let next=Math.max(-1,...[...editor.querySelectorAll('input[type=hidden]')].map(input=>Number(input.value)))+1;
  editor.addEventListener('click',event=>{
   if(event.target.closest('[data-remove-schedule]')){event.target.closest('.schedule-row').remove();return;}
   if(!event.target.closest('[data-add-schedule]'))return;
   const row=editor.querySelector('template').content.cloneNode(true),index=next++,key=editor.dataset.schedules;
   row.querySelector('input[type=hidden]').value=index;
   const inputs=[row.querySelector('select'),...row.querySelectorAll('input:not([type=hidden])')];
   inputs.forEach((input,i)=>input.name=`${key}_${index}_${['day','start','end'][i]}`);
   editor.querySelector('[data-schedule-rows]').append(row);
  });
 }
 for(const row of document.querySelectorAll('[data-group-policy]')){const manage=row.querySelector('input[name=permission]'),values=row.querySelector('[data-group-values]');manage.addEventListener('change',()=>{values.disabled=!manage.checked;});}
 const workspace=document.querySelector('[data-permission-user]');if(!workspace)return;
 let initial=workspace.dataset.snapshot||null;
 async function check(){if(document.hidden)return;try{
  const response=await fetch(`/admin/users/${workspace.dataset.permissionUser}/permissions/status?service=${workspace.dataset.service}`,{credentials:'same-origin'});if(!response.ok)return;
  const state=await response.json();const time=workspace.querySelector('time[data-timestamp]');if(time&&state.checked_at)time.textContent=new Date(state.checked_at*1000).toLocaleString(document.documentElement.lang);if(initial!==null&&initial!==state.hash)workspace.querySelector('.permission-refresh-notice').hidden=false;initial??=state.hash;
 }catch{/* Keep the current form on a transient network failure. */}}
 check();setInterval(check,60000);
})();
