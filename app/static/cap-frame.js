/* Cap instrumentation needs eval. Keep it in this opaque sandbox, never the parent page. */
'use strict';
(()=>{const bootstrap=document.currentScript,expected=bootstrap.dataset.origin,nonce=bootstrap.nonce;let started=false;
window.addEventListener('message',event=>{if(started||event.source!==parent||event.origin!==expected||event.data?.type!=='gatearr:cap-run'||typeof event.data.code!=='string'||event.data.code.length>200000)return;started=true;const script=document.createElement('script');script.nonce=nonce;script.textContent=event.data.code;document.body.append(script);const onload=window.onload;window.onload=null;if(typeof onload==='function')onload();});})();
