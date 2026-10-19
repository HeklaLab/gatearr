'use strict';
document.querySelectorAll('select[name=kind]').forEach(select=>{
 const form=select.form;
 const update=()=>form.querySelectorAll('[data-kind]').forEach(label=>{label.hidden=label.dataset.kind!==select.value;label.querySelectorAll('input,select').forEach(input=>input.disabled=label.hidden);});
 select.addEventListener('change',update);update();
});
