// Run against an isolated demo: node scripts/review_admin_navigation.cjs URL SESSION_JSON
// SESSION_JSON contains a short-lived review cookie, never printed in results.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
(async()=>{
 const base=process.argv[2],session=JSON.parse(fs.readFileSync(process.argv[3]));
 const browser=await chromium.launch({headless:true,...(process.env.GATEARR_CHROME_PATH?{executablePath:process.env.GATEARR_CHROME_PATH}:{})});
 try{
  const page=await browser.newPage(),errors=[],results=[];page.on('pageerror',e=>errors.push(e.message));
  await page.context().addCookies([{name:'gatearr_session',value:session.cookie,url:base}]);
  for(const width of [1440,780,390]){
   await page.setViewportSize({width,height:1000});await page.goto(base+'/admin');
   await page.evaluate(()=>window.originalNav=document.querySelector('.admin-navigation'));
   // Moving from activity to appearance previously measured a 300px submenu
   // whose actual content was only 96px tall. Check EVERY animation frame.
   for(const path of ['/admin/activity','/admin/branding','/admin/users','/admin/activity','/admin/branding','/admin/emails']){
    await page.evaluate(()=>{window.samples=[];window.sampling=true;const sample=()=>{window.samples.push(document.querySelector('.admin-navigation').getBoundingClientRect().height);if(window.sampling)requestAnimationFrame(sample)};sample()});
    await page.locator('.admin-navigation>a[href="'+path+'"]').click();await page.waitForURL(base+path);await page.waitForTimeout(620);
    const motion=await page.evaluate(()=>{window.sampling=false;return {samples,retained:originalNav===document.querySelector('.admin-navigation'),closing:document.querySelectorAll('[data-side-closing]').length}});
    const max=Math.max(motion.samples[0],motion.samples.at(-1));
    assert(Math.max(...motion.samples)<=max+5,JSON.stringify({width,path,max,peak:Math.max(...motion.samples)}));
    assert(motion.retained);assert.equal(motion.closing,0);results.push({width,path,peak:Math.max(...motion.samples),final:motion.samples.at(-1)});
   }
   // A second navigation during expansion must leave no stretched/stale menu.
   await page.locator('.admin-navigation>a[href="/admin/branding"]').click();await page.waitForURL(base+'/admin/branding');
   await page.locator('.admin-navigation>a[href="/admin/users"]').click();await page.waitForURL(base+'/admin/users');await page.waitForTimeout(650);
   assert.equal(await page.locator('[data-side-closing]').count(),0);
   for(const submenu of await page.locator('.admin-sidebar-children').all())assert(await submenu.evaluate(e=>e.offsetHeight<200));
  }
  await page.emulateMedia({reducedMotion:'reduce'});await page.goto(base+'/admin');await page.locator('.admin-navigation>a[href="/admin/branding"]').click();await page.waitForURL(base+'/admin/branding');
  assert(await page.evaluate(()=>document.getAnimations().every(a=>!a.effect?.target?.matches?.('.admin-sidebar-children'))));
  await page.goto(base+'/admin');assert.equal(await page.locator('.admin-directory-utilities a[href="/admin/activity/mail"]').count(),0);
  for(const path of ['/admin/emails','/admin/emails?tab=smtp','/admin/mail-editor']){
   await page.goto(base+path);const position=await page.evaluate(()=>{const link=document.querySelector('.email-log-shortcut'),content=document.querySelector('.admin-content');return {count:document.querySelectorAll('.email-log-shortcut').length,last:link===content.lastElementChild}});
   assert.equal(position.count,1);assert(position.last,JSON.stringify({path,position}));
  }
  assert.deepEqual(errors,[]);console.log(JSON.stringify({results,rapidNavigation:true,reducedMotion:true,emailShortcutAtBottom:true,errors},null,2));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
