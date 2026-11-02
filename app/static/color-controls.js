'use strict';
(() => {
 function toHex(value){
  const ctx=document.createElement('canvas').getContext('2d');ctx.fillStyle='#000000';ctx.fillStyle=value||'#000000';const normalized=ctx.fillStyle;
  if(/^#[0-9a-f]{6}$/i.test(normalized))return normalized;
  const rgb=normalized.match(/[\d.]+/g);return rgb&&rgb.length>=3?'#'+rgb.slice(0,3).map(n=>Math.round(Number(n)).toString(16).padStart(2,'0')).join(''):'#000000';
 }
 function enhance(input){
  if(input.dataset.colorEnhanced)return;input.dataset.colorEnhanced='true';
  const label=input.getAttribute('aria-label')||input.closest('label')?.childNodes[0]?.textContent?.trim()||input.name||'Color';
  const wrap=document.createElement('span'),hex=document.createElement('input');wrap.className='gatearr-color';
  hex.type='text';hex.className='gatearr-color-hex';hex.maxLength=7;hex.pattern='#[0-9a-fA-F]{6}';hex.autocomplete='off';hex.spellcheck=false;hex.setAttribute('aria-label',label+' · HEX');
  input.setAttribute('aria-label',label);input.parentNode.insertBefore(wrap,input);wrap.append(input,hex);
  const sync=()=>{hex.value=input.value.toUpperCase();hex.disabled=input.disabled;hex.setCustomValidity('');};sync();
  input.addEventListener('input',sync);input.addEventListener('change',sync);
  hex.addEventListener('input',()=>{if(!/^#[0-9a-f]{6}$/i.test(hex.value))return;input.value=hex.value;input.dispatchEvent(new Event('input',{bubbles:true}));});
  hex.addEventListener('change',()=>{if(/^#[0-9a-f]{6}$/i.test(hex.value)){input.value=hex.value;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));}else sync();});
  hex.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();hex.dispatchEvent(new Event('change'));}if(e.key==='Escape'){e.preventDefault();sync();}});
  if(input.closest('.studio-color-control'))input.closest('.studio-color-control').querySelector('code')?.remove();
 }
 function bind(root=document){if(root.matches?.('input[type=color]'))enhance(root);root.querySelectorAll?.('input[type=color]').forEach(enhance);}
 window.GatearrColor={enhance,bind,toHex};bind();
 new MutationObserver(records=>{for(const r of records)for(const n of r.addedNodes)if(n.nodeType===1)bind(n);}).observe(document.body,{childList:true,subtree:true});
})();
