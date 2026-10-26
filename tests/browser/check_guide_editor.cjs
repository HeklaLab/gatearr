// Read-only interaction check on an authenticated local guide-builder review.
const {chromium}=require('playwright'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const base=process.env.GATEARR_REVIEW_URL,session=process.env.GATEARR_REVIEW_SESSION;
 assert(base&&session,'Set GATEARR_REVIEW_URL and GATEARR_REVIEW_SESSION.');
 assert(['localhost','127.0.0.1'].includes(new URL(base).hostname),'Use a local review instance.');
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_BIN?{executablePath:process.env.CHROME_BIN}:{})});
 try{
  const ctx=await browser.newContext();await ctx.addCookies([{name:'gatearr_session',value:JSON.parse(fs.readFileSync(session)).cookie,url:base}]);
  const page=await ctx.newPage();await page.goto(base+'/admin/design/home/howto/emby');
  const cards=page.locator('.journey-card');assert(await cards.count()>0,'Review requires published Emby choices.');
  for(const width of [320,390,640,900,1440]){
   await page.setViewportSize({width,height:1000});
   const card=cards.first(),id=await card.getAttribute('data-id');
   await card.click({position:{x:5,y:5}});
   assert.equal(await page.locator('.journey-card[aria-current=true]').getAttribute('data-id'),id,'Tile padding must select its settings.');
   const title=card.locator('.journey-card-title');await title.focus();await page.keyboard.press('Enter');
   assert.equal(await title.getAttribute('aria-pressed'),'true');
   assert(await title.evaluate(el=>document.activeElement===el),'Keyboard selection must retain focus.');
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  const group=cards.filter({has:page.getByRole('button',{name:'Open choices',exact:true})}).first();
  if(await group.count()){
   await group.getByRole('button',{name:'Open choices',exact:true}).click();
   assert(await page.locator('#journey-crumbs button').count()>1,'Open choices must open the submenu.');
  }
  console.log('Guide tile padding, keyboard selection, submenu action and responsive layout verified.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
