'use strict';
(()=>{
 let lifetime=new AbortController();
 window.GatearrPage={
  get signal(){return lifetime.signal;},
  listen(target,type,listener,options={}){target.addEventListener(type,listener,{...(typeof options==='boolean'?{capture:options}:options),signal:lifetime.signal});},
  reset(){lifetime.abort();lifetime=new AbortController();delete this.beforeLeave;}
 };
 function bind(){document.querySelectorAll('.user-tabs,.admin-tabs,.studio-pages').forEach(nav=>nav.classList.add('local-capsule'));}
 bind();document.addEventListener('gatearr:navigated',bind);
})();

// Presentation-only disclosure; existing photo endpoints and validation are retained.
document.addEventListener('click',event=>{
 const button=event.target.closest('[data-photo-toggle]');if(!button)return;
 const form=document.getElementById(button.getAttribute('aria-controls'));if(!form)return;
 form.hidden=!form.hidden;button.setAttribute('aria-expanded',String(!form.hidden));
 if(!form.hidden)form.querySelector('.upload-picker')?.focus();
});
document.addEventListener('invalid',event=>{
 for(let parent=event.target.parentElement;parent;parent=parent.parentElement)if(parent.matches('details'))parent.open=true;
},true);

// One motion clock follows the selected link while submenus expand or collapse.
(()=>{
 const observed=new Map(),slides=new Map(),flows=new Map();
 const reduced=()=>matchMedia('(prefers-reduced-motion:reduce)').matches;
 const links=menu=>[...menu.children].filter(el=>el.matches('a'));
 const target=menu=>{
  const link=links(menu).find(el=>el.getAttribute('aria-current')==='page');if(!link)return null;
  const m=menu.getBoundingClientRect(),r=link.getBoundingClientRect();
  return [r.left-m.left-menu.clientLeft,r.top-m.top-menu.clientTop,r.width,r.height];
 };
 const write=(menu,values)=>{['x','y','width','height'].forEach((name,i)=>menu.style.setProperty('--side-'+name,values[i]+'px'));menu.dataset.sideReady='true';};
 function place(menu,animate=true){
  const end=target(menu);if(!end){cancelAnimationFrame(slides.get(menu));slides.delete(menu);delete menu.dataset.sideReady;return;}
  if(slides.has(menu)&&animate)return;
  cancelAnimationFrame(slides.get(menu));slides.delete(menu);
  if(!animate||!menu.dataset.sideReady||reduced()){write(menu,end);return;}
  const start=['x','y','width','height'].map(name=>parseFloat(menu.style.getPropertyValue('--side-'+name))||0);
  if(start.every((v,i)=>Math.abs(v-end[i])<.5)&&!flows.size)return;
  const began=performance.now();
  function frame(now){
   if(!menu.isConnected){slides.delete(menu);return;}
   const next=target(menu);if(!next){delete menu.dataset.sideReady;slides.delete(menu);return;}
   const t=Math.min(1,(now-began)/220),ease=t*t*(3-2*t);
   write(menu,start.map((value,i)=>value+(next[i]-value)*ease));
   if(t<1)slides.set(menu,requestAnimationFrame(frame));else slides.delete(menu);
  }
  slides.set(menu,requestAnimationFrame(frame));
 }
 function bind(){
  for(const [menu,observer]of observed)if(!menu.isConnected){observer.disconnect();observed.delete(menu);cancelAnimationFrame(slides.get(menu));slides.delete(menu);}
  for(const menu of document.querySelectorAll('.admin-navigation,.admin-sidebar-children:not([data-side-closing])')){
   place(menu,observed.has(menu));
   if(!observed.has(menu)){let width=menu.getBoundingClientRect().width;const observer=new ResizeObserver(()=>{const next=menu.getBoundingClientRect().width;place(menu,Math.abs(next-width)<1);width=next;});observer.observe(menu);observed.set(menu,observer);}
  }
 }
 function flow(menu,opening){
  const style=getComputedStyle(menu),height=opening?0:menu.getBoundingClientRect().height;
  const marginTop=parseFloat(style.marginTop),marginBottom=parseFloat(style.marginBottom);
  flows.get(menu)?.cancel();
  if(!opening){menu.dataset.sideClosing='true';menu.inert=true;for(const link of links(menu))link.removeAttribute('aria-current');}
  if(reduced()){if(!opening)menu.remove();bind();return;}
  // scrollHeight includes the absolutely positioned selection capsule. Before
  // binding a new submenu it can inherit its parent's offset and wildly inflate
  // that measurement. The natural border box only measures the actual links.
  const full=menu.getBoundingClientRect().height;
  menu.style.overflow='hidden';
  const animation=menu.animate([
   {height:height+'px',marginTop:opening?'0px':marginTop+'px',marginBottom:opening?'0px':marginBottom+'px',opacity:opening?0:1},
   {height:opening?full+'px':'0px',marginTop:opening?marginTop+'px':'0px',marginBottom:opening?marginBottom+'px':'0px',opacity:opening?1:0}
  ],{duration:200,easing:'cubic-bezier(.4,0,.2,1)',fill:'both'});
  flows.set(menu,animation);
  animation.onfinish=()=>{flows.delete(menu);if(opening){animation.cancel();menu.style.removeProperty('overflow');}else menu.remove();bind();};
  place(menu.parentElement);
 }
 function select(url){
  const nav=document.querySelector('.admin-navigation');if(!nav)return;
  const path=url.pathname,branding=/^\/admin\/(branding|portal|footer|design|access|guides|access-guides)(\/|$)/.test(path),people=/^\/admin\/(users|groups|emby|security)(\/|$)/.test(path);
  const parent=branding?'/admin/branding':people?'/admin/users':path;
  for(const menu of [nav,...nav.querySelectorAll('.admin-sidebar-children:not([data-side-closing])')]){
   const value=menu===nav?parent:branding&&!path.startsWith('/admin/branding')?'/admin/portal':path;
   const match=links(menu).filter(a=>a.pathname===value||a.pathname!=='/admin'&&value.startsWith(a.pathname+'/')).sort((a,b)=>b.pathname.length-a.pathname.length)[0];
   for(const link of links(menu)){if(link===match)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');}place(menu);
  }
 }
 function sync(fresh){
  const old=document.querySelector('.admin-sidebar');if(!old||!fresh)return;
  const nav=old.querySelector('.admin-navigation'),next=fresh.querySelector('.admin-navigation');if(!nav||!next)return;
  const oldLinks=links(nav),oldChildren=nav.querySelector('.admin-sidebar-children:not([data-side-closing])');
  const freshChildren=next.querySelector('.admin-sidebar-children');
  const signature=menu=>menu&&links(menu).map(a=>a.pathname).join('|');
  const keepChildren=oldChildren&&signature(oldChildren)===signature(freshChildren);
  const departing=[...nav.querySelectorAll('[data-side-closing]')];
  if(oldChildren&&!keepChildren){oldChildren.dataset.sideOwner=oldChildren.previousElementSibling?.getAttribute('href')||'';departing.push(oldChildren);}
  const wanted=[];
  for(const el of [...next.children]){
   let keep=el;
   if(el.matches('a'))keep=oldLinks.find(a=>a.getAttribute('href')===el.getAttribute('href'))||el;
   else if(keepChildren&&el===freshChildren){keep=oldChildren;for(const link of links(keep)){const replacement=links(el).find(a=>a.pathname===link.pathname);if(replacement?.hasAttribute('aria-current'))link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');}}
   if(el.matches('a')){if(el.hasAttribute('aria-current'))keep.setAttribute('aria-current','page');else keep.removeAttribute('aria-current');}
   wanted.push(keep);
   if(el.matches('a'))for(const child of departing)if(child.dataset.sideOwner===el.getAttribute('href'))wanted.push(child);
  }
  for(const el of [...nav.children])if(!wanted.includes(el))el.remove();
  for(const el of wanted)nav.append(el);
  nav.setAttribute('aria-label',next.getAttribute('aria-label'));
  if(oldChildren&&!keepChildren)flow(oldChildren,false);
  if(freshChildren&&!keepChildren)flow(freshChildren,true);
  return old;
 }
 window.GatearrSidebar={select,sync};bind();document.fonts?.ready.then(bind);document.addEventListener('gatearr:navigated',bind);
})();
