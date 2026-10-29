'use strict';
// Shared formatting controls for page content, accordion answers and guide steps.
window.GatearrFormatting={mount(box,tools,t,onchange,{basic=false}={}){
 let range;
 const remember=()=>{const s=getSelection();if(s.rangeCount&&box.contains(s.anchorNode)&&box.contains(s.focusNode))range=s.getRangeAt(0).cloneRange();};
 function apply(command,value=null){
  box.focus();if(range&&box.contains(range.commonAncestorContainer)){const s=getSelection();s.removeAllRanges();s.addRange(range);}
  if(command==='foreColor')document.execCommand('styleWithCSS',false,true);
  document.execCommand(command,false,value);
  if(command==='foreColor')document.execCommand('styleWithCSS',false,false);
  remember();onchange(box.innerHTML);
 }
 const commands=[['Bold','bold','bold'],['Italic','italic','italic'],['Underline','underline','underline'],['Bulleted list','insertUnorderedList','list-ul'],['Numbered list','insertOrderedList','list-ol'],...(!basic?[['Align left','justifyLeft','align-left'],['Align center','justifyCenter','align-center'],['Align right','justifyRight','align-right']]:[])];
 for(const[name,command,icon]of commands){
  const b=document.createElement('button'),glyph=document.createElement('i');b.type='button';b.className='secondary rich-tool-button';b.title=t(name);b.setAttribute('aria-label',t(name));glyph.className='fa-solid fa-'+icon;glyph.setAttribute('aria-hidden','true');b.append(glyph);b.onmousedown=e=>{remember();e.preventDefault();};b.onclick=()=>apply(command);tools.append(b);
 }
 const label=document.createElement('label'),glyph=document.createElement('i'),color=document.createElement('input');label.className='accordion-text-color rich-tool-color';label.title=t('Text color');glyph.className='fa-solid fa-font';glyph.setAttribute('aria-hidden','true');color.type='color';color.value='#159eff';label.style.setProperty('--format-color',color.value);color.setAttribute('aria-label',t('Text color'));color.onpointerdown=remember;color.oninput=()=>{label.style.setProperty('--format-color',color.value);apply('foreColor',color.value);};label.append(glyph,color);tools.append(label);
 box.addEventListener('keyup',remember);box.addEventListener('mouseup',remember);box.addEventListener('input',()=>{remember();onchange(box.innerHTML);});
 box.addEventListener('paste',e=>{e.preventDefault();document.execCommand('insertText',false,e.clipboardData.getData('text/plain'));});box.addEventListener('drop',e=>e.preventDefault());
}};
