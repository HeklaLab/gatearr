// This fixture publishes test blocks: run ONLY against a disposable local review copy.
const {chromium}=require('playwright'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const base=process.env.GATEARR_REVIEW_URL,session=process.env.GATEARR_REVIEW_SESSION;
 assert(base&&session,'Set GATEARR_REVIEW_URL and GATEARR_REVIEW_SESSION for a disposable review copy.');
 const target=new URL(base);assert(['localhost','127.0.0.1'].includes(target.hostname)&&target.port!=='8855','Do not run against the main demo or a production installation.');
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_BIN?{executablePath:process.env.CHROME_BIN}:{})});
 try{
  const ctx=await browser.newContext({viewport:{width:1440,height:1000}});
  await ctx.addCookies([{name:'gatearr_session',value:JSON.parse(fs.readFileSync(session)).cookie,url:base}]);
  const page=await ctx.newPage();await page.goto(base+'/admin/design/home');
  const csrf=await page.locator('#studio-csrf').inputValue();
  const upload=await ctx.request.post(base+'/admin/assets',{headers:{Origin:base,Accept:'application/json'},multipart:{csrf,icon_file:{name:'alignment.svg',mimeType:'image/svg+xml',buffer:Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40" viewBox="0 0 80 40"><rect width="80" height="40" fill="#159eff"/></svg>')}}});
  assert.equal(upload.status(),200);const url=(await upload.json()).url;
  async function aligned(view,prefix='main'){ 
   await view.locator(prefix+' [data-block-id="align-left"] img').waitFor();
   await view.waitForFunction(()=>[...document.querySelectorAll('.kind-image img')].every(img=>img.complete&&img.naturalWidth));
   const measured=await view.locator(prefix+' [data-block-id^="align-"] figure').evaluateAll(figures=>figures.map(figure=>{const f=figure.getBoundingClientRect(),i=figure.querySelector('img').getBoundingClientRect();return {id:figure.parentElement.dataset.blockId,left:Math.abs(i.left-f.left),center:Math.abs((i.left+i.right-f.left-f.right)/2),right:Math.abs(i.right-f.right),width:i.width,height:i.height,zone:figure.parentElement.getBoundingClientRect().width,container:figure.parentElement.parentElement.getBoundingClientRect().width};}));
   assert.equal(measured.length,3);
   for(const item of measured){assert(item[item.id.slice(6)]<1,JSON.stringify(item));assert(Math.abs(item.zone-item.container)<1,'An image is still constrained to its former grid columns');assert(Math.abs(item.width/item.height-2)<.01,'Image proportions changed');}
  }
  for(const kind of ['home','login','footer']){
   await page.goto(base+'/admin/design/'+kind);const boot=JSON.parse(await page.locator('#studio-data').textContent());
   const blocks=['left','center','right'].map((align,i)=>({id:'align-'+align,kind:'image',region:'main',order:900+i,span:align==='right'?4:12,...(align==='right'?{}:{image_width:80,image_unit:'px'}),url,alt:align,style:{align,padding:0}}));
   const layout={...boot.layout,blocks:[...boot.layout.blocks.filter(b=>b.kind==='login_form'),...blocks]};
   const fields={csrf,version:String(boot.version),payload:JSON.stringify(layout)};
   const preview=await ctx.request.post(base+'/admin/design/'+kind+'/preview',{headers:{Origin:base},form:fields});assert.equal(preview.status(),200);
   const pv=await ctx.newPage();await pv.goto(base+'/login');await pv.setContent(await preview.text());await aligned(pv,kind==='footer'?'footer':'main');await pv.close();
   const publish=await ctx.request.post(base+'/admin/design/'+kind+'/publish',{headers:{Origin:base},form:fields});assert.equal(publish.status(),200);
   const live=await ctx.newPage();await live.goto(base+(kind==='login'?'/login':'/home'));await aligned(live,kind==='footer'?'footer':'main');await live.close();
  }
  console.log('Image alignment verified: left/center/right, previews and published login/portal/footer; legacy third-width right alignment and image proportions preserved.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
