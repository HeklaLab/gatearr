'use strict';
window.GatearrPage.listen(document,'change',async event=>{
 const input=event.target;if(!input.matches('[data-upload-target]')||!input.files[0])return;
 const form=input.closest('form'),data=new FormData();data.set('csrf',form.elements.csrf.value);data.set('icon_file',input.files[0]);input.disabled=true;input.setCustomValidity('');
 try{const response=await fetch('/admin/assets',{method:'POST',body:data,headers:{Accept:'application/json'}});if(!response.ok)throw Error();form.elements.namedItem(input.dataset.uploadTarget).value=(await response.json()).url;}
 catch{input.setCustomValidity(input.dataset.uploadError);input.reportValidity();}finally{input.disabled=false;}
});
