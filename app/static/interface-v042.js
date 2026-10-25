'use strict';
(() => {
 // Retain native checkboxes, names, validation and change handlers. Only the
 // visual wrapper changes, including controls created inside the builders.
 function switches(root=document) {
  const inputs=[...(root.matches?.('input[type=checkbox]')?[root]:[]),...root.querySelectorAll('input[type=checkbox]')];
  for(const input of inputs) {
   if(input.closest('.gatearr-switch')||input.hidden)continue;
   const wrapper=document.createElement('span');wrapper.className='gatearr-switch';
   const track=document.createElement('span');track.className='gatearr-switch-track';track.setAttribute('aria-hidden','true');
   input.before(wrapper);wrapper.append(input,track);input.setAttribute('role','switch');
  }
 }
 switches();
 new MutationObserver(changes=>{for(const change of changes)for(const node of change.addedNodes)if(node.nodeType===1)switches(node);}).observe(document.body,{childList:true,subtree:true});

 // The account menu uses a single sliding language selection; layout dimensions
 // stay fixed when the active language changes.
 const menus=new WeakSet();
 function bindMenus(){
  for(const group of document.querySelectorAll('.language-choice-grid')){
   if(menus.has(group))continue;menus.add(group);
   const mark=document.createElement('span');mark.className='menu-slide';mark.setAttribute('aria-hidden','true');group.prepend(mark);
   const place=(button,animate=true)=>{
    if(!button)return;
    if(!animate)group.classList.remove('menu-animate');
    mark.style.transform=`translate(${button.offsetLeft}px,${button.offsetTop}px)`;
    mark.style.width=button.offsetWidth+'px';mark.style.height=button.offsetHeight+'px';
    group.classList.add('menu-ready');requestAnimationFrame(()=>group.classList.add('menu-animate'));
   };
   const selected=()=>group.querySelector('[aria-pressed=true]');
   new ResizeObserver(()=>place(selected(),false)).observe(group);
   // The capsule identifies the saved language, not the item under the pointer.
   // Hover has its own quiet fill; keyboard focus retains its visible outline.
   new MutationObserver(()=>place(selected())).observe(group,{subtree:true,attributes:true,attributeFilter:['aria-pressed']});
   group.closest('details')?.addEventListener('toggle',()=>place(selected(),false));
   place(selected(),false);
  }
 }
 bindMenus();document.addEventListener('gatearr:headerupdated',bindMenus);document.addEventListener('gatearr:navigated',bindMenus);
})();
