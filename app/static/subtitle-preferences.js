'use strict';
(()=>{
 function refresh(root){
  const list=root.querySelector('[data-subtitle-rows]'),add=root.querySelector('[data-subtitle-add]');if(!list||!add)return;
  const rows=[...list.querySelectorAll('[data-subtitle-row]')],choices=rows.map(row=>row.querySelector('select').value);
  root.querySelector('[data-subtitle-count]').textContent=rows.length;
  add.disabled=root.dataset.saving==='true'||rows.length>=Number(root.dataset.capacity);
  for(const row of rows)row.querySelector('[data-subtitle-remove]').disabled=root.dataset.saving==='true'||row.hasAttribute('data-subtitle-locked');
  root.querySelector('[data-subtitle-empty]').hidden=rows.length>0;
  for(const row of rows){const select=row.querySelector('select');for(const option of select.options)option.disabled=!!option.value&&option.value!==select.value&&choices.includes(option.value);}
 }
 document.querySelectorAll('[data-subtitle-preferences]').forEach(refresh);
 window.GatearrPage.listen(document,'click',event=>{
  const root=event.target.closest('[data-subtitle-preferences]');if(!root)return;
  const list=root.querySelector('[data-subtitle-rows]'),add=root.querySelector('[data-subtitle-add]');if(!list||!add)return;
  if(event.target.closest('[data-subtitle-add]')){
   if(add.disabled)return;
   list.append(root.querySelector('[data-subtitle-template]').content.cloneNode(true));refresh(root);
   requestAnimationFrame(()=>{const row=list.lastElementChild;(row.querySelector('.guided-select-trigger')||row.querySelector('select')).focus();});
  }
  const remove=event.target.closest('[data-subtitle-remove]');
  if(remove&&!remove.disabled){const row=remove.closest('[data-subtitle-row]'),next=row.nextElementSibling||row.previousElementSibling;row.remove();refresh(root);(next?.querySelector('.guided-select-trigger')||(!add.disabled?add:root.querySelector('button:not([type=button])'))).focus();}
 });
 window.GatearrPage.listen(document,'submit',event=>{if(event.target.matches('form[action="/account/subtitles/language"]')){const root=event.target.closest('[data-subtitle-preferences]');root.dataset.saving='true';refresh(root);}});
 window.GatearrPage.listen(document,'gatearr:savefailed',event=>{const root=event.detail.form.closest('[data-subtitle-preferences]');if(root){delete root.dataset.saving;refresh(root);}});
 window.GatearrPage.listen(document,'change',event=>{const root=event.target.closest('[data-subtitle-preferences]');if(root)refresh(root);});
 window.GatearrPage.listen(document,'gatearr:saved',event=>{
  if(event.detail.action.pathname!=='/account/subtitles/language')return;
  const root=document.querySelector('[data-subtitle-preferences]'),fresh=event.detail.doc.getElementById('subtitle-preferences');if(!root)return;
  if(!fresh){root.remove();return;}
  delete root.dataset.saving;root.dataset.capacity=fresh.dataset.capacity;refresh(root);
 });
})();
