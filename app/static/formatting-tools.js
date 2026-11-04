'use strict';
// Shared toolbar. Keep the selection while operating its controls.
window.GatearrFormatting={mount(box,tools,t,onchange,{basic=false}={}){
 let range;
 const remember=()=>{const s=getSelection();if(s.rangeCount&&box.contains(s.anchorNode)&&box.contains(s.focusNode))range=s.getRangeAt(0).cloneRange();};
 function restore(){if(!range||!box.contains(range.commonAncestorContainer))return false;box.focus();const s=getSelection();s.removeAllRanges();s.addRange(range);return true;}
 function apply(command,value=null){
  if(!restore())return;
  if(command==='foreColor')document.execCommand('styleWithCSS',false,true);
  document.execCommand(command,false,value);
  if(command==='foreColor')document.execCommand('styleWithCSS',false,false);
  remember();sync();onchange(box.innerHTML);
 }
 function command(name,action,icon){const b=document.createElement('button'),glyph=document.createElement('i');b.type='button';b.className='secondary rich-tool-button';b.title=t(name);b.setAttribute('aria-label',t(name));glyph.className='fa-solid fa-'+icon;glyph.setAttribute('aria-hidden','true');b.append(glyph);b.onmousedown=e=>{remember();e.preventDefault();};b.onclick=action;tools.append(b);return b;}
 for(const [name,action,icon]of [['Bold','bold','bold'],['Italic','italic','italic'],['Underline','underline','underline']])command(name,()=>apply(action),icon);
 const size=document.createElement('select');size.className='rich-text-size';size.setAttribute('aria-label',t('Font size'));
 for(const [value,label]of [['mixed',t('Mixed sizes')],['default',t('Default size')],...[12,14,16,18,20,24,32].map(n=>[String(n),n+' px'])]){const o=document.createElement('option');o.value=value;o.textContent=label;o.disabled=value==='mixed';size.append(o);}
 size.value='default';size.disabled=true;size.onpointerdown=remember;tools.append(size);
 function sync(){
  size.disabled=!range||range.collapsed||!box.contains(range.commonAncestorContainer);if(size.disabled)return;
  const values=new Set(),walker=document.createTreeWalker(box,NodeFilter.SHOW_TEXT);
  while(walker.nextNode()){const n=walker.currentNode;if(!n.textContent.trim()||!range.intersectsNode(n))continue;let p=n.parentElement,value='default';while(p&&p!==box){if(p.style.fontSize){value=p.style.fontSize==='1rem'?'default':String(parseFloat(p.style.fontSize));break;}p=p.parentElement;}values.add(value);}
  const value=values.size>1?'mixed':[...values][0]||'default';size.value=[...size.options].some(o=>o.value===value)?value:'mixed';
 }
 size.onchange=()=>{
  const value=size.value;if(value==='mixed'||!restore()||range.collapsed)return;
  const before=range.cloneRange();before.selectNodeContents(box);before.setEnd(range.startContainer,range.startOffset);const start=before.toString().length,end=start+range.toString().length;
  document.execCommand('styleWithCSS',false,false);document.execCommand('fontSize',false,'7');
  box.querySelectorAll('font[size="7"]').forEach(n=>{const span=document.createElement('span');span.style.fontSize=value==='default'?'1rem':value+'px';while(n.firstChild)span.append(n.firstChild);n.replaceWith(span);});
  const walker=document.createTreeWalker(box,NodeFilter.SHOW_TEXT),selected=document.createRange();let offset=0,started=false;
  while(walker.nextNode()){const n=walker.currentNode,length=n.textContent.length;if(!started&&start<=offset+length){selected.setStart(n,Math.max(0,start-offset));started=true;}if(started&&end<=offset+length){selected.setEnd(n,Math.max(0,end-offset));break;}offset+=length;}
  const s=getSelection();s.removeAllRanges();s.addRange(selected);remember();sync();onchange(box.innerHTML);
 };
 for(const [name,action,icon]of [['Bulleted list','insertUnorderedList','list-ul'],['Numbered list','insertOrderedList','list-ol'],...(!basic?[['Align left','justifyLeft','align-left'],['Align center','justifyCenter','align-center'],['Align right','justifyRight','align-right']]:[])])command(name,()=>apply(action),icon);
 const color=document.createElement('input');color.type='color';color.value='#159eff';color.setAttribute('aria-label',t('Choose text color'));color.onpointerdown=remember;
 const paint=command('Apply text color',()=>apply('foreColor',color.value),'font');paint.style.setProperty('--format-color',color.value);paint.classList.add('rich-apply-color');
 color.oninput=()=>{paint.style.setProperty('--format-color',color.value);apply('foreColor',color.value);};tools.append(color);
 const update=()=>{remember();sync();};box.addEventListener('keyup',update);box.addEventListener('mouseup',update);box.addEventListener('input',()=>{update();onchange(box.innerHTML);});
 const onSelection=()=>{if(!box.isConnected){document.removeEventListener('selectionchange',onSelection);return;}if(box.contains(getSelection().anchorNode))update();};document.addEventListener('selectionchange',onSelection);
 box.addEventListener('paste',e=>{e.preventDefault();document.execCommand('insertText',false,e.clipboardData.getData('text/plain'));});box.addEventListener('drop',e=>e.preventDefault());
 return {insertText(text){
  if(!restore()){box.focus();const selection=getSelection(),end=document.createRange();end.selectNodeContents(box);end.collapse(false);selection.removeAllRanges();selection.addRange(end);}
  document.execCommand('insertText',false,text);remember();sync();onchange(box.innerHTML);
 }};
}};
