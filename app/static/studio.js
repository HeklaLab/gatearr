'use strict';
(() => {
 const boot=JSON.parse(document.getElementById('studio-data').textContent),copy=JSON.parse(document.getElementById('studio-copy').textContent),t=s=>copy[s]||s;
 const root=document.getElementById('page-studio'),frame=document.getElementById('studio-preview'),inspector=document.getElementById('studio-inspector'),status=document.getElementById('studio-status'),csrf=document.getElementById('studio-csrf').value;
 const headerPage=boot.page==='header',headerFunctions=['header_navigation','header_account'];let previewAudience='member';
 let state=boot.layout,version=boot.version,selected=null,history=[],future=[],timer,previewTimer,previewCount=0,drag=null,queue=Promise.resolve(),dirty=false,blocked=false;
 const applicationPanels=new Map(),accordionPreview=new Map(),accessPage=!!boot.system_key?.startsWith('guide:'),memberPage=boot.page==='home'||boot.page.startsWith('p-');
 const clone=x=>JSON.parse(JSON.stringify(x)),id=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join(''),base='/admin/design/'+boot.page+'/';
 const widgetKinds=[...(boot.widgets?.types||[])].sort((a,b)=>['widget_library','widget_tracearr'].indexOf(a)-['widget_library','widget_tracearr'].indexOf(b)).map(k=>[k,({widget_media:'Emby / Jellyfin widget',widget_seerr:'Seerr widget',widget_tracearr:'Statistics',widget_library:'Library updates'})[k],({widget_media:'film',widget_seerr:'list-check',widget_tracearr:'chart-line',widget_library:'bell'})[k]]);
 const accountKinds=(boot.account_blocks||[]).map(b=>b.kind);
 const kinds=(headerPage?[['logo','Logo','gem'],['header_navigation','Main navigation','bars'],['header_account','Account menu','circle-user'],['columns','Columns','table-columns'],['spacer','Spacing','arrows-up-down'],['text','Text','align-left'],['title','Title','heading'],['button','Button','arrow-up-right-from-square'],['page_menu','Page menu','file-lines']]:[...(boot.account_blocks||[]).map(b=>[b.kind,b.label,b.icon]),['welcome','Welcome','hand-sparkles'],['applications','Applications','grip'],['title','Title','heading'],['text','Text','align-left'],['image','Image','image'],['button','Button','arrow-up-right-from-square'],['page_menu','Page menu','bars'],['guide_embed','Access guide','route'],['accordion','Accordion','list'],['columns','Columns','table-columns'],['logo','Logo','gem'],['divider','Divider','minus'],['spacer','Spacing','arrows-up-down'],...widgetKinds]).filter(([k])=>(k!=='applications'||boot.page==='home')&&(k!=='guide_embed'||boot.page.startsWith('p-'))&&(!k.startsWith('widget_')||(memberPage&&!accessPage))&&(headerPage||memberPage||k==='page_menu'&&['footer','account'].includes(boot.page)||(!['applications','page_menu','guide_embed'].includes(k)&&!k.startsWith('widget_'))));
 function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=t(text);if(cls)e.className=cls;return e;}
 function button(text,fn,cls='secondary'){const b=el('button',text,cls);b.type='button';b.onclick=fn;return b;}
 function field(parent,label,value,onchange,type='text'){const l=el('label',label),input=el(type==='textarea'?'textarea':'input');if(type!=='textarea')input.type=type;input.value=value??'';input.addEventListener('input',()=>onchange(input.value));l.append(input);parent.append(l);return input;}
 function select(parent,label,value,options,onchange){const l=el('label',label),s=el('select');for(const [v,name]of options){const o=el('option',name);o.value=v;o.selected=String(v)===String(value);s.append(o);}s.onchange=()=>onchange(s.value);l.append(s);parent.append(l);return s;}
 function check(parent,label,value,fn){const l=el('label',undefined,'check'),i=el('input');i.type='checkbox';i.checked=!!value;i.onchange=()=>fn(i.checked);l.append(i,el('span',label,'check-label'));parent.append(l);return i;}
 function change(fn){history.push(clone(state));if(history.length>50)history.shift();future=[];fn();normalize();dirty=true;refresh();}
 function normalize(){if(headerPage){const container=state.blocks.find(b=>b.kind==='header_container');if(container)for(const b of state.blocks)if(b!==container&&!b.parent)Object.assign(b,{parent:container.id,slot:0,region:'main'});}state.blocks.forEach((b,i)=>b.order=(i+1)*10);state.blocks.filter(b=>b.kind==='applications').forEach(b=>{b.span=12;b.region='main';delete b.parent;delete b.slot;});}
 function refresh(rebuild=false){accountCompleteness();status.textContent=t('Unsaved changes');clearTimeout(timer);timer=setTimeout(()=>persist('save'),1000);clearTimeout(previewTimer);previewTimer=setTimeout(preview,220);if(rebuild)settings();root.querySelector('[data-command=undo]').disabled=!history.length;root.querySelector('[data-command=redo]').disabled=!future.length;}
 function make(kind){return {id:id(),kind,region:'main',span:12,order:10,title:headerPage&&kind==='logo'?'{app_name}':kind==='title'?'{page_title}':kind==='welcome'?'Welcome, {username}.':kind==='button'?'Open link':kind==='text'?'Your title':'',body:kind==='text'?'Write something welcoming.':'',alt:'',menu_key:'main',include_emby:true,columns:2,service_key:'emby',applications:[],...(headerPage&&kind==='logo'?{logo_mode:'logo',logo_width:180}:{}),...(kind==='page_menu'?{page_ids:[],menu_layout:'cards'}:kind==='accordion'?{items:[{id:id(),question:'Your question',answer:'Your answer'}],multiple:false}:{}),...(kind==='image'?{url:''}:kind==='button'?{url:'https://example.com'}:{}),...(kind==='text'?{rich:true}:{}),...(accountKinds.includes(kind)?{span:boot.default_layout.blocks.find(b=>b.kind===kind)?.span||12,title:kind==='account_intro'?'Hello, {name}.':boot.account_blocks.find(b=>b.kind===kind).label,body:kind==='account_intro'?'Your services at your fingertips.':''}:{}),...(kind.startsWith('widget_')?{show_logo:false,seasons:boot.widgets.tracearr,requests:boot.widgets.seerr,metrics:Object.keys(boot.widgets.metrics[kind]||{}).slice(0,2),groups:[],days:14,retention:'duration',period:'week',priority:0}:{} )};}
 function add(kind,target={}){if(headerPage&&headerFunctions.includes(kind)&&state.blocks.some(b=>b.kind===kind))return;if(accountKinds.includes(kind)&&state.blocks.some(b=>b.kind===kind))return;if(kind.startsWith('widget_')&&!boot.widgets.enabled[kind])return;if(state.blocks.length>=50){status.textContent=t('The portal supports up to 50 blocks');return;}const block=make(kind);if(headerPage&&headerFunctions.includes(kind)&&!target.parent){const preset=boot.default_layout.blocks.find(b=>b.kind===kind);if(preset&&state.blocks.some(b=>b.id===preset.parent))Object.assign(block,{parent:preset.parent,slot:preset.slot,style:clone(preset.style||{})});}change(()=>{Object.assign(block,target);state.blocks.push(block);});selected=block.id;settings();}
 for(const[k,label,icon]of kinds){const b=button(label,()=>add(k));b.draggable=true;b.dataset.kind=k;const i=boot.widgets?.icons[k]?el('img'):el('i');if(i.tagName==='IMG'){i.src=boot.widgets.icons[k];i.alt='';}else i.className='fa-solid fa-'+icon;b.prepend(i);if(k.startsWith('widget_')&&!boot.widgets.enabled[k]){b.disabled=true;b.title=t('Connection not configured');}b.ondragstart=e=>{drag={kind:k};e.dataTransfer.setData('text/plain',k);e.dataTransfer.effectAllowed='copy';};b.ondragend=()=>{drag=null;};document.getElementById('studio-palette').append(b);}

 let pointerDrag=null,skipClickUntil=0;
 function place(payload,event){if(headerPage&&headerFunctions.includes(payload.kind)&&state.blocks.some(b=>b.kind===payload.kind))return;if(payload.kind?.startsWith('widget_')&&!boot.widgets.enabled[payload.kind])return;const x=targetAt(event),moving=payload.id&&state.blocks.find(b=>b.id===payload.id),block=moving||make(payload.kind);if(!moving&&state.blocks.length>=50)return;
  const parent=x.container?.dataset.container||'',slot=Number(x.container?.dataset.slot||0);if(x.b?.dataset.blockId===block.id)return;let ancestor=parent;while(ancestor){if(ancestor===block.id)return;ancestor=state.blocks.find(b=>b.id===ancestor)?.parent||'';}
  change(()=>{state.blocks=state.blocks.filter(b=>b.id!==block.id);Object.assign(block,{parent,slot,region:x.region});const index=x.b?state.blocks.findIndex(b=>b.id===x.b.dataset.blockId):-1;if(index<0)state.blocks.push(block);else{const r=x.b.getBoundingClientRect();state.blocks.splice(index+(event.clientY>r.top+r.height/2?1:0),0,block);}});selected=block.id;settings();
 }
 function pointerStart(event,payload,inFrame=false){if(headerPage&&state.blocks.find(b=>b.id===payload.id)?.kind==='header_container')return;if(event.button!==0||event.currentTarget.disabled)return;const origin=inFrame?frame.getBoundingClientRect():{left:0,top:0};pointerDrag={payload,startX:event.clientX+origin.left,startY:event.clientY+origin.top,inFrame,active:false,ghost:null,source:event.currentTarget};pointerDrag.pointerId=event.pointerId;}
 function pointerMove(event){if(!pointerDrag)return;const origin=pointerDrag.inFrame?frame.getBoundingClientRect():{left:0,top:0},x=event.clientX+origin.left,y=event.clientY+origin.top;
  if(!pointerDrag.active&&Math.hypot(x-pointerDrag.startX,y-pointerDrag.startY)<7)return;event.preventDefault();if(!pointerDrag.active){pointerDrag.active=true;try{pointerDrag.source.setPointerCapture(pointerDrag.pointerId);}catch{}const ghost=el('div',pointerDrag.payload.kind?kinds.find(k=>k[0]===pointerDrag.payload.kind)?.[1]||'Move':'Move','studio-drag-ghost');document.body.append(ghost);pointerDrag.ghost=ghost;}
  pointerDrag.ghost.style.left=(x+12)+'px';pointerDrag.ghost.style.top=(y+12)+'px';const r=frame.getBoundingClientRect(),doc=frame.contentDocument;doc.querySelectorAll('.studio-drop').forEach(e=>e.classList.remove('studio-drop'));if(x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom){const target=doc.elementFromPoint(x-r.left,y-r.top);const block=target?.closest('[data-block-id]')||target?.closest('[data-container]');block?.classList.add('studio-drop');}
 }
 function pointerEnd(event){if(!pointerDrag)return;const current=pointerDrag;pointerDrag=null;if(!current.active)return;event.preventDefault();skipClickUntil=Date.now()+500;current.ghost?.remove();const r=frame.getBoundingClientRect(),origin=current.inFrame?r:{left:0,top:0},x=event.clientX+origin.left,y=event.clientY+origin.top;const doc=frame.contentDocument;doc.querySelectorAll('.studio-drop').forEach(e=>e.classList.remove('studio-drop'));if(x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom){const target=doc.elementFromPoint(x-r.left,y-r.top);if(target)place(current.payload,{target,clientY:y-r.top});}
 }
 root.addEventListener('click',event=>{if(Date.now()<skipClickUntil){event.preventDefault();event.stopImmediatePropagation();}},true);
 for(const b of document.querySelectorAll('#studio-palette [data-kind]')){b.draggable=false;b.style.touchAction='none';b.addEventListener('pointerdown',e=>pointerStart(e,{kind:b.dataset.kind}));b.addEventListener('pointermove',pointerMove);b.addEventListener('pointerup',pointerEnd);b.addEventListener('pointercancel',()=>{pointerDrag?.ghost?.remove();pointerDrag=null;});}
 async function request(action,payload){const data=new FormData();data.set('csrf',csrf);data.set('version',version);data.set('payload',JSON.stringify(payload));if(headerPage)data.set('audience',previewAudience);const r=await fetch(base+action,{method:'POST',body:data});if(!r.ok){if(r.status===409)blocked=true;let message=t(r.status===409?'The page changed elsewhere. Reload before continuing.':'Unable to save. Check your settings and try again.');try{const doc=new DOMParser().parseFromString(await r.text(),'text/html');message+=' '+(doc.querySelector('[data-error-message],main .lead,main p:last-child')?.textContent||'');}catch{}throw Error(message);}return r;}
 function persist(action){if(blocked)return Promise.resolve();queue=queue.catch(()=>{}).then(async()=>{status.textContent=t(action==='publish'?'Publishing…':'Saving…');const snapshot=clone(state);try{const r=await request(action,snapshot),result=await r.json();version=result.version;if(action==='restore'){state=result.layout;history=[];future=[];selected=null;settings();preview();}dirty=JSON.stringify(snapshot)!==JSON.stringify(state);status.textContent=t(action==='publish'?'Published':'Draft saved');if(action==='publish')window.dispatchEvent(new CustomEvent('gatearr:feedback',{detail:{success:true}}));if(dirty){clearTimeout(timer);timer=setTimeout(()=>persist('save'),300);}}catch(e){dirty=true;status.textContent=e.message;if(action==='publish')window.dispatchEvent(new CustomEvent('gatearr:feedback',{detail:{success:false}}));}});return queue;}
 async function preview(){const seq=++previewCount;try{const r=await request('preview',clone(state)),html=await r.text();if(seq===previewCount)frame.srcdoc=html;}catch(e){status.textContent=e.message;}}
 function targetAt(e){const d=frame.contentDocument,b=e.target.closest('[data-block-id]'),container=e.target.closest('[data-container]'),region=e.target.closest('[data-region]');return{b,container,region:region?.dataset.region||'main'};}
 frame.onload=()=>{const doc=frame.contentDocument;if(!doc)return;const style=doc.createElement('style');style.textContent='.visual-preview .portal-block{position:relative;min-height:32px;outline:1px dashed #50617a;outline-offset:4px;cursor:pointer}.visual-preview .portal-block:hover{outline:2px solid #45cdf4}.visual-preview .portal-grid{min-height:65px}.visual-preview .portal-block[data-selected]{outline:3px solid #159eff}.visual-preview .design-slot:empty:before{grid-column:1/-1;content:'+JSON.stringify(t('Drop a block here'))+';color:#a7bbd9;text-align:center;padding:20px}.visual-preview .portal-main:empty:before{grid-column:1/-1;content:'+JSON.stringify(t('Drop a block here'))+';padding:30px}.visual-preview .studio-drop{box-shadow:0 -5px 0 #45cdf4!important}.visual-preview header{pointer-events:none}';if(headerPage)style.textContent+='.visual-preview header{pointer-events:auto}';doc.head.append(style);
  for(const b of doc.querySelectorAll('[data-block-id]')){b.draggable=false;if(b.dataset.blockId===selected)b.dataset.selected='true';for(const detail of b.querySelectorAll(':scope > .page-accordion > details'))detail.open=accordionPreview.get(b.dataset.blockId)?.has(detail.dataset.accordionId)||false;}
 };
 // All editing gestures stay in the parent document. Preview links never receive a click.
 // Let the outer builder page scroll the entire preview and its side panels.
 let previewSizeObserver;
 window.GatearrPage.listen(frame,'load',()=>{
  previewSizeObserver?.disconnect();const doc=frame.contentDocument;if(!doc?.body)return;
  const sizing=doc.createElement('style');sizing.textContent='html,body{height:auto!important;min-height:0!important;overflow:hidden!important}.shell>main{min-height:0!important}';doc.head.append(sizing);
  const fit=()=>{const height=Math.max(240,Math.ceil(doc.body.scrollHeight),Math.ceil(doc.body.getBoundingClientRect().height));if(frame.style.height!==height+'px')frame.style.height=height+'px';};
  previewSizeObserver=new ResizeObserver(fit);previewSizeObserver.observe(doc.body);fit();doc.fonts?.ready.then(()=>{if(frame.contentDocument===doc)fit();});
 });
 window.GatearrPage.signal.addEventListener('abort',()=>previewSizeObserver?.disconnect(),{once:true});
 const shield=el('div',undefined,'studio-interaction-layer');shield.tabIndex=0;shield.setAttribute('aria-label',t('Live page preview'));frame.parentElement.append(shield);frame.style.pointerEvents='none';
 function hit(event){const r=frame.getBoundingClientRect(),doc=frame.contentDocument;return doc?.elementFromPoint(event.clientX-r.left,event.clientY-r.top);}
 function toggleAccordion(block,detail){
  const opening=!detail.open,container=detail.parentElement;
  if(opening&&container.dataset.multiple!=='true')for(const sibling of container.children)if(sibling.tagName==='DETAILS')sibling.open=false;
  detail.open=opening;accordionPreview.set(block.dataset.blockId,new Set(Array.from(container.children).filter(d=>d.open).map(d=>d.dataset.accordionId)));
 }
 function selectPreviewBlock(b){const changed=selected!==b.dataset.blockId;selected=b.dataset.blockId;const doc=frame.contentDocument;doc.querySelectorAll('[data-selected]').forEach(x=>delete x.dataset.selected);b.dataset.selected='true';if(changed)settings();}
 shield.addEventListener('click',e=>{e.preventDefault();if(Date.now()<skipClickUntil)return;const target=hit(e),b=target?.closest('[data-block-id]');if(!b){selected=null;frame.contentDocument?.querySelectorAll('[data-selected]').forEach(x=>delete x.dataset.selected);settings();return;}selectPreviewBlock(b);const summary=target.closest('.page-accordion summary');if(summary)toggleAccordion(b,summary.parentElement);});
 shield.addEventListener('pointerdown',e=>{const target=hit(e),b=target?.closest('[data-block-id]');if(b)pointerStart(e,{id:b.dataset.blockId});});
 shield.addEventListener('pointermove',pointerMove);shield.addEventListener('pointerup',pointerEnd);shield.addEventListener('pointercancel',()=>{pointerDrag?.ghost?.remove();pointerDrag=null;});
 shield.addEventListener('keydown',e=>{if(!['ArrowDown','ArrowUp','Enter',' '].includes(e.key))return;e.preventDefault();if(['Enter',' '].includes(e.key)){const block=frame.contentDocument?.querySelector('[data-block-id="'+selected+'"]'),detail=block?.querySelector(':scope > .page-accordion > details');if(detail){toggleAccordion(block,detail);return;}}const blocks=state.blocks;if(!blocks.length)return;let i=blocks.findIndex(b=>b.id===selected);i=e.key==='ArrowUp'?Math.max(0,i-1):e.key==='ArrowDown'?Math.min(blocks.length-1,i+1):Math.max(0,i);selected=blocks[i].id;settings();frame.contentDocument?.querySelector('[data-block-id="'+selected+'"]')?.scrollIntoView({block:'nearest'});});
 function rich(parent,label,html,onchange,basic=false){
  const l=el('div',undefined,'studio-rich-field'),caption=el('span',label),tools=el('div',undefined,'editor-tools'),box=el('div',undefined,'studio-rich');l.append(caption);box.contentEditable='true';box.setAttribute('role','textbox');box.setAttribute('aria-label',t(label));box.innerHTML=html||'';window.GatearrFormatting.mount(box,tools,t,onchange,{basic});
  l.append(tools,box);parent.append(l);
 }
 function colors(parent,style,onchange){
  const panel=el('div',undefined,'studio-color-panel');
  function swatch(parent,key,label){
   const row=el('label',undefined,'studio-color-row'),caption=el('span',label),control=el('span',undefined,'studio-color-control'),input=el('input'),hex=el('code');
   input.type='color';input.value=style[key]||boot.palette[key]||'#0b101b';input.setAttribute('aria-label',t(label));hex.textContent=input.value.toUpperCase();
   input.addEventListener('input',()=>{hex.textContent=input.value.toUpperCase();onchange(key,input.value);});
   control.append(input,hex);row.append(caption,control);parent.append(row);
  }
  for(const[title,fields]of [['Buttons',[['accent','Accent'],['button_hover','Button hover'],['ink','Button text']]],['Background',[['bg','Background'],['surface','Block surface'],['text','Text'],['muted','Secondary text']]]]){
   const group=el('fieldset',undefined,'studio-color-group');group.append(el('legend',title));for(const[key,label]of fields)swatch(group,key,label);panel.append(group);
  }
  const gradient=el('details',undefined,'studio-gradient');gradient.open=!!style.gradient;gradient.append(el('summary','Gradient'));const options=el('div',undefined,'studio-gradient-options');
  check(gradient,'Gradient',style.gradient,v=>{options.hidden=!v;onchange('gradient',v);});options.hidden=!style.gradient;
  swatch(options,'gradient_start','Gradient start');swatch(options,'gradient_end','Gradient end');field(options,'Gradient angle',style.angle??135,v=>onchange('angle',Math.min(360,Math.max(0,Number(v)))),'number');
  gradient.append(options);panel.append(gradient);parent.append(panel);
 }
 async function upload(file,done){const data=new FormData();data.set('csrf',csrf);data.set('icon_file',file);status.textContent=t('Uploading…');try{const r=await fetch('/admin/assets',{method:'POST',body:data,headers:{Accept:'application/json'}});if(!r.ok)throw Error();done((await r.json()).url);}catch{status.textContent=t('Image upload failed. Choose a valid PNG or SVG, up to 5 MB.');}}
 function imageUpload(parent,done,current=''){const l=el('label','Upload image'),i=el('input');i.type='file';i.accept='image/png,image/svg+xml,image/jpeg,image/webp';i.dataset.logoEditor='image';if(current)i.dataset.uploadPreview=current;i.onchange=()=>{if(i.files[0])upload(i.files[0],done);};l.append(i);parent.append(l);}
 let pageIcons;
 function pageIcon(parent,p){
  const wrap=el('div',undefined,'page-icon-picker'),toggle=button('Choose an icon',async()=>{panel.hidden=!panel.hidden;if(panel.hidden)return;try{pageIcons||=await fetch('/static/fontawesome-icons.json').then(r=>r.json());draw();search.focus();}catch{panel.textContent=t('Unable to load icons. Try again.');}}),panel=el('div'),search=el('input'),grid=el('div',undefined,'page-icon-grid');
  const glyph=el('i');glyph.className=p.icon?.includes(':')?'fa-'+p.icon.replace(':',' fa-'):'fa-solid fa-'+(p.icon||'file-lines');toggle.prepend(glyph);search.type='search';search.placeholder=t('Search icons');search.setAttribute('aria-label',t('Search icons'));panel.hidden=true;
  function draw(){grid.replaceChildren();for(const item of pageIcons.filter(x=>(x.label+' '+x.id+' '+x.search).toLowerCase().includes(search.value.toLowerCase())).slice(0,72)){const b=button('',()=>{change(()=>{p.icon=item.id;p.icon_url='';});settings();}),i=el('i');i.className=item.id.includes(':')?'fa-'+item.id.replace(':',' fa-'):'fa-solid fa-'+item.id;b.title=item.label;b.setAttribute('aria-label',item.label);b.append(i);grid.append(b);}}
  search.oninput=draw;panel.append(search,grid);wrap.append(toggle,panel);parent.append(wrap);
 }
 function pageSettings(){
  state.page_settings||={title:'Home',slug:'home',description:'',icon:'house',icon_url:'',navigation:false,audience:{everyone:true,admins:true,groups:[]}};
  const p=state.page_settings;inspector.append(el('h2','Page settings'));
  if(boot.page==='home'){const title=field(inspector,'Page title','Home',()=>{});title.disabled=true;inspector.append(el('p','The Home page cannot be renamed or deleted.','hint'));}else field(inspector,'Page title',p.title,v=>change(()=>p.title=v));
  if(boot.page!=='home'&&!boot.system_key?.startsWith('guide:'))field(inspector,'Page address',p.slug,v=>change(()=>p.slug=v));
  field(inspector,'Description',p.description,v=>change(()=>p.description=v),'textarea');
  imageUpload(inspector,v=>{change(()=>p.icon_url=v);settings();},p.icon_url||'');
  pageIcon(inspector,p);
  check(inspector,'Show in page navigation',p.navigation,v=>change(()=>p.navigation=v));
  if(boot.page!=='home')audienceControls(inspector,p);
 }
 function audienceControls(parent,b){
  const groups=boot.groups||[],a=b.audience||{everyone:(b.visibility||'everyone')==='everyone'&&!(b.groups||[]).length,admins:b.visibility==='admins',groups:b.groups||[]};
  const section=el('fieldset',undefined,'block-audience');section.append(el('legend','Visible to'));parent.append(section);
  const chips=el('div',undefined,'audience-chips');section.append(chips);
  for(const[key,label]of [['everyone','Everyone'],['admins','Administrators'],...groups.map(g=>[g.id,g.name])]){const active=a.everyone|| (key==='admins'?a.admins:key==='everyone'?a.everyone:a.groups.includes(key));const control=button(label,()=>{change(()=>{b.audience=window.GatearrAudience.toggle(a,key,!active,groups);delete b.visibility;delete b.groups;});settings();},'secondary');control.setAttribute('aria-pressed',String(!!active));chips.append(control);}
  const test=el('details',undefined,'audience-test');test.append(el('summary','Test visibility'));for(const u of [{label:'Administrator',admin:true,group:null},{label:'User without a group',admin:false,group:null},...groups.map(g=>({label:g.name,admin:false,group:g.id}))]){const row=el('p'),icon=el('i');icon.className='fa-solid fa-'+(window.GatearrAudience.matches(a,u)?'eye':'eye-slash');icon.setAttribute('aria-hidden','true');row.append(icon,document.createTextNode(' '+t(u.label)+' · '+t(window.GatearrAudience.matches(a,u)?'Visible':'Hidden')));test.append(row);}const demo=el('a','Test visibility');demo.href='/admin/audience-demo';demo.target='_blank';demo.rel='noopener';test.append(demo);section.append(test);
 }
 function headerCompleteness(){
  if(!headerPage)return;
  const notice=document.getElementById('header-completeness'),present=new Set(state.blocks.map(b=>b.kind)),missing=(boot.header_blocks||[]).filter(b=>!present.has(b.kind));
  notice.replaceChildren();notice.hidden=!missing.length;
  if(missing.length){notice.append(el('strong','Some header features are unavailable'),el('p','These system blocks have been removed. Add them again to restore their controls in the header.'));for(const entry of missing){const line=el('p',undefined,'hint');line.textContent=t(entry.label)+' — '+t(entry.impact);notice.append(line);}const list=el('div',undefined,'studio-buttons');for(const entry of missing){const action=button('',()=>add(entry.kind));action.textContent=t(entry.label)+' +';list.append(action);}notice.append(list);}
 }
 function accountCompleteness(){
  headerCompleteness();
  if(boot.page!=='account')return;
  const notice=document.getElementById('account-completeness'),present=new Set(state.blocks.filter(b=>b.region!=='login').map(b=>b.kind)),missing=boot.account_blocks.filter(b=>b.required&&!present.has(b.kind));
  notice.replaceChildren();notice.hidden=!missing.length;
  if(missing.length){notice.append(el('strong','Some account features are unavailable'),el('p','Add the missing blocks so members can manage these settings from My account.'));const list=el('div',undefined,'studio-buttons');for(const entry of missing){const action=button('',()=>add(entry.kind));action.textContent=t(entry.label)+' +';list.append(action);}notice.append(list);}
  for(const control of document.querySelectorAll('#studio-palette [data-kind]'))if(accountKinds.includes(control.dataset.kind)){control.disabled=present.has(control.dataset.kind);control.setAttribute('aria-disabled',String(control.disabled));}
 }
 if(headerPage){root.querySelector('[data-command=header-container]')?.addEventListener('click',()=>{selected=state.blocks.find(b=>b.kind==='header_container')?.id;settings();const block=frame.contentDocument?.querySelector('[data-block-id="'+selected+'"]');if(block)selectPreviewBlock(block);});root.querySelector('[data-header-audience]')?.addEventListener('change',e=>{previewAudience=e.target.value;preview();});root.querySelector('[data-command=header-default]')?.addEventListener('click',()=>{change(()=>{state=clone(boot.default_layout);selected=null;});settings();});}
 root.querySelector('[data-command=account-default]')?.addEventListener('click',()=>{change(()=>{state=clone(boot.default_layout);selected=null;});settings();});
 function settings(){accountCompleteness();if(headerPage)for(const k of headerFunctions){const p=root.querySelector('[data-kind="'+k+'"]');if(p){p.disabled=state.blocks.some(b=>b.kind===k);p.title=t('Move the existing block in the preview.');}}inspector.replaceChildren();const b=state.blocks.find(x=>x.id===selected);if(!b){if(memberPage)pageSettings();inspector.append(el('h2','Page colors and layout'));if(headerPage){field(inspector,'Browser tab title',state.browser_title||'',v=>change(()=>state.browser_title=v));inspector.append(el('p','Leave blank for the default title. Use ${app_name} to include the application name.','hint'));}if(!headerPage)check(inspector,'Show header',state.show_header!==false,v=>change(()=>state.show_header=v));if(!headerPage)select(inspector,'Navigation position',state.nav_position,[['top','Top'],['left','Left'],['right','Right']],v=>change(()=>state.nav_position=v));colors(inspector,state.colors||{},(k,v)=>change(()=>{state.colors||={};state.colors[k]=v;if(k==='gradient'&&v){state.colors.gradient_start||=boot.palette.gradient_start;state.colors.gradient_end||=boot.palette.gradient_end;}}));return;}
 inspector.append(el('h2',b.kind==='header_container'?'Header':kinds.find(x=>x[0]===b.kind)?.[1]||(b.kind==='account_form'?'My account':'Sign-in form')));
 const actions=el('div',undefined,'studio-buttons'),fixed=b.kind==='header_container',forms=['login_form','forgot_form','reset_form'];
 const descendants=()=>{const all=new Set([b.id]);for(let i=0;i<4;i++)state.blocks.forEach(x=>{if(all.has(x.parent))all.add(x.id);});return all;};
 if(!fixed){const move=delta=>change(()=>{let i=state.blocks.indexOf(b),j=i+delta;if(j>=0&&j<state.blocks.length&&state.blocks[j].kind!=='header_container')[state.blocks[i],state.blocks[j]]=[state.blocks[j],state.blocks[i]];});actions.append(button('Move up ↑',()=>move(-1)),button('Move down ↓',()=>move(1)));}
 if(!fixed&&!forms.includes(b.kind)){
  if(!accountKinds.includes(b.kind)&&!state.blocks.some(x=>descendants().has(x.id)&&headerFunctions.includes(x.kind)))actions.append(button('Duplicate',()=>{change(()=>{const all=descendants(),copies=state.blocks.filter(x=>all.has(x.id)).map(clone);if(state.blocks.length+copies.length>50)return;const ids=Object.fromEntries(copies.map(x=>[x.id,id()]));for(const c of copies){c.id=ids[c.id];if(ids[c.parent])c.parent=ids[c.parent];}state.blocks.push(...copies);selected=ids[b.id];});settings();}));
  actions.append(button('Delete',()=>{change(()=>{const removed=descendants();if(state.blocks.some(x=>removed.has(x.id)&&forms.includes(x.kind))){status.textContent=t('Keep the sign-in form on this page');return;}state.blocks=state.blocks.filter(x=>!removed.has(x.id));selected=null;});settings();},'danger'));
 }
 inspector.append(actions);
 if(headerPage&&b.kind==='logo'){select(inspector,'Display',b.logo_mode||'logo',[['logo','Logo only'],['name','Name only'],['both','Logo and name']],v=>{change(()=>b.logo_mode=v);settings();});const width=field(inspector,'Logo width (px)',b.logo_width||180,v=>change(()=>b.logo_width=Math.max(24,Math.min(600,Math.round(Number(v)||180)))),'number');width.min='24';width.max='600';inspector.append(el('p','Upload your light and dark logos in Identity.','hint'));const link=el('a','Logo and identity');link.href='/admin/branding';inspector.append(link);}
 if(b.kind==='spacer'){const input=field(inspector,'Size (px)',b.size??32,v=>change(()=>b.size=Math.max(0,Math.min(2000,Math.round(Number(v)||0)))),'number');input.min='0';input.max='2000';}else if(!headerFunctions.includes(b.kind)&&b.kind!=='header_container'){const title=field(inspector,headerPage&&b.kind==='logo'?'Text':'Title',b.title,v=>change(()=>b.title=v));if(headerPage&&b.kind==='logo'){const vars=el('div',undefined,'title-variables');vars.append(button('Insert application name',()=>{const start=title.selectionStart??title.value.length,end=title.selectionEnd??start;change(()=>b.title=title.value.slice(0,start)+'{app_name}'+title.value.slice(end));settings();}),el('p','Use {app_name} to display the application name from Identity.','hint'));inspector.append(vars);}if(b.kind==='title'){const variables=el('div',undefined,'title-variables');variables.append(button('Insert page title',()=>{const start=title.selectionStart??title.value.length,end=title.selectionEnd??start;change(()=>b.title=title.value.slice(0,start)+'{page_title}'+title.value.slice(end));settings();},'secondary'),el('p','Use {page_title} to display the current page title.','hint'));inspector.append(variables);}}if(['text','welcome','forgot_form','reset_form','account_intro'].includes(b.kind)){if(b.kind==='text')rich(inspector,'Text',b.body,v=>change(()=>{b.rich=true;b.body=v;}));else field(inspector,'Text',b.body,v=>change(()=>b.body=v),'textarea');}
 if(!['applications','image','header_container'].includes(b.kind))select(inspector,'Width',b.span,headerPage?Array.from({length:12},(_,i)=>[i+1,String(i+1)+' / 12']):[[12,'Full width'],[6,'Half'],[4,'Third']],v=>change(()=>b.span=Number(v)));
 if(!headerPage&&b.kind!=='applications')select(inspector,'Placement',b.region,[['header','Above the content'],['main','Main content'],['sidebar','Sidebar'],['footer','Bottom of page']],v=>change(()=>{b.region=v;delete b.parent;}));
 if(memberPage||boot.page==='footer'||boot.page==='account')audienceControls(inspector,b);
 if(b.kind==='columns'){
  select(inspector,'Number of columns',b.columns||2,[[1,'1'],[2,'2'],[3,'3']],v=>{change(()=>{b.columns=Number(v);if(headerPage)b.column_sizes=Array.from({length:b.columns},()=>1);state.blocks.filter(x=>x.parent===b.id&&x.slot>=b.columns).forEach(x=>x.slot=b.columns-1);});settings();});
  if(headerPage)for(let i=0;i<(b.columns||2);i++){const width=field(inspector,t('Column')+' '+(i+1)+' · '+t('Width'),b.column_sizes?.[i]||1,v=>change(()=>{b.column_sizes||=Array.from({length:b.columns||2},()=>1);b.column_sizes[i]=Math.max(1,Math.min(12,Math.round(Number(v)||1)));}),'number');width.min='1';width.max='12';}
 }
 if(b.kind.startsWith('widget_')){
 if(!boot.widgets.types.includes(b.kind))inspector.append(el('p','Enable the required integration in Applications & API.','hint'));
 check(inspector,'Show application logo',b.show_logo,v=>change(()=>b.show_logo=v));
 for(const [key,label]of Object.entries(boot.widgets.metrics[b.kind]||{}))check(inspector,label,(b.metrics||[]).includes(key),v=>change(()=>b.metrics=v?[...(b.metrics||[]),key]:(b.metrics||[]).filter(x=>x!==key)));
 if(b.kind==='widget_media'){select(inspector,'Count display',b.count_mode||'exact',[['exact','Exact counts'],['promotion','Promotion']],v=>{change(()=>b.count_mode=v);settings();});if(b.count_mode==='promotion')select(inspector,'Round down to',String(b.round_to||100),[['10','Nearest lower ten'],['100','Nearest lower hundred']],v=>change(()=>b.round_to=Number(v)));}
 if(b.kind==='widget_tracearr')select(inspector,'Period',b.period||'week',[['week','This week'],['month','This month'],['30days','Last 30 days']],v=>change(()=>b.period=v));
 if(b.kind==='widget_library'){if(boot.widgets.seerr)check(inspector,'Available requests',b.requests!==false,v=>change(()=>b.requests=v));if(boot.widgets.tracearr)check(inspector,'New seasons',b.seasons!==false,v=>change(()=>b.seasons=v));select(inspector,'Keep announcements',b.retention||'duration',boot.widgets.tracearr?[['duration','For a duration'],['watched','Until watched']]:[['duration','For a duration']],v=>{change(()=>b.retention=v);settings();});if(b.retention!=='watched')field(inspector,'Days',b.days||14,v=>change(()=>b.days=Math.max(1,Math.min(365,Number(v)))),'number');}
 field(inspector,'Priority',b.priority||0,v=>change(()=>b.priority=Math.max(0,Math.min(100,Number(v)))),'number');inspector.append(el('p','One widget of each type is shown per user. Targeted groups take priority over roles and general audiences.','hint'));
 }
 if(b.kind==='image'){
  const widthFields=el('div',undefined,'image-width-fields');inspector.append(widthFields);
  const unit=b.image_unit||'%',amount=b.image_width??100;
  const width=field(widthFields,'Width',amount,value=>{const n=Number(value);if(Number.isFinite(n)&&n>=1)change(()=>{b.span=12;b.image_width=Math.min(unit==='%'?100:4096,n);b.image_unit=unit;});},'number');width.min='1';width.max=unit==='%'?'100':'4096';width.step='any';
  const units=select(widthFields,'',unit,[['px','px'],['%','%']],next=>{const section=frame.contentDocument?.querySelector('[data-block-id="'+CSS.escape(b.id)+'"]'),image=section?.querySelector('.portal-image'),pixels=image?.getBoundingClientRect().width;
   change(()=>{b.span=12;b.image_unit=next;b.image_width=Math.max(1,Math.min(next==='%'?100:4096,pixels?(next==='px'?Math.round(pixels):Math.round(pixels/(section.clientWidth-parseFloat(frame.contentWindow.getComputedStyle(section).paddingLeft)-parseFloat(frame.contentWindow.getComputedStyle(section).paddingRight))*10000)/100):amount));});settings();});units.setAttribute('aria-label',t('Width')+' (px / %)');
  imageUpload(inspector,url=>{change(()=>b.url=url);settings();},b.url);field(inspector,'Image description',b.alt,v=>change(()=>b.alt=v));
 }
 if(b.kind==='button'){
  if(accessPage)select(inspector,'Button action',b.button_action||'link',[['link','Open link'],['choose_device','Choose another device']],v=>{change(()=>{b.button_action=v;if(v==='choose_device'){b.title='Choose another device';b.new_tab=false;b.after_device=true;}else if(!b.url)b.url='https://example.com';});settings();});
  if(b.button_action==='choose_device'){inspector.append(el('p','Returns to the device choices for this page.','hint'));check(inspector,'Show only after selecting a device',b.after_device!==false,v=>change(()=>b.after_device=v));}
  else{field(inspector,'URL',b.url,v=>change(()=>b.url=v),'url');check(inspector,'New tab',b.new_tab,v=>change(()=>b.new_tab=v));}
 }
 if(b.kind==='applications'){
 select(inspector,'Number of applications',b.columns||3,[1,2,3,4,5,6].map(n=>[n,String(n)]),v=>{change(()=>{b.columns=Number(v);b.applications=(b.applications||[]).slice(0,b.columns);});settings();});
 const chosen=b.applications||[],list=el('div',undefined,'application-selection');let dragged=null;
 inspector.append(el('p',undefined,'application-count'));inspector.lastChild.textContent=t('Applications')+': '+chosen.length+' / '+(b.columns||3);
 const expanded=applicationPanels.has(b.id)?applicationPanels.get(b.id):chosen[0];
 for(const app of [...boot.services].filter(app=>app.key!=='tracearr'||(b.audience?!b.audience.everyone&&b.audience.admins&&!b.audience.groups?.length:b.visibility==='admins')).sort((a,c)=>(chosen.includes(a.key)?chosen.indexOf(a.key):999)-(chosen.includes(c.key)?chosen.indexOf(c.key):999))){
  const enabled=chosen.includes(app.key),name=app.key==='account'?t('My account'):app.name,row=el('div',undefined,'application-choice'),header=el('div',undefined,'application-choice-header');row.append(header);
  row.ondragover=e=>{if(dragged)e.preventDefault();};row.ondrop=e=>{e.preventDefault();if(!dragged||dragged===app.key||!chosen.includes(app.key))return;change(()=>{b.applications=chosen.filter(k=>k!==dragged);b.applications.splice(b.applications.indexOf(app.key),0,dragged);});settings();};
  const checkbox=check(header,'',enabled,on=>{if(on&&chosen.length>=(b.columns||3)){settings();return;}change(()=>{b.applications=on?[...chosen,app.key]:chosen.filter(k=>k!==app.key);if(on&&app.default_mode){b.application_behaviors||={};b.application_behaviors[app.key]||={mode:app.default_mode};}});applicationPanels.set(b.id,on?app.key:null);settings();});checkbox.setAttribute('aria-label',name);checkbox.disabled=!enabled&&chosen.length>=(b.columns||3);
  if(!enabled){header.append(el('span',name,'application-choice-name'));list.append(row);continue;}
  const fields=el('div',undefined,'application-choice-fields'),summary=el('p',undefined,'application-choice-summary');fields.id='application-fields-'+b.id+'-'+chosen.indexOf(app.key);fields.hidden=expanded!==app.key;summary.hidden=!fields.hidden;
  const title=button(name,()=>{const opening=fields.hidden;for(const panel of list.querySelectorAll('.application-choice-fields'))panel.hidden=true;for(const toggle of list.querySelectorAll('[aria-expanded]'))toggle.setAttribute('aria-expanded','false');for(const caption of list.querySelectorAll('.application-choice-summary'))caption.hidden=false;fields.hidden=!opening;summary.hidden=opening;title.setAttribute('aria-expanded',String(opening));applicationPanels.set(b.id,opening?app.key:null);},'application-choice-toggle');title.setAttribute('aria-expanded',String(!fields.hidden));title.setAttribute('aria-controls',fields.id);const caret=el('i');caret.className='fa-solid fa-chevron-down';caret.setAttribute('aria-hidden','true');title.append(caret);header.append(title);
  const controls=el('div',undefined,'application-order');for(const delta of [-1,1]){const move=button(delta<0?'↑':'↓',()=>{const i=chosen.indexOf(app.key),j=i+delta;if(j<0||j>=chosen.length)return;change(()=>{const next=[...chosen];[next[i],next[j]]=[next[j],next[i]];b.applications=next;});settings();});move.disabled=chosen.indexOf(app.key)+delta<0||chosen.indexOf(app.key)+delta>=chosen.length;move.setAttribute('aria-label',t(delta<0?'Move up ↑':'Move down ↓')+' · '+name);controls.append(move);}header.append(controls);
  title.draggable=true;title.ondragstart=e=>{dragged=app.key;e.dataTransfer.setData('text/plain',app.key);};title.ondragend=()=>dragged=null;
  const subtitle=()=>b.subtitles?.[app.key]??({'access:emby':'Access medias','access:seerr':'Request new movies & series','account':'Manage my account'}[app.key]||'Open application');
  const behavior=()=>{const value=b.application_behaviors?.[app.key]||{mode:app.default_mode};return app.opening_modes&&!app.opening_modes.includes(value.mode)?{...value,mode:app.default_mode}:value;};
  const modeNames={direct:'Direct link',embedded:'Open inside Gatearr',guide:'Access guide'};
  const caption=()=>summary.textContent=(app.opening_modes?t(modeNames[behavior().mode])+' · ':'')+subtitle();caption();
  field(fields,'Subtitle',subtitle(),v=>{change(()=>{b.subtitles||={};b.subtitles[app.key]=v;});caption();});
  if(['access:emby','access:seerr'].includes(app.key)){
   const info=()=>{b.information||={};return b.information[app.key]||=clone(state.application_information_defaults?.[app.key]||{enabled:true});},current=b.information?.[app.key]||state.application_information_defaults?.[app.key]||{},kind=app.key==='access:emby'?'widget_media':app.key==='tracearr'?'widget_tracearr':'widget_seerr';
   const information=el('div',undefined,'application-information-settings');fields.append(information);
   check(information,'Show information in application card',current.enabled!==false,v=>{change(()=>info().enabled=v);settings();});
   if(current.enabled!==false){
    const defaults=current.metrics||current.rules?.[0]?.metrics||({widget_media:['movies','series'],widget_seerr:['movies_left','series_left'],widget_tracearr:['watch_time','favorite']}[kind]);
    const metrics=el('div',undefined,'application-metrics-settings');information.append(metrics);
    for(const [metric,label]of Object.entries(boot.widgets.metrics[kind]))check(metrics,label,defaults.includes(metric),v=>{change(()=>{const active=info().metrics||defaults;info().metrics=v?[...active,metric]:active.filter(x=>x!==metric);});settings();});
    if(kind==='widget_tracearr')select(information,'Period',current.period||'week',[['week','This week'],['month','This month'],['30days','Last 30 days']],v=>{change(()=>info().period=v);settings();});
    if(kind==='widget_media'){
     const mode=current.count_mode||current.rules?.[0]?.count_mode||'exact';
     select(fields,'Count display',mode,[['exact','Exact counts'],['promotion','Promotion']],v=>{change(()=>info().count_mode=v);settings();});
     if(mode==='promotion')select(fields,'Round down to',String(current.round_to||current.rules?.[0]?.round_to||100),[['10','Nearest lower ten'],['100','Nearest lower hundred']],v=>change(()=>info().round_to=Number(v)));
    }
   }
  }
  if(app.opening_modes){
   const setBehavior=values=>{b.application_behaviors||={};b.application_behaviors[app.key]={...behavior(),...values};};
   const modes=app.opening_modes.map(mode=>[mode,modeNames[mode]]);
   // Keep unavailable integration-based access visible without making it selectable.
   if(app.integration_configured===false)modes.push(['embedded',modeNames.embedded]);
   const modeSelect=select(fields,'When clicked',behavior().mode,modes,mode=>{change(()=>setBehavior({mode}));caption();settings();});
   if(app.integration_configured===false){
    const option=[...modeSelect.options].find(item=>item.value==='embedded');
    option.disabled=true;option.dataset.description=t('Not configured in Applications & API');
    const hint=el('p','Not configured in Applications & API','hint');
    fields.append(hint);
   }
   if(behavior().mode==='direct'){
    const url=field(fields,'Public interface URL',behavior().url||app.direct_url||'',value=>change(()=>setBehavior({url:value})),'url');url.placeholder='https://application.example.com';
    if(!behavior().url&&!app.direct_url)fields.append(el('p','Public interface address required','hint'));
    check(fields,'New tab',behavior().new_tab??app.external,value=>change(()=>setBehavior({new_tab:value})));
   }
  }
  if(app.howto){const a=el('a','Edit Access guides','application-guide-link');a.href='/admin/design/home/howto/'+app.howto;fields.append(a);
  }else if(!app.howto&&app.key.startsWith('menu:')){fields.append(button('Create Access guides',async()=>{clearTimeout(timer);await persist('save');if(dirty||blocked)return;try{const data=new FormData();data.set('csrf',csrf);const r=await fetch('/admin/design/home/enable-howto/'+app.key.split(':')[1],{method:'POST',body:data});if(!r.ok)throw Error(t('Unable to create Access guides'));window.location.assign((await r.json()).url);}catch(e){status.textContent=e.message;}}));}
  row.append(summary,fields);list.append(row);
 }inspector.append(list,el('p','Applications are visible only to users with permission to access them.','hint'));const manage=el('a','Manage applications');manage.href='/admin/integrations';inspector.append(manage);
 }
 if(b.kind==='page_menu'){
  select(inspector,'Layout',b.menu_layout||'cards',[['cards','Cards'],['tiles','Tiles'],['list','List'],['pills','Compact menu']],v=>change(()=>b.menu_layout=v));
  inspector.append(el('p','Pages without permission are automatically hidden.','hint'));
  select(inspector,'Pages to show',b.menu_source||'selected',[['selected','Selected pages'],['navigation','Pages in navigation']],v=>{change(()=>b.menu_source=v);settings();});
  if(boot.page!=='home')check(inspector,'Show Back button',b.show_back===true,v=>change(()=>b.show_back=v));
  if(b.menu_source!=='navigation')for(const p of boot.pages||[])check(inspector,p.title,(b.page_ids||[]).includes(p.key),v=>change(()=>{b.page_ids=v?[...(b.page_ids||[]),p.key]:(b.page_ids||[]).filter(k=>k!==p.key);}));
 }
 if(b.kind==='guide_embed'){
  select(inspector,'Application',b.service_key||'emby',boot.services.filter(s=>s.howto).map(s=>[s.howto,s.name]),v=>change(()=>b.service_key=v));
  const link=el('a','Configure devices and guides');link.href='/admin/design/home/howto/'+b.service_key;inspector.append(link);inspector.append(el('p','Publish guides and their journey separately. This block displays their published content.','hint'));
 }
 if(b.kind==='accordion'){
  check(inspector,'Allow several items to stay open',b.multiple,v=>change(()=>b.multiple=v));
  for(const item of b.items||[]){
   const row=el('fieldset',undefined,'accordion-editor');field(row,'Question',item.question,v=>change(()=>item.question=v));
   const visual=el('details',undefined,'accordion-visual-settings');visual.append(el('summary','Icon or logo (optional)'));
   imageUpload(visual,v=>{change(()=>{item.icon_url=v;item.icon='';});settings();},item.icon_url||'');pageIcon(visual,item);
   if(item.icon||item.icon_url)visual.append(button('Remove icon',()=>{change(()=>{item.icon='';item.icon_url='';item.watermark=false;});settings();}));
   const background=check(visual,'Show icon in background',item.watermark,v=>change(()=>item.watermark=v));background.disabled=!item.icon&&!item.icon_url;row.append(visual);
   const answer=item.rich?item.answer:el('div',item.answer||'').innerHTML.replace(/\n/g,'<br>');
   rich(row,'Answer',answer,v=>change(()=>{item.rich=true;item.answer=v;}),true);
   const i=b.items.indexOf(item);row.append(button('Move up ↑',()=>{if(i>0){change(()=>[b.items[i-1],b.items[i]]=[b.items[i],b.items[i-1]]);settings();}}),button('Move down ↓',()=>{if(i<b.items.length-1){change(()=>[b.items[i+1],b.items[i]]=[b.items[i],b.items[i+1]]);settings();}}),button('Delete',()=>{change(()=>b.items=b.items.filter(x=>x!==item));settings();},'danger'));inspector.append(row);
  }
  if((b.items||[]).length<30)inspector.append(button('Add a question',()=>{change(()=>{b.items||=[];b.items.push({id:id(),question:'Your question',answer:'Your answer'});});settings();}));
 }

 select(inspector,'Alignment',b.style?.align||'left',[['left','Left'],['center','Center'],['right','Right']],v=>change(()=>{b.style||={};b.style.align=v;}));
 if(b.kind==='text'){
  const appearance=el('fieldset',undefined,'text-appearance');appearance.append(el('legend','Background and border'));inspector.append(appearance);
  const set=(key,value)=>change(()=>{b.style||={};b.style[key]=value;});
  select(appearance,'Background',b.style?.background_mode||'default',[['default','Page default'],['transparent','Transparent'],['color','Color'],['gradient','Gradient'],['picture','Picture']],v=>{set('background_mode',v);settings();});
  if(b.style?.background_mode==='color')field(appearance,'Background color',b.style?.bg||'#0b101b',v=>set('bg',v),'color');
  if(b.style?.background_mode==='gradient'){field(appearance,'Gradient start',b.style?.gradient_start||'#0b101b',v=>set('gradient_start',v),'color');field(appearance,'Gradient end',b.style?.gradient_end||'#159eff',v=>set('gradient_end',v),'color');field(appearance,'Gradient angle',b.style?.angle??135,v=>set('angle',Math.max(0,Math.min(360,Number(v)))),'number');}
  if(b.style?.background_mode==='picture')imageUpload(appearance,url=>{set('background_image',url);settings();},b.style?.background_image||'');
  select(appearance,'Border',b.style?.border_mode||'default',[['default','Page default'],['none','Transparent'],['color','Color']],v=>{set('border_mode',v);settings();});
  if(b.style?.border_mode==='color'){field(appearance,'Border color',b.style?.border_color||'#526789',v=>set('border_color',v),'color');const w=field(appearance,'Border width (px)',b.style?.border_width??1,v=>set('border_width',Math.max(0,Math.min(12,Number(v)))),'number');w.min=0;w.max=12;}
 }
 const details=el('details'),summary=el('summary','Colors and appearance');details.append(summary);colors(details,b.style||{},(k,v)=>change(()=>{b.style||={};b.style[k]=v;if(k==='gradient'&&v){b.style.gradient_start||=boot.palette.gradient_start;b.style.gradient_end||=boot.palette.gradient_end;}}));field(details,'Padding',b.style?.padding??0,v=>change(()=>{b.style||={};b.style.padding=Number(v);}), 'number');field(details,'Rounded corners',b.style?.radius??0,v=>change(()=>{b.style||={};b.style.radius=Number(v);}), 'number');details.append(button('Use page colors',()=>{change(()=>delete b.style);settings();}));inspector.append(details);
 }
 document.querySelector('.studio-canvas').addEventListener('click',e=>{if(e.target.closest('#studio-frame-wrap'))return;selected=null;frame.contentDocument?.querySelectorAll('[data-selected]').forEach(x=>delete x.dataset.selected);settings();});
 root.querySelectorAll('[data-command]').forEach(b=>b.onclick=()=>{const c=b.dataset.command;if(c==='undo'&&history.length){future.push(clone(state));state=history.pop();dirty=true;refresh();settings();}else if(c==='redo'&&future.length){history.push(clone(state));state=future.pop();dirty=true;refresh();settings();}else if(c==='page-settings'){selected=null;settings();}else if(c==='publish'){clearTimeout(timer);persist('publish');}else if(c==='restore'&&confirm(t('Replace this draft with the published page?'))){clearTimeout(timer);persist('restore');}});
 root.querySelectorAll('[data-width]').forEach(b=>b.onclick=()=>{document.getElementById('studio-frame-wrap').style.width=b.dataset.width;root.querySelectorAll('[data-width]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));});
 const preset=document.getElementById('studio-preset');
 if(preset&&boot.page==='home')preset.onchange=e=>{const kind=e.target.value;if(!kind)return;if(!confirm(t('Replace this draft with the selected template?'))){e.target.value='';return;}change(()=>{state.blocks=clone(boot.home_preset.blocks);if(kind==='simple')state.blocks.shift();if(kind==='banner')state.blocks[0].style={align:'center',padding:32};selected=null;});settings();e.target.value='';};
 window.GatearrPage.beforeLeave=async()=>{if(dirty)await persist('save');return !dirty;};
 window.GatearrPage.signal.addEventListener('abort',()=>{clearTimeout(timer);clearTimeout(previewTimer);},{once:true});
 window.GatearrPage.listen(window,'beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});settings();preview();
})();
