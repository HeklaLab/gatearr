window.CAP_SCRIPT_NONCE=document.currentScript.nonce;
window.CAP_CUSTOM_WASM_URL='/static/cap/cap_wasm_bg.wasm';
window.CAP_CUSTOM_HASHWX_URL='/static/cap/hashwx.wasm';

window.CAP_PAKO_URL='/static/cap/pako_inflate.min.js';
// Keep entered credentials in place when the challenge has not been completed.
document.addEventListener('submit',event=>{
 const form=event.target,widget=form.querySelector('cap-widget');
 if(!widget||form.querySelector('input[name="cap-token"]')?.value)return;
 event.preventDefault();event.stopImmediatePropagation();
 let notice=form.querySelector('.captcha-required');if(!notice){notice=document.createElement('p');notice.className='captcha-required';notice.setAttribute('role','alert');widget.after(notice);}
 notice.textContent=widget.dataset.requiredMessage;widget.shadowRoot?.querySelector('[role=button]')?.focus();
},true);
document.addEventListener('solve',event=>{if(event.target.matches('cap-widget'))event.target.closest('form')?.querySelector('.captcha-required')?.remove();});
