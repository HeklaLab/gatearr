/* Email studio uses the same palette / page / inspector layout as the portal studio. */
'use strict';
(()=>{
 const form=document.querySelector('#mail-editor-form');if(!form)return;
 const canvas=document.querySelector('#rich-editor'),source=form.elements.html,preview=document.querySelector('.mail-preview'),copy=JSON.parse(document.querySelector('#mail-builder-copy').textContent),t=s=>copy[s]||s;
 const make=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=t(text);return n;};
 const layout=make('div'),palette=make('aside'),stage=make('div'),props=make('aside');
 layout.className='studio-workspace mail-builder';palette.className='studio-palette mail-block-palette';stage.className='studio-canvas mail-canvas-wrap';props.className='studio-inspector mail-block-settings';props.setAttribute('aria-label',t('Block settings'));
 const host=document.querySelector('.mail-editor-host');host.before(layout);layout.append(palette,stage,props);stage.append(canvas,preview);host.remove();
 canvas.innerHTML=source.value;canvas.hidden=false;canvas.contentEditable='false';canvas.classList.add('mail-block-canvas');canvas.dataset.empty=t('Drop a block here');document.querySelector('#html-fallback').hidden=true;
 for(const n of [...canvas.childNodes])if(n.nodeType===3){if(n.textContent.trim()){const p=make('p');n.replaceWith(p);p.append(n);}else n.remove();}
 let drag=null,selected=null,mode='edit',history=[],future=[],baseline=null;let initialSubject=form.elements.subject.value;
 const button=(text,fn,icon)=>{const b=make('button',text);b.type='button';b.className=text==='Delete'?'danger':'secondary';if(icon){const i=make('i');i.className='fa-solid fa-'+icon;i.setAttribute('aria-hidden','true');b.prepend(i);}b.onclick=fn;return b;};
 function serialize(){const clone=canvas.cloneNode(true);for(const b of clone.children){for(const key of ['draggable','tabindex','data-selected','aria-label'])b.removeAttribute(key);b.classList.remove('mail-block','mail-drop-target');if(!b.className)b.removeAttribute('class');}return clone.innerHTML;}
 function setView(view){mode=view;canvas.hidden=view!=='edit';preview.hidden=view!=='preview';for(const b of form.querySelectorAll('[data-mail-view]'))b.setAttribute('aria-pressed',String(b.dataset.mailView===view));}
 function sync(record=true){
  source.value=serialize();baseline??=source.value;const dirty=source.value!==baseline||form.elements.subject.value!==initialSubject;document.querySelector('#mail-editor-status').textContent=t(dirty?'Unsaved changes':'Draft ready');const saved=document.querySelector('.mail-saved-status');if(saved)saved.hidden=dirty;if(record&&history.at(-1)!==source.value){history.push(source.value);if(history.length>60)history.shift();future=[];}
  form.querySelector('[data-mail-command=undo]').disabled=history.length<2;form.querySelector('[data-mail-command=redo]').disabled=!future.length;
  const values={app_name:form.dataset.appName,username:'Alex',link:form.dataset.publicUrl+(form.elements.purpose.value==='reset'?'/reset?token=preview':form.elements.purpose.value==='new_season'?'/library/open/preview':'/verify-email?token=preview'),minutes:'30',title:'Fargo',season:'5'},doc=make('div');doc.innerHTML=source.value;
  const replace=s=>s.replace(/\$\{(app_name|username|link|minutes|title|season)\}/g,(_,k)=>values[k]);for(const e of doc.querySelectorAll('*'))for(const a of [...e.attributes])e.setAttribute(a.name,replace(a.value));
  const walker=document.createTreeWalker(doc,NodeFilter.SHOW_TEXT);while(walker.nextNode())walker.currentNode.textContent=replace(walker.currentNode.textContent);
  preview.srcdoc='<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0;padding:24px;background:white;color:#222;font:15px/1.6 Arial"><div style="max-width:640px;margin:auto">'+doc.innerHTML+'</div></body></html>';
 }
 function field(label,value,fn,type='text'){const l=make('label',label),i=make('input');i.type=type;i.value=value??'';i.oninput=()=>{fn(i.value,i);sync();};l.append(i);props.append(l);return i;}
 function valid(v){try{const u=new URL(v);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password;}catch{return false;}}
 function kind(b){return b.tagName==='IMG'?'image':b.tagName==='HR'?'divider':b.tagName==='A'?'button':/^H[123]$/.test(b.tagName)?'heading':b.tagName==='DIV'&&!b.textContent.trim()&&b.style.lineHeight?'spacer':'text';}
 function select(b){
  selected=b;for(const x of canvas.children)x.toggleAttribute('data-selected',x===b);props.replaceChildren(make('h2','Block settings'));
  const tools=make('div');tools.className='studio-buttons';tools.append(button('Move up ↑',()=>{if(b.previousElementSibling)canvas.insertBefore(b,b.previousElementSibling);sync();}),button('Move down ↓',()=>{if(b.nextElementSibling)canvas.insertBefore(b.nextElementSibling,b);sync();}),button('Duplicate',()=>{const c=b.cloneNode(true);b.after(c);wire();select(c);sync();}),button('Delete',()=>{const next=b.nextElementSibling||b.previousElementSibling;b.remove();selected=null;wire();if(next)select(next);else props.replaceChildren(make('h2','Block settings'),make('p','Select a block to configure it.'));sync();}));props.append(tools);
  const type=kind(b);
  if(type==='image'){
   field('Image description',b.alt,v=>b.alt=v);
   const width=field('Image width (px)',b.getAttribute('width')||parseInt(b.style.width,10)||600,(v,i)=>{const n=Number(v),ok=Number.isInteger(n)&&n>=1&&n<=1200;i.setCustomValidity(ok?'':t('Image width (px)'));if(ok){b.width=n;b.style.width=n+'px';b.style.height='auto';b.removeAttribute('height');b.style.maxWidth='100%';}},'number');width.min='1';width.max='1200';
   const l=make('label','Upload image'),i=make('input');i.type='file';i.accept='image/png,image/svg+xml';i.onchange=async()=>{if(!i.files[0])return;const data=new FormData();data.set('csrf',form.elements.csrf.value);data.set('icon_file',i.files[0]);try{const r=await fetch('/admin/assets',{method:'POST',body:data,headers:{Accept:'application/json'}});if(!r.ok)throw Error();b.src=new URL((await r.json()).url,form.dataset.publicUrl).href;sync();select(b);}catch{i.setCustomValidity(t('Image upload failed.'));i.reportValidity();}};l.append(i);props.append(l);
  }else if(type==='divider'){props.append(make('p','Divider'));}
  else if(type==='spacer'){const i=field('Spacing (px)',parseInt(b.style.lineHeight,10)||24,(v,input)=>{const n=Number(v),ok=Number.isInteger(n)&&n>=4&&n<=120;input.setCustomValidity(ok?'':t('Spacing (px)'));if(ok)b.style.lineHeight=n+'px';},'number');i.min='4';i.max='120';}
  else if(type==='button'){field('Button label',b.textContent,v=>b.textContent=v);field('Link URL',b.getAttribute('href'),(v,i)=>{const ok=v==='${link}'||valid(v);i.setCustomValidity(ok?'':form.dataset.invalidUrl);if(ok)b.setAttribute('href',v);});}
  else{
   const l=make('div'),box=make('div');box.className='mail-text-edit';box.contentEditable='true';box.setAttribute('role','textbox');box.setAttribute('aria-label',t('Text'));box.innerHTML=b.innerHTML;box.oninput=()=>{b.innerHTML=box.innerHTML;sync();};
   box.onpaste=e=>{e.preventDefault();const s=window.getSelection();if(!s.rangeCount)return;const r=s.getRangeAt(0);if(!box.contains(r.commonAncestorContainer))return;r.deleteContents();const text=document.createTextNode(e.clipboardData.getData('text/plain'));r.insertNode(text);r.setStartAfter(text);r.collapse(true);s.removeAllRanges();s.addRange(r);b.innerHTML=box.innerHTML;sync();};box.ondrop=e=>e.preventDefault();box.onclick=e=>{if(e.target.closest('a'))e.preventDefault();};
   const formatting=make('div');formatting.className='editor-tools';for(const [label,command]of[['Bold','bold'],['Italic','italic'],['Underline','underline'],['Bullet list','insertUnorderedList'],['Numbered list','insertOrderedList']]){const control=button(label,()=>{box.focus();document.execCommand(command,false,null);b.innerHTML=box.innerHTML;sync();});control.onmousedown=e=>e.preventDefault();formatting.append(control);}l.append(formatting,box);props.append(l);
  }
  if(type==='button')field('Background color',b.style.backgroundColor||'#167cdb',v=>b.style.backgroundColor=v,'color');
  if(!['image','divider','spacer'].includes(type))field('Text color',b.style.color||'#222222',v=>b.style.color=v,'color');
  const l=make('label','Alignment'),align=make('select');for(const key of ['left','center','right']){const o=make('option',key);o.value=key;o.selected=key===(b.style.textAlign||'left');align.append(o);}align.onchange=()=>{b.style.textAlign=align.value;if(type==='image'||type==='button'){b.style.display=type==='image'?'block':'table';b.style.marginLeft=align.value==='left'?'0':'auto';b.style.marginRight=align.value==='right'?'0':'auto';}sync();};l.append(align);props.append(l);
 }
 function add(type,before=null){
  setView('edit');let b;if(type==='image'||type==='logo'){b=make('img');b.alt=type==='logo'?form.dataset.appName:t('Image');if(type==='logo'&&form.dataset.logo)b.src=new URL(form.dataset.logo,form.dataset.publicUrl).href;b.width=type==='logo'?200:600;b.style.maxWidth='100%';}
  else if(type==='divider')b=make('hr');else if(type==='spacer'){b=make('div');b.style.lineHeight='24px';b.append(make('br'));}
  else if(type==='button'){b=make('a','Confirm my email');b.href='${link}';b.style.cssText='background-color:#167cdb;color:white;font-size:15px;line-height:1.5;text-decoration:none;display:table;padding:10px 18px;border-radius:6px';}
  else b=make(type==='heading'?'h2':'p',type==='heading'?'Your title':'Write your message here.');canvas.insertBefore(b,before);wire();select(b);sync();
 }
 function drop(e,before){e.preventDefault();e.stopPropagation();for(const b of canvas.children)b.classList.remove('mail-drop-target');const value=e.dataTransfer.getData('text/plain');if(value.startsWith('kind:'))add(value.slice(5),before);else if(drag&&drag!==before){canvas.insertBefore(drag,before);drag=null;sync();}}
 function wire(){for(const image of canvas.querySelectorAll('img')){if(image.hasAttribute('width'))image.style.width=image.getAttribute('width')+'px';image.style.maxWidth='100%';image.style.height='auto';}for(const b of canvas.children){b.classList.add('mail-block');b.draggable=true;b.tabIndex=0;b.setAttribute('aria-label',t('Edit block')+' · '+t(({text:'Text',heading:'Heading',image:'Image',divider:'Divider',button:'Button',spacer:'Spacing'})[kind(b)]));b.onclick=e=>{e.preventDefault();select(b);};b.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();select(b);}};b.ondragstart=e=>{drag=b;e.dataTransfer.setData('text/plain','block');};b.ondragover=e=>{e.preventDefault();b.classList.add('mail-drop-target');};b.ondragleave=()=>b.classList.remove('mail-drop-target');b.ondrop=e=>drop(e,e.clientY>b.getBoundingClientRect().top+b.getBoundingClientRect().height/2?b.nextElementSibling:b);}}
 palette.append(make('h2','Add a block'));for(const [key,label,icon]of[['heading','Heading','heading'],['text','Text','align-left'],['image','Image','image'],['logo','Logo','gem'],['divider','Divider','minus'],['button','Button','arrow-pointer'],['spacer','Spacing','arrows-up-down']]){const b=button(label,()=>add(key),icon);b.draggable=true;b.ondragstart=e=>{drag=null;e.dataTransfer.setData('text/plain','kind:'+key);};palette.append(b);}palette.append(make('p','Drag blocks to reorder. Click a block to edit it.'));
 canvas.ondragover=e=>e.preventDefault();canvas.ondrop=e=>drop(e,null);
 for(const b of form.querySelectorAll('[data-mail-view]'))b.onclick=()=>{sync(false);setView(b.dataset.mailView);};
 for(const b of form.querySelectorAll('[data-mail-width]'))b.onclick=()=>stage.style.setProperty('--mail-width',b.dataset.mailWidth);
 function restore(){canvas.innerHTML=history.at(-1);wire();if(canvas.firstElementChild)select(canvas.firstElementChild);sync(false);}
 form.querySelector('[data-mail-command=undo]').onclick=()=>{if(history.length>1){future.push(history.pop());restore();}};
 form.querySelector('[data-mail-command=redo]').onclick=()=>{if(future.length){history.push(future.pop());restore();}};
 document.addEventListener('gatearr:saved',event=>{if(event.detail.form!==form||!event.detail.success)return;baseline=event.detail.data.get('html');initialSubject=event.detail.data.get('subject');sync(false);if(source.value===baseline&&form.elements.subject.value===initialSubject)document.querySelector('#mail-editor-status').textContent=document.body.dataset.saved;});
 form.elements.subject.addEventListener('input',()=>sync(false));form.addEventListener('submit',()=>sync(false));wire();sync();if(canvas.firstElementChild)select(canvas.firstElementChild);
})();
