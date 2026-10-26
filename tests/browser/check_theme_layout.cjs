// Read-only browser regression: run against an authenticated local review instance.
// GATEARR_REVIEW_URL=http://localhost:8870 GATEARR_REVIEW_SESSION=/path/session.json node tests/browser/check_theme_layout.cjs
const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.GATEARR_REVIEW_URL;
 const session=process.env.GATEARR_REVIEW_SESSION;
 assert(base&&session,'Set GATEARR_REVIEW_URL and GATEARR_REVIEW_SESSION for a local review instance.');
 assert(['localhost','127.0.0.1'].includes(new URL(base).hostname),'Use an isolated local review instance.');
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_BIN?{executablePath:process.env.CHROME_BIN}:{})});
 try{
  const context=await browser.newContext();
  await context.addCookies([{name:'gatearr_session',value:JSON.parse(fs.readFileSync(session)).cookie,url:base}]);
  const page=await context.newPage();
  for(const width of [320,390,640,900,1440]){
   await page.setViewportSize({width,height:1000});
   await page.goto(base+'/admin/branding/themes');
   assert.equal(await page.locator('.color-grid').count(),2,'Authenticated theme editor required');
   const grids=await page.locator('.color-grid').evaluateAll(elements=>elements.map(grid=>{
    const columns=getComputedStyle(grid).gridTemplateColumns.split(' ').length;
    return [...grid.querySelectorAll('input[type=color]')].map((input,i)=>({row:Math.floor(i/columns),top:input.getBoundingClientRect().top}));
   }));
   for(const cells of grids)for(const cell of cells)assert(Math.abs(cell.top-cells.find(other=>other.row===cell.row).top)<1,`Color controls misaligned at ${width}px`);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Page overflow at ${width}px`);
   for(const form of await page.locator('.palette-editor').all()){
    const gap=await form.evaluate(el=>el.querySelector('label.check').getBoundingClientRect().top-el.querySelector('.color-grid').getBoundingClientRect().bottom);
    assert(gap>=20,`Palette gradient switch touches the color controls at ${width}px`);
   }
  }
  const guest=await browser.newContext();
  const login=await guest.newPage();await login.goto(base+'/login');
  const menu=login.locator('.guest-language-menu');
  if(await menu.count()){
   await menu.locator('summary').click();
   assert.equal(await menu.locator('form.account-menu-language').evaluate(e=>getComputedStyle(e).borderBottomWidth),'0px');
  }
  console.log('Theme controls aligned at five widths; guest menu has no trailing divider.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
