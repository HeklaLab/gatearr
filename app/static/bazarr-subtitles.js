'use strict';
(()=>{
 function policy(root){const select=root.querySelector('[data-subtitle-policy]'),days=root.querySelector('[data-subtitle-lock-days]');if(select&&days){days.hidden=select.value!=='days';days.querySelector('input').disabled=days.hidden;}}
 document.querySelectorAll('[data-bazarr-settings]').forEach(policy);
 window.GatearrPage.listen(document,'change',event=>{if(event.target.matches('[data-subtitle-policy]'))policy(event.target.closest('[data-bazarr-settings]'));});
 window.GatearrPage.listen(document,'gatearr:saved',()=>document.querySelectorAll('[data-bazarr-settings]').forEach(policy));
 window.GatearrPage.listen(document,'click',async event=>{
 const button=event.target.closest('[data-bazarr-load]');if(!button)return;
 const root=button.closest('[data-bazarr-settings]');
 const select=root.querySelector('[data-bazarr-profile]'),status=root.querySelector('[data-bazarr-status]');
 if(!button||!select)return;

  button.disabled=true;status.textContent='';
  try{
   const response=await fetch('/admin/bazarr/subtitle-profiles',{headers:{Accept:'application/json'}});
   if(!response.ok)throw Error();
   const data=await response.json(),selected=select.value;
   select.replaceChildren(new Option(root.dataset.selectProfile,''));
   for(const profile of data.profiles)select.add(new Option(profile.name,String(profile.id),false,String(profile.id)===selected));
   status.textContent=data.profiles.length?'':root.dataset.noProfiles;
  }catch(error){status.textContent=root.dataset.loadError;}
  finally{button.disabled=false;}
 });
})();
