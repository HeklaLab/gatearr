'use strict';
(() => {
 const frame=document.querySelector('.tool-frame');const notice=document.querySelector('[data-tool-failure]');
 if(!frame||!notice)return;
 const report=()=>{notice.hidden=false;};
 const signal=window.GatearrPage?.signal;
 window.addEventListener('message',event=>{if(event.origin===location.origin&&event.source===frame.contentWindow&&event.data?.type==='gatearr:tdarr-failure')report();},{signal});
 frame.addEventListener('error',report,{signal});
 frame.addEventListener('load',()=>{
  setTimeout(()=>{
   if(!frame.isConnected)return;
   try{
    const body=frame.contentDocument?.body;
    const text=body?.innerText.trim();
    if(body&&(!text||/^(Tool unavailable|Open this tool|Invalid path)/.test(text)))report();
   }catch{/* Cross-origin native interfaces retain their own isolation. */}
  },8000);
 },{signal});
 document.querySelector('[data-tool-retry]')?.addEventListener('click',()=>{notice.hidden=true;frame.src=frame.src;},{signal});
})();
