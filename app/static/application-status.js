'use strict';
(() => {
 let timer,controller;
 async function update(){
  if(!document.querySelector('[data-application-health]'))return;
  controller?.abort();controller=new AbortController();const signal=controller.signal;
  try{
   const response=await fetch('/api/application-status',{credentials:'same-origin',cache:'no-store',signal});if(!response.ok)throw Error('unavailable');const values=await response.json();if(signal.aborted)return;
   render(values);
  }catch(e){if(e.name!=='AbortError')render({});}
 }
 function render(values){document.querySelectorAll('[data-application-health]').forEach(el=>{
  const state=['online','offline'].includes(values[el.dataset.applicationHealth])?values[el.dataset.applicationHealth]:'unknown';el.dataset.state=state;const labels=JSON.parse(el.dataset.labels);el.querySelector('[data-health-label]').textContent=labels[state];
 });document.querySelectorAll('[data-application-warning]').forEach(el=>{el.hidden=values[el.dataset.applicationWarning]!=='offline';});}
 function bind(){clearInterval(timer);controller?.abort();if(document.querySelector('[data-application-health]')){update();timer=setInterval(update,60000);}}
 document.addEventListener('gatearr:navigated',bind);window.addEventListener('pagehide',()=>{clearInterval(timer);controller?.abort();});bind();
})();
