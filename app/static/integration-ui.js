(()=>{
'use strict';
const reduce=()=>matchMedia('(prefers-reduced-motion:reduce)').matches;
function mark(){
 const opened=document.querySelector('.integration-list>.integration-detail[open]');
 for(const link of document.querySelectorAll('[data-open-connection]')){
  const selected=opened?.id==='connection-'+link.dataset.openConnection;
  if(selected)link.setAttribute('aria-current','true');else link.removeAttribute('aria-current');
  link.setAttribute('aria-controls','connection-'+link.dataset.openConnection);link.setAttribute('aria-expanded',String(selected));
 }
}
function choose(id,remember=true){
 const panel=document.getElementById(id),list=panel?.parentElement;if(!panel?.classList.contains('integration-detail'))return;
 for(const detail of list.querySelectorAll('.integration-detail'))detail.open=detail===panel;
 list.prepend(panel);mark();
 if(remember)history.replaceState(history.state,'',location.pathname+location.search+'#'+id);
 if(!reduce())panel.querySelector('.integration-detail-grid')?.animate([{opacity:0,transform:'translateY(5px)'},{opacity:1,transform:'translateY(0)'}],{duration:240,easing:'ease-out'});
}
// Delegation also covers cards replaced after a connection test or save.
window.GatearrPage.listen(document,'click',event=>{
 const link=event.target.closest('[data-open-connection]');if(!link||event.defaultPrevented||event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
 event.preventDefault();choose('connection-'+link.dataset.openConnection);
 const header=document.querySelector('.integration-list>.integration-detail>summary'),bottom=header?.getBoundingClientRect().bottom;
 if(bottom>innerHeight-24)window.scrollBy({top:bottom-innerHeight+24,behavior:reduce()?'instant':'smooth'});
});
const selected=new URLSearchParams(location.search).get('connection');
const active=location.hash.startsWith('#connection-')?location.hash.slice(1):selected?'connection-'+selected:'';
if(active){
 history.replaceState(history.state,'',location.pathname+location.search);
 choose(active,false);
 const restore=()=>{history.replaceState(history.state,'',location.pathname+location.search+'#'+active);document.getElementById('connection-overview')?.scrollIntoView({block:'start'});};
 if(document.readyState==='complete')restore();else window.GatearrPage.listen(window,'load',restore,{once:true});
}
window.GatearrPage.listen(document,'gatearr:saved',mark);mark();
// Test the current form values without saving or replacing the configured status.
window.GatearrPage.listen(document,'submit',async event=>{
 const form=event.target;if(!form.matches('form[action="/admin/connections/test"]'))return;
 const service=form.elements.service?.value;if(!service||service==='all')return;
 event.preventDefault();event.stopImmediatePropagation();const source=document.getElementById('connection-save-'+service),button=event.submitter,result=document.getElementById('connection-result-'+service);if(!source||button.disabled)return;
 const data=new FormData(source);for(const key of [...data.keys()])if(!['csrf','url','api_key','media_server'].includes(key))data.delete(key);data.set('service',service);button.disabled=true;button.setAttribute('aria-busy','true');const original=button.textContent;button.textContent=button.dataset.testing;button.classList.add('is-saving');const spinner=document.createElement('span');spinner.className='button-feedback is-loading';button.append(spinner);result.querySelector('.save-error')?.remove();
 try{const response=await fetch('/admin/connections/test',{method:'POST',body:data,credentials:'same-origin',headers:{Accept:'application/json'}});if(!response.ok){const doc=new DOMParser().parseFromString(await response.text(),'text/html');throw new Error(doc.querySelector('main .card p,main p,[role=alert]')?.textContent||'HTTP '+response.status)}const reply=await response.json();result.replaceChildren();result.dataset.transient='true';const status=document.createElement('p');status.className=reply.state==='connected'?'sync-green':'sync-red';status.setAttribute('role','status');status.textContent=reply.detail;const note=document.createElement('p');note.className='connection-unsaved';note.textContent=document.body.dataset.unsavedTest||'Test of current values · not saved';result.append(note,status);const d=reply.diagnostics,dl=document.createElement('dl');dl.className='connection-diagnostics';const fields=[['Server',d.host],['Resolved IP',(d.resolved_ips||[]).join(', ')],['Server response',d.server_http_status?'HTTP '+d.server_http_status+' · '+d.server_response_ms+' ms':'—'],['API response',d.interface_only?'—':d.api_http_status?'HTTP '+d.api_http_status+' · '+d.api_response_ms+' ms':'—']];for(const [label,value]of fields){const row=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=JSON.parse(document.body.dataset.diagnosticLabels||'{}')[label]||label;dd.textContent=value||'—';row.append(dt,dd);dl.append(row)}result.append(dl);}
 catch(error){const notice=document.createElement('p');notice.className='save-error';notice.setAttribute('role','alert');notice.textContent=error.message;result.append(notice)}finally{button.disabled=false;button.removeAttribute('aria-busy');button.classList.remove('is-saving');button.textContent=original;}
},true);
for(const form of document.querySelectorAll('[id^=connection-save-]'))form.addEventListener('input',()=>{const result=document.getElementById(form.id.replace('connection-save-','connection-result-'));if(result?.dataset.transient){result.querySelector('.connection-unsaved').textContent=document.body.dataset.retest||'Values changed · test again';result.querySelector('[role=status]')?.remove();delete result.dataset.transient;}});

})();
