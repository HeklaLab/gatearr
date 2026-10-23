/* A shared, progressively enhanced select. The native control remains the form source. */
'use strict';
(() => {
 const widgets = new Map();
 let opened = null, serial = 0, typed = '', typedAt = 0;
 const make = (tag, cls, text) => { const node = document.createElement(tag); node.className = cls; if (text) node.textContent = text; return node; };
 const languages = {'en':'🇬🇧','fr':'🇫🇷','de':'🇩🇪','es':'🇪🇸','it':'🇮🇹','pt':'🇵🇹','pt-br':'🇧🇷','nl':'🇳🇱','pl':'🇵🇱','ru':'🇷🇺','uk':'🇺🇦','cs':'🇨🇿','sv':'🇸🇪','da':'🇩🇰','nb':'🇳🇴','fi':'🇫🇮','tr':'🇹🇷','ar':'🌐','he':'🌐','ja':'🇯🇵','ko':'🇰🇷','zh-cn':'🇨🇳','el':'🇬🇷','ro':'🇷🇴','hu':'🇭🇺','bg':'🇧🇬','sk':'🇸🇰','hr':'🇭🇷','id':'🇮🇩','vi':'🇻🇳','th':'🇹🇭','hi':'🇮🇳','is':'🇮🇸'};
 const languageField = select => /^(locale|language|edit_locale|default_locale|mail_locale)$/.test(select.name) || select.dataset.guidedKind === 'language';
 const unavailable = option => option.disabled || option.hidden || option.parentElement.disabled;
 function close(focus = false) {
  if (!opened) return;
  const item = opened; opened = null;
  item.button.setAttribute('aria-expanded','false'); item.button.removeAttribute('aria-activedescendant'); item.menu.remove();
  if (focus && item.button.isConnected) item.button.focus({preventScroll:true});
 }
 function label(select) {
  if (select.getAttribute('aria-label')) return select.getAttribute('aria-label');
  const labels = [...(select.labels || [])].map(el => {const copy = el.cloneNode(true); copy.querySelectorAll('select,button,.guided-select-trigger').forEach(n => n.remove()); return copy.textContent.trim();}).filter(Boolean);
  return labels.join(' ') || select.name || select.id;
 }
 function update(item) {
  const {select,button,value} = item;
  button.disabled = select.matches(':disabled');
  button.hidden = select.hidden || !!select.closest('[hidden]');
  button.setAttribute('aria-label', label(select));
  button.setAttribute('aria-required', String(select.required));
  const options = [...select.selectedOptions];
  value.textContent = options.map(o => o.label).join(', ') || '—';
  const option = options[0];
  item.mark.textContent = languageField(select) && option ? languages[option.value.toLowerCase()] || '🌐' : '';
  item.mark.hidden = !item.mark.textContent;
 }
 function position(item) {
  const rect = item.button.getBoundingClientRect();
  const viewport = window.visualViewport;
  const width = viewport?.width || innerWidth, height = viewport?.height || innerHeight;
  const leftEdge = viewport?.offsetLeft || 0, topEdge = viewport?.offsetTop || 0;
  const below = height + topEdge - rect.bottom - 12, above = rect.top - topEdge - 12;
  const up = below < 200 && above > below;
  const maxHeight = Math.max(40, Math.min(340, up ? above : below));
  item.menu.style.width = Math.min(Math.max(rect.width, 200),width - 16) + 'px';
  item.menu.style.maxHeight = maxHeight + 'px';
  item.menu.style.left = Math.max(leftEdge+8, Math.min(rect.left,leftEdge+width-item.menu.offsetWidth-8)) + 'px';
  item.menu.style.top = (up ? Math.max(topEdge+8,rect.top-item.menu.offsetHeight-6) : rect.bottom+6) + 'px';
 }
 function highlight(item,index) {
  const choices = item.choices;
  if (!choices.length) return;
  item.active = Math.max(0,Math.min(index,choices.length-1));
  choices.forEach((choice,n) => choice.node.classList.toggle('is-active',n===item.active));
  const node = choices[item.active].node;
  item.button.setAttribute('aria-activedescendant',node.id);
  node.scrollIntoView({block:'nearest'});
 }
 function choose(item,index) {
  const choice = item.choices[index]; if (!choice) return;
  const select = item.select;
  if (select.multiple) choice.option.selected = !choice.option.selected;
  else select.selectedIndex = choice.option.index;
  // Keep all existing change handlers, autosave and builder behavior intact.
  select.dispatchEvent(new Event('input',{bubbles:true}));
  select.dispatchEvent(new Event('change',{bubbles:true}));
  update(item);
  if (select.multiple && select.isConnected) open(item); else close(true);
 }
 function open(item) {
  close(); update(item);
  if (item.button.disabled || item.button.hidden) return;
  const menu = make('div','guided-select-menu'); menu.id = item.id; menu.setAttribute('role','listbox'); menu.setAttribute('aria-label',label(item.select));
  menu.dir = getComputedStyle(item.select).direction;
  if (item.select.multiple) menu.setAttribute('aria-multiselectable','true');
  item.menu = menu; item.choices = []; opened = item;
  let previousGroup;
  for (const option of item.select.options) {
   if (option.hidden) continue;
   const group = option.parentElement.tagName==='OPTGROUP' ? option.parentElement.label : '';
   if (group && group !== previousGroup) { menu.append(make('div','guided-select-group',group)); previousGroup = group; }
   const node = make('div','guided-select-option'); node.id = item.id+'-'+option.index; node.setAttribute('role','option'); node.setAttribute('aria-selected',String(option.selected));
   const disabled = unavailable(option); node.setAttribute('aria-disabled',String(!!disabled));
   const mark = make('span','guided-select-icon'); mark.setAttribute('aria-hidden','true');
   if (languageField(item.select)) mark.textContent = languages[option.value.toLowerCase()] || '🌐';
   else {const glyph = make('i','fa-solid fa-'+(option.dataset.icon || item.select.dataset.guidedIcon || 'sliders')); mark.append(glyph);}
   const copy = make('span','guided-select-copy'); copy.append(make('span','guided-select-title',option.label));
   // Descriptions must come from translated application copy, never guessed from values.
   const description = option.dataset.description || (languageField(item.select) ? option.value.toUpperCase() : '');
   if (description) copy.append(make('small','guided-select-description',description));
   const check = make('i','fa-solid fa-check guided-select-check'); check.setAttribute('aria-hidden','true');
   node.append(mark,copy,check); menu.append(node);
   if (!disabled) { const index = item.choices.length; item.choices.push({option,node}); node.addEventListener('pointermove',()=>highlight(item,index)); node.addEventListener('mousedown',e=>e.preventDefault()); node.addEventListener('click',e=>{e.preventDefault();choose(item,index);}); }
  }
  (item.select.closest('dialog[open]') || document.body).append(menu); item.button.setAttribute('aria-expanded','true'); position(item);
  highlight(item, Math.max(0,item.choices.findIndex(choice=>choice.option.selected)));
 }
 function enhance(select) {
  if (widgets.has(select)) return;
  const button = make('button','guided-select-trigger'); button.type = 'button'; button.setAttribute('role','combobox'); button.setAttribute('aria-haspopup','listbox'); button.setAttribute('aria-expanded','false');
  const mark = make('span','guided-select-value-icon'); mark.setAttribute('aria-hidden','true');
  const value = make('span','guided-select-value'); const arrow = make('i','fa-solid fa-chevron-down guided-select-chevron'); arrow.setAttribute('aria-hidden','true'); button.append(mark,value,arrow);
  const item = {select,button,value,mark,id:'guided-select-'+(++serial),active:0,choices:[]};
  button.setAttribute('aria-controls',item.id);
  select.insertAdjacentElement('afterend',button); widgets.set(select,item);
  select.classList.add('guided-select-source'); select.tabIndex = -1; select.setAttribute('aria-hidden','true');
  update(item);
  button.addEventListener('click',e=>{e.preventDefault();opened===item?close():open(item)});
  button.addEventListener('keydown',e=>{
   if (e.key==='Tab') {close();return;}
   if (e.key==='Escape') {if(opened===item){e.preventDefault();e.stopPropagation();close(true);}return;}
   if (['ArrowDown','ArrowUp','Home','End','Enter',' '].includes(e.key)) {
    e.preventDefault();
    if (opened!==item) {open(item);if(e.key==='End')highlight(item,item.choices.length-1);return;}
    if(e.key==='Enter'||e.key===' '){choose(item,item.active);return;}
    highlight(item,e.key==='Home'?0:e.key==='End'?item.choices.length-1:item.active+(e.key==='ArrowUp'?-1:1)); return;
   }
   if(e.key.length===1&&!e.ctrlKey&&!e.metaKey&&!e.altKey){
    e.preventDefault(); if(opened!==item)open(item);
    const now=Date.now();typed=now-typedAt>800?e.key:typed+e.key;typedAt=now;
    const found=item.choices.findIndex(c=>c.option.label.toLocaleLowerCase().startsWith(typed.toLocaleLowerCase()));if(found>=0)highlight(item,found);
   }
  });
  select.addEventListener('change',()=>update(item));
  select.addEventListener('focus',()=>button.focus());
  select.addEventListener('invalid',e=>{e.preventDefault();button.setAttribute('aria-invalid','true');button.focus();open(item)});
  select.addEventListener('change',()=>button.removeAttribute('aria-invalid'));
 }
 function scan() {
  for(const [select,item] of widgets) {
   if(!select.isConnected){if(opened===item)close();item.button.remove();widgets.delete(select);}
   else if(select.nextElementSibling!==item.button)select.insertAdjacentElement('afterend',item.button);
   else update(item);
  }
  document.querySelectorAll('select').forEach(enhance);
 }
 let scheduled=false;
 const observer=new MutationObserver(records=>{
  if(records.every(r=>r.target.closest?.('.guided-select-trigger,.guided-select-menu')))return;
  if(!scheduled){scheduled=true;queueMicrotask(()=>{scheduled=false;scan()})}
 });
 observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['disabled','hidden','selected','label','value','required']});
 document.addEventListener('pointerdown',e=>{if(opened&&!opened.menu.contains(e.target)&&!opened.button.contains(e.target))close()});
 document.addEventListener('reset',()=>setTimeout(scan,0));
 document.addEventListener('close',e=>{if(opened&&e.target.contains(opened.menu))close()},true);
 document.addEventListener('gatearr:navigated',()=>{close();scan()});
 document.addEventListener('gatearr:headerupdated',()=>{close();scan()});
 document.addEventListener('submit',()=>close(),true);
 document.addEventListener('scroll',e=>{if(opened&&!opened.menu.contains(e.target))close()},true);
 window.addEventListener('resize',()=>close());
 scan();
})();
