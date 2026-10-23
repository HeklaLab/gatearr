(()=>{
'use strict';
const columns=document.querySelector('#footer-columns');if(columns){const select=columns.querySelector('select[name=count]');const update=()=>columns.querySelectorAll('[data-column]').forEach(field=>field.hidden=Number(field.dataset.column)>=Number(select.value));select.addEventListener('change',update);update();}

})();
