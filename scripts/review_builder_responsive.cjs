// Run against an isolated demo: node scripts/review_builder_responsive.cjs URL SESSION_JSON
const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
const checkLayout=require('./builder_layout_checks.cjs');
(async()=>{
 const base=process.argv[2],session=JSON.parse(fs.readFileSync(process.argv[3]));
 const browser=await chromium.launch({headless:true,...(process.env.GATEARR_CHROME_PATH?{executablePath:process.env.GATEARR_CHROME_PATH}:{})});
 try{
  const page=await browser.newPage(),errors=[],results=[];page.on('pageerror',e=>errors.push(e.message));
  await page.context().addCookies([{name:'gatearr_session',value:session.cookie,url:base}]);
  const ready=async()=>{await page.locator('#studio-palette button').first().waitFor();await page.frameLocator('#studio-preview').locator('.portal-main').waitFor();await page.waitForTimeout(250)};
  const geometry=()=>page.evaluate(()=>({columns:getComputedStyle(document.querySelector('.studio-workspace')).gridTemplateColumns,palette:getComputedStyle(document.querySelector('#studio-palette')).gridTemplateColumns,styles:[...document.querySelectorAll('head link[rel=stylesheet]')].map(e=>new URL(e.href).pathname)}));
  // Include both sides of legacy viewport breakpoints and the admin-sidebar collapse.
  for(const width of [320,390,600,601,640,700,701,760,761,780,900,1000,1100,1101,1440,1920]){
   await page.setViewportSize({width,height:1000});await page.goto(base+'/admin/portal');await ready();
   const direct=await geometry();assert.deepEqual(await page.evaluate(checkLayout),[],`Reload at ${width}`);
   await page.goto(base+'/admin');await page.evaluate(()=>window.reviewDocument=true);
   await page.locator('.admin-content a[href="/admin/portal"]').first().click();await ready();
   assert(await page.evaluate(()=>window.reviewDocument),'Navigation reloaded the document');
   assert.deepEqual(await geometry(),direct,`Navigation changed the cascade/layout at ${width}`);
   assert.deepEqual(await page.evaluate(checkLayout),[],`Navigation at ${width}`);
   results.push({width,columns:direct.columns,palette:direct.palette});
  }
  // Browser zoom reduces the CSS viewport. Use the equivalent layout widths
  // rather than CSS zoom, which leaves viewport media queries unchanged.
  for(const zoom of [1,1.25,1.5,2]){
   await page.setViewportSize({width:Math.floor(1440/zoom),height:Math.floor(1000/zoom)});await page.waitForTimeout(350);
   assert.deepEqual(await page.evaluate(checkLayout),[],`Zoom-equivalent viewport ${zoom}`);
  }
  // Exercise all preview sizes and block editing on the isolated draft only.
  for(const width of [640,1101,1440]){
   await page.setViewportSize({width,height:1000});
   for(const device of ['390px','768px','100%']){
    await page.locator(`[data-width="${device}"]`).click();await page.waitForTimeout(350);
    assert.deepEqual(await page.evaluate(checkLayout),[],`${width}/${device}`);
   }
  }
  await page.setViewportSize({width:640,height:1000});
  const count=()=>page.frameLocator('#studio-preview').locator('[data-block-id]').count();const before=await count();
  await page.locator('#studio-palette [data-kind=text]').click();await page.waitForTimeout(1600);assert.equal(await count(),before+1);
  await page.locator('[data-command=undo]').click();await page.waitForTimeout(1600);assert.equal(await count(),before);
  assert.deepEqual(await page.evaluate(checkLayout),[]);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({results,zoomEquivalentViewports:[100,125,150,200],previewSizes:true,addAndUndo:true,errors},null,2));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
