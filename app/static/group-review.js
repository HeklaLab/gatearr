(()=>{
const dialog=document.querySelector('[data-group-dialog]');if(!dialog)return;
const q=s=>dialog.querySelector(s),bypass=new WeakSet();let active,submitter,result,index=0,seen=new Set(),controller;
const close=()=>{controller?.abort();dialog.close();};dialog.querySelectorAll('[data-review-close]').forEach(b=>b.addEventListener('click',close));dialog.addEventListener('cancel',()=>controller?.abort());
function show(){
 const user=result.users[index];seen.add(index);q('[data-review-user]').textContent=user.name+' · '+result.group;
 const rows=q('[data-review-rows]');rows.replaceChildren();user.differences.forEach(diff=>{const tr=document.createElement('tr');['service','label','before','after'].forEach((key,column)=>{const td=document.createElement('td');td.dataset.label=dialog.querySelectorAll('thead th')[column].textContent;td.textContent=diff[key];tr.append(td);});rows.append(tr);});
 q('[data-review-empty]').hidden=!!user.differences.length;q('[data-review-empty]').textContent=dialog.dataset.empty;q('.group-review-table').hidden=!user.differences.length;
 q('[data-review-page]').value=String(index);q('[data-review-prev]').disabled=index===0;q('[data-review-next]').disabled=index===result.users.length-1;q('[data-review-confirm]').disabled=seen.size!==result.users.length;
}
q('[data-review-prev]').addEventListener('click',()=>{index--;show();});q('[data-review-next]').addEventListener('click',()=>{index++;show();});q('[data-review-page]').addEventListener('change',e=>{index=Number(e.target.value);show();});
q('[data-review-confirm]').addEventListener('click',()=>{if(!result||seen.size!==result.users.length)return;let token=active.querySelector('[name="review_token"]');if(!token){token=document.createElement('input');token.type='hidden';token.name='review_token';active.append(token);}token.value=result.review_token;dialog.close();bypass.add(active);active.requestSubmit(submitter);});
window.GatearrPage.listen(document,'submit',async event=>{
 const form=event.target;if(!form.matches('[data-group-review]'))return;if(bypass.delete(form))return;
 event.preventDefault();event.stopImmediatePropagation();active=form;submitter=event.submitter;result=null;seen=new Set();index=0;
 q('[data-review-body]').hidden=true;q('[data-review-confirm]').disabled=true;q('[data-review-status]').hidden=false;q('[data-review-status]').textContent=dialog.querySelector('[data-review-status]').dataset.loading||'';
 controller=new AbortController();dialog.showModal();
 try{const data=new FormData(form);if(submitter?.name)data.append(submitter.name,submitter.value);data.set('review_only','on');const response=await fetch(form.action,{method:'POST',body:data,credentials:'same-origin',signal:controller.signal,headers:{Accept:'application/json'}});if(!response.ok){let message=dialog.dataset.failed;try{const html=await response.text();const doc=new DOMParser().parseFromString(html,'text/html');message=doc.querySelector('main .card p,main .lead,[role=alert]')?.textContent||message;}catch{}throw new Error(message);}result=await response.json();if(!result.required){dialog.close();bypass.add(form);form.requestSubmit(submitter);return;}
 const select=q('[data-review-page]');select.replaceChildren();result.users.forEach((u,i)=>{const option=document.createElement('option');option.value=String(i);option.textContent=(i+1)+' / '+result.users.length+' · '+u.name;select.append(option);});q('[data-review-status]').hidden=true;q('[data-review-body]').hidden=false;show();
 }catch(error){if(error.name!=='AbortError')q('[data-review-status]').textContent=error.message;}
},true);
q('[data-review-status]').dataset.loading=q('[data-review-status]').textContent;
})();
