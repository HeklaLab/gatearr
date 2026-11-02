// Deterministic, isolated regression check for every consumer of the shared toolbar.
const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_BIN?{executablePath:process.env.CHROME_BIN}:{})});
 try{
  const page=await browser.newPage();
  for(const basic of [false,true]){
   await page.setContent('<div class="editor-tools" id="tools"></div><div id="editor" contenteditable="true"><p>Alpha <b>Beta</b> Gamma</p></div>');
   for(const file of ['color-controls.js','guided-select.js','formatting-tools.js'])await page.addScriptTag({content:fs.readFileSync(path.join(__dirname,'../../app/static',file),'utf8')});
   await page.evaluate(basic=>{window.changed=[];GatearrFormatting.mount(document.getElementById('editor'),document.getElementById('tools'),s=>s,html=>changed.push(html),{basic});},basic);
   async function select(part){await page.evaluate(part=>{const box=document.getElementById('editor'),r=document.createRange();if(part==='all')r.selectNodeContents(box);else if(part==='bold')r.selectNodeContents(box.querySelector('b'));else{const walker=document.createTreeWalker(box,NodeFilter.SHOW_TEXT);let n;while(walker.nextNode())if(walker.currentNode.textContent.includes(part)){n=walker.currentNode;break;}const start=n.textContent.indexOf(part);r.setStart(n,start);r.setEnd(n,start+part.length);}getSelection().removeAllRanges();getSelection().addRange(r);box.dispatchEvent(new MouseEvent('mouseup'));},part);}
   await select('bold');await page.getByRole('combobox',{name:'Font size',exact:true}).click();await page.getByRole('option',{name:'24 px',exact:true}).click();
   assert((await page.locator('#editor b').innerHTML()).includes('24px'));
   await select('all');assert.equal(await page.locator('.rich-text-size').inputValue(),'mixed');
   await select('bold');await page.getByRole('combobox',{name:'Font size',exact:true}).click();await page.getByRole('option',{name:'Default size',exact:true}).click();assert((await page.locator('#editor b').innerHTML()).includes('1rem'));
   await select('Alpha');await page.getByRole('button',{name:'Apply text color',exact:true}).click();
   await select('Gamma');await page.getByRole('button',{name:'Apply text color',exact:true}).click();
   const content=await page.locator('#editor').innerHTML();assert.equal((content.match(/color: rgb\(21, 158, 255\)/g)||[]).length,2);assert(content.includes('<b>'));
   await page.locator('.gatearr-color-hex').fill('#CC3377');assert.equal(await page.locator('input[type=color]').inputValue(),'#cc3377');
   await select('Beta');await page.getByRole('button',{name:'Apply text color',exact:true}).click();assert((await page.locator('#editor b').innerHTML()).includes('204, 51, 119'));
   await page.evaluate(()=>{const box=document.getElementById('editor'),r=document.createRange();r.selectNodeContents(box);r.collapse(false);getSelection().removeAllRanges();getSelection().addRange(r);box.dispatchEvent(new MouseEvent('mouseup'));});
   assert(await page.getByRole('combobox',{name:'Font size',exact:true}).isDisabled());
   assert((await page.evaluate(()=>changed)).length>=5);
   console.log('PASS shared toolbar '+(basic?'accordion':'text / guide / email')+': size, mixed selection, default, repeated colour, HEX, selection scope');
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
