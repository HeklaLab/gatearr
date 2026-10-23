'use strict';
for(const link of document.querySelectorAll('[data-open-connection]'))link.addEventListener('click',()=>{for(const panel of document.querySelectorAll('.integration-detail'))panel.open=panel.id==='connection-'+link.dataset.openConnection;});
const selected=new URLSearchParams(location.search).get('connection');
const active=location.hash.startsWith('#connection-')?location.hash.slice(1):selected?'connection-'+selected:'';
if(active){const detail=document.getElementById(active);if(detail?.classList.contains('integration-detail')){for(const panel of document.querySelectorAll('.integration-detail'))panel.open=panel===detail;detail.scrollIntoView({block:'start'});}}
