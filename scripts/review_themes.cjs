const {chromium}=require('playwright');
const fs=require('fs');
const path=require('path');
const http=require('http');
const {once}=require('events');
const checkBuilderLayout=require('./builder_layout_checks.cjs');
const widths=process.env.GATEARR_REVIEW_WIDTHS?.split(',').map(Number)||[1440,390];
const screens=process.env.GATEARR_REVIEW_SCREENS?.split(',')||['users','account','group','home','admin','themes','widgets','integrations','mail','builder','guides','translations','mail-log','bazarr','subtitle-account','subtitle-locked','subtitle-permanent'];
const dest=path.resolve(process.argv[2]||'theme-review');
const assets=path.resolve(__dirname,'../app/static');
const mime={'.html':'text/html','.css':'text/css','.js':'text/javascript','.png':'image/png','.svg':'image/svg+xml','.woff2':'font/woff2'};
(async()=>{
 const scenes=JSON.parse(fs.readFileSync(path.join(dest,'landscapes.json'),'utf8'));
 const server=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://localhost');
  if(url.pathname==='/theme-landscape.svg'){const name=scenes[url.pathname+url.search];if(!name){res.writeHead(404).end();return;}res.setHeader('Content-Type','image/svg+xml');res.end(fs.readFileSync(path.join(dest,name)));return;}
  // Only serve exported preview snapshots; no save or publish action is simulated.
  if(req.method==='POST'){
   const source=new URL(req.headers.referer||'http://localhost').pathname.match(/^\/((?:boreal|electric-lime|neon-rose)-(?:dark|light))-(builder|guides)\.html$/);
   const preview=url.pathname==='/admin/design/home/preview'?'preview':url.pathname==='/admin/visual-howto/emby/preview'?'guides-preview':null;
   req.resume();if(!source||!preview){res.writeHead(405).end();return;}
   fs.readFile(path.join(dest,source[1]+'-'+preview+'.html'),(error,data)=>{if(error){res.writeHead(404).end();return;}res.setHeader('Content-Type','text/html');res.end(data);});return;
  }
  const base=url.pathname.startsWith('/static/')?assets:dest;
  let file;try{file=path.resolve(base,decodeURIComponent(url.pathname.replace(url.pathname.startsWith('/static/')?'/static/':'/','')));}catch{res.writeHead(400).end();return;}
  if(!file.startsWith(base+path.sep)){res.writeHead(403).end();return;}
  fs.readFile(file,(error,data)=>{if(error){res.writeHead(404).end();return;}res.setHeader('Content-Type',mime[path.extname(file)]||'application/octet-stream');res.end(data);});
 });
 server.listen(0,'127.0.0.1');await once(server,'listening');
 let browser;
 try{
 browser=await chromium.launch({headless:true,...(process.env.GATEARR_CHROME_PATH?{executablePath:process.env.GATEARR_CHROME_PATH}:{})});
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));const results=[];
 for(const preset of ['boreal','electric-lime','neon-rose'])for(const mode of ['dark','light'])for(const width of widths)for(const screen of screens){
  const name=preset+'-'+mode+'-'+screen;
  await page.setViewportSize({width,height:1050});await page.goto('http://127.0.0.1:'+server.address().port+'/'+name+'.html');await page.waitForTimeout(160);if(screen==='account'){
   await page.locator('.account-menu>summary').click();
   const alternative=page.locator('.account-menu-panel .language-choice[aria-pressed=false]').first();
   if(await alternative.count()){
    await alternative.hover();await page.waitForTimeout(300);
    const stable=await page.locator('.language-choice-grid').evaluate(group=>{
     const mark=group.querySelector('.menu-slide')?.getBoundingClientRect(),selected=group.querySelector('[aria-pressed=true]')?.getBoundingClientRect();
     return mark&&selected&&Math.abs(mark.top-selected.top)<1&&Math.abs(mark.left-selected.left)<1;
    });
    if(!stable)throw Error('Language hover moved the saved-language capsule');
   }
  }
  if(screen==='bazarr')await page.locator('[data-open-connection="bazarr"]').click();
  if(['subtitle-account','subtitle-locked','subtitle-permanent'].includes(screen))await page.locator('.bazarr-subtitle-account').scrollIntoViewIfNeeded();
  if(screen==='builder'){
   const boot=JSON.parse(await page.locator('#studio-data').textContent());
   const index=boot.layout.blocks.findIndex(block=>block.kind==='applications');
   if(index>=0){await page.locator('.studio-interaction-layer').focus();for(let i=0;i<=index;i++)await page.keyboard.press('ArrowDown');await page.locator('.application-choice').first().waitFor();await page.waitForTimeout(100);}
  }
  const check=await page.evaluate(async()=>{
   const canvas=document.createElement('canvas');canvas.width=canvas.height=1;const ctx=canvas.getContext('2d',{willReadFrequently:true});
   const rgb=c=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=c;ctx.fillRect(0,0,1,1);return [...ctx.getImageData(0,0,1,1).data];};
   const blend=(top,bottom)=>top.slice(0,3).map((v,i)=>v*(top[3]/255)+bottom[i]*(1-top[3]/255));
   const lum=c=>c.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
   const ratio=(a,b)=>{const [lo,hi]=[lum(a),lum(b)].sort((a,b)=>a-b);return (hi+.05)/(lo+.05);};
   const bg=el=>{const ancestors=[];for(let p=el;p;p=p.parentElement)ancestors.unshift(p);let c=rgb(getComputedStyle(document.documentElement).getPropertyValue('--bg').trim());for(const p of ancestors)c=[...blend(rgb(getComputedStyle(p).backgroundColor),c),255];return c;};
   // Inspect the actual generated scene, not merely the body's solid fallback.
   // Use its worst luminance so the review also covers content after scrolling.
   let scene=null;
   const source=getComputedStyle(document.body,'::before').backgroundImage.match(/^url\(["']?(.*?)["']?\)$/)?.[1];
   if(source){
    const picture=new Image();picture.src=source;await picture.decode();
    const bitmap=document.createElement('canvas');bitmap.width=120;bitmap.height=110;
    const paint=bitmap.getContext('2d',{willReadFrequently:true});paint.drawImage(picture,0,0,120,110);
    const pixels=paint.getImageData(0,0,120,110).data;
    const dark=getComputedStyle(document.documentElement).colorScheme==='dark';let extreme=dark?-1:2;
    for(let i=0;i<pixels.length;i+=4){const value=lum([...pixels.slice(i,i+3)]);if(dark?value>extreme:value<extreme){extreme=value;scene=[...pixels.slice(i,i+3),255];}}
   }
   const backdrop=el=>{if(!scene)return bg(el);const ancestors=[];for(let p=el;p&&p!==document.body;p=p.parentElement)ancestors.unshift(p);let c=scene;for(const p of ancestors)c=[...blend(rgb(getComputedStyle(p).backgroundColor),c),255];return c;};
   const failures=[];const selector='h1,h2,h3,.user-name-avatar,.primary-capsule a,.local-capsule a,.admin-navigation a,button,.button,.widget-metrics strong,.widget-metrics span,.widget-quota-context,.language-policy-panel .hint,.account-menu-panel strong,.account-menu-panel legend,.language-choice,.account-menu-panel small,.connection-indicator,.studio-toolbar [role=status],.bazarr-subtitle-account p,.bazarr-subtitle-account label,.subtitle-capacity,.subtitle-row-note,.bazarr-subtitle-settings label,.bazarr-subtitle-settings h3,.studio-inspector label,.studio-inspector .check-label,.journey-card-title,.hint,.service-copy strong,.service-description,.application-metric>strong,.application-metric>span:not(.widget-quota-meter),.application-metric>small,.admin-directory-panel-heading h2,.admin-directory-panel-heading p,.admin-directory-link strong,.admin-directory-link small,.admin-directory-utility-title,.admin-directory-utilities p,.admin-directory-text-link,.admin-directory-shortcuts a,.mail-log-state,.mail-log-recipient,.mail-log-subject,.mail-log-table time,.mail-log-error';
   for(const el of document.querySelectorAll(selector)){
    const r=el.getBoundingClientRect(),s=getComputedStyle(el);if(!r.width||!r.height||s.visibility==='hidden'||el.closest('[hidden],fieldset:disabled')||el.disabled||!el.textContent.trim()||Number(s.opacity)<1)continue;
    const fg=rgb(s.color);const background=backdrop(el);const contrast=ratio(blend(fg,background),background);
    if(contrast<4.48)failures.push({tag:el.tagName,class:el.className,text:el.textContent.trim().slice(0,55),contrast:+contrast.toFixed(2),fg:s.color});
   }
   const overflow=[...document.querySelectorAll('main .card,main .structured-account,.portal-widget,.users-toolbar,.account-section,.group-language-panel,.builder-surface,.integration-overview,.admin-directory-panel,.admin-directory-utilities>.card,.mail-log-table')].filter(el=>{const r=el.getBoundingClientRect();return r.width&&r.right>document.documentElement.clientWidth+2;}).map(el=>el.className);
   const inspectorLayout=[...document.querySelectorAll('.application-choice-fields:not([hidden]) label.check')].filter(e=>e.getBoundingClientRect().width).map(e=>{
    const text=e.querySelector('.check-label')?.getBoundingClientRect(),control=e.querySelector('.gatearr-switch')?.getBoundingClientRect();
    return !text||!control||Math.abs((text.top+text.bottom-control.top-control.bottom)/2)>2||text.right>control.left+1;
   }).some(Boolean);
   const inspector=document.querySelector('.studio-inspector');
   const inspectorOverflow=!!inspector&&inspector.scrollWidth>inspector.clientWidth+2;
   return {inspectorLayout,inspectorOverflow,viewport:document.documentElement.clientWidth,pageWidth:document.documentElement.scrollWidth,overflow,failures,switches:document.querySelectorAll('.gatearr-switch').length,rawChecks:document.querySelectorAll('input[type=checkbox]:not(.gatearr-switch input)').length};
  });
  const builderIssues=await page.evaluate(checkBuilderLayout);
  results.push({preset,mode,width,screen,...check,builderIssues});
  if((width===1440&&['users','account','widgets','integrations','mail','builder','guides','translations','mail-log','admin','bazarr','subtitle-account','subtitle-locked','subtitle-permanent'].includes(screen))||(width===390&&['group','home','widgets','mail','builder','integrations','guides','admin','mail-log','bazarr','subtitle-account','subtitle-locked','subtitle-permanent'].includes(screen)))await page.screenshot({path:path.join(dest,name+'-'+width+'.png')});
 }
 fs.writeFileSync(path.join(dest,'audit.json'),JSON.stringify({errors,results},null,2));
 if(errors.length||results.some(x=>x.builderIssues.length||x.failures.length||x.pageWidth>x.viewport+2||x.overflow.length||x.rawChecks||x.inspectorLayout||x.inspectorOverflow))process.exitCode=1;
 console.log(JSON.stringify({builderIssues:results.filter(x=>x.builderIssues.length).map(x=>({preset:x.preset,mode:x.mode,width:x.width,issues:x.builderIssues}))}));
 console.log(JSON.stringify({inspectorIssues:results.filter(x=>x.inspectorLayout||x.inspectorOverflow).map(x=>[x.preset,x.mode,x.width,x.screen]),pages:results.length,scriptErrors:[...new Set(errors)],overflow:results.filter(x=>x.pageWidth>x.viewport+2||x.overflow.length).map(x=>({case:[x.preset,x.mode,x.width,x.screen].join('/'),pageWidth:x.pageWidth,viewport:x.viewport,overflow:x.overflow})),contrast:results.filter(x=>x.failures.length).map(x=>({case:[x.preset,x.mode,x.width,x.screen].join('/'),failures:x.failures})),rawChecks:results.filter(x=>x.rawChecks).map(x=>[x.preset,x.mode,x.screen,x.rawChecks])},null,2));
 }finally{await browser?.close();server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
