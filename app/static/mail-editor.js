/* Small local editor built on Selection/Range; no external runtime or deprecated editing API. */
'use strict';
(() => {
  const form=document.querySelector('#mail-editor-form');
  if(!form)return;
  const editor=document.querySelector('#rich-editor'), source=form.elements.html;
  editor.innerHTML=source.value; // Server-sanitized HTML only.
  editor.hidden=false;
  document.querySelector('#html-fallback').hidden=true;
  document.querySelectorAll('.editor-toolbar,.editor-insert').forEach(node=>node.hidden=false);
  let savedRange=null;
  function remember(){const s=window.getSelection();if(s.rangeCount && editor.contains(s.anchorNode) && editor.contains(s.focusNode))savedRange=s.getRangeAt(0).cloneRange();}
  document.addEventListener('selectionchange',remember);
  function range(){editor.focus();const valid=savedRange && editor.contains(savedRange.commonAncestorContainer);const r=valid?savedRange.cloneRange():document.createRange();if(!valid){r.selectNodeContents(editor);r.collapse(false);}return r;}
  function insert(node){const r=range();r.deleteContents();r.insertNode(node);r.setStartAfter(node);r.collapse(true);const s=window.getSelection();s.removeAllRanges();s.addRange(r);savedRange=r.cloneRange();source.value=editor.innerHTML;}
  function format(command){
    const r=range();
    if(['left','center','right'].includes(command)){
      let node=r.startContainer.nodeType===Node.ELEMENT_NODE?r.startContainer:r.startContainer.parentElement;
      while(node.parentElement!==editor && node!==editor)node=node.parentElement;
      if(node===editor){const p=document.createElement('p');p.append(r.extractContents());p.style.textAlign=command;insert(p);}else node.style.textAlign=command;
    }else{
      const tags={bold:'strong',italic:'em',underline:'u',h2:'h2',p:'p',ul:'ul',ol:'ol'};
      const node=document.createElement(tags[command]);
      if(command==='ul'||command==='ol'){const li=document.createElement('li');li.append(r.extractContents());if(!li.textContent)li.append(document.createElement('br'));node.append(li);}else{node.append(r.extractContents());if(!node.textContent)node.append(document.createElement('br'));}
      r.insertNode(node);const s=window.getSelection();r.selectNodeContents(node);s.removeAllRanges();s.addRange(r);savedRange=r.cloneRange();
    }
    source.value=editor.innerHTML;
  }
  document.querySelectorAll('[data-command]').forEach(button=>{button.addEventListener('mousedown',e=>e.preventDefault());button.addEventListener('click',()=>format(button.dataset.command));});
  document.querySelector('#editor-color').addEventListener('input',e=>{const r=range(),node=document.createElement('span');node.style.color=e.target.value;node.append(r.extractContents());r.insertNode(node);savedRange=null;source.value=editor.innerHTML;});
  function url(value){try{const parsed=new URL(value);return ['https:','http:'].includes(parsed.protocol)&&!parsed.username&&!parsed.password?parsed.href:null;}catch{return null;}}
  document.querySelector('[data-insert="image"]').addEventListener('click',()=>{const input=document.querySelector('#image-url'),src=url(input.value);input.setCustomValidity(src?'':form.dataset.invalidUrl);if(!input.reportValidity())return;const img=document.createElement('img');img.src=src;img.alt=document.querySelector('#image-alt').value;img.style.maxWidth='100%';insert(img);});
  document.querySelector('[data-insert="link"]').addEventListener('click',()=>{const input=document.querySelector('#link-url'),href=input.value==='${link}'?'${link}':url(input.value);input.setCustomValidity(href?'':form.dataset.invalidUrl);if(!input.reportValidity())return;const a=document.createElement('a');a.setAttribute('href',href);a.textContent=document.querySelector('#link-text').value||href;insert(a);});
  // Paste and drop cannot introduce active HTML into the administration page.
  editor.addEventListener('paste',e=>{e.preventDefault();insert(document.createTextNode(e.clipboardData.getData('text/plain')));});
  editor.addEventListener('drop',e=>e.preventDefault());
  editor.addEventListener('click',e=>{if(e.target.closest('a'))e.preventDefault();});
  editor.addEventListener('input',()=>{source.value=editor.innerHTML;remember();});
  form.addEventListener('submit',()=>{source.value=editor.innerHTML;});
})();
