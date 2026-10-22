const {chromium}=require('C:/Users/86134/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'); const path=require('path'); const {pathToFileURL}=require('url');
(async()=>{
 const root=path.resolve(__dirname,'../../..'); const out=path.join(__dirname,'visual_check');
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1100},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.goto(pathToFileURL(path.join(root,'architecture_tlm/random_service/architecture-view.html')).href);
 await page.getByRole('heading',{name:'共享32bit种子总线',exact:true}).waitFor();
 await page.screenshot({path:path.join(out,'architecture-desktop.png'),fullPage:true});
 for(const id of ['physical','readout','condition','bus','software','lfsr','gf','bivium','ffn','attention','fair']){
  await page.locator(`[data-node="${id}"]`).click();
  if(await page.locator(`[data-node="${id}"]`).getAttribute('aria-pressed')!=='true')throw Error('node selection '+id);
 }
 await page.locator('#tab-protocol').click();
 for(const kind of ['lfsr32','lfsr32_shared64','bivium'])for(const scene of ['boot','stall','reseed','replay']){
  await page.selectOption('#trace-kind',kind);await page.selectOption('#trace-scene',scene);
  await page.locator('#timeline button').last().click();
  if(!(await page.locator('#state-value').textContent()).startsWith('0x'))throw Error('trace state');
  await page.locator('#prev-cycle').click();await page.locator('#next-cycle').click();
 }
 await page.screenshot({path:path.join(out,'protocol-desktop.png'),fullPage:true});
 await page.locator('#tab-sharing').click();
 if(!(await page.locator('#instance-count').textContent()).includes('26'))throw Error('default count');
 if(!(await page.locator('#seed-volume').textContent()).includes('5,184'))throw Error('default seed bits');
 await page.selectOption('#reseed-setting','1000000');
 if(!(await page.locator('#seed-rate').textContent()).includes('518.4'))throw Error('10ms bandwidth');
 await page.locator('#candidates').fill('513');
 if(!(await page.locator('#lane-count').textContent()).includes('7路'))throw Error('padding');
 await page.selectOption('#reseed-setting','0');
 if(!(await page.locator('#seed-rate').textContent()).includes('无周期'))throw Error('startup only');
 await page.locator('#candidates').fill('0');
 if(!(await page.locator('#calc-error').isVisible()))throw Error('invalid input not rejected');
 await page.locator('#candidates').fill('512');
 await page.locator('#tab-review').click();
 await page.locator('input[value="seed-only"]').check();
 await page.locator('#review-notes').fill('核对测试，不是用户确认。');
 const downloadPromise=page.waitForEvent('download');await page.locator('#export-review').click();
 const download=await downloadPromise;await download.saveAs(path.join(out,'test-review.json'));
 const review=JSON.parse(fs.readFileSync(path.join(out,'test-review.json'),'utf8'));
 if(review.checked.join()!=='seed-only'||!review.notes.includes('不是用户确认'))throw Error('review export');
 const widths=[1440,768,390];
 for(const width of widths){await page.setViewportSize({width,height:1000});for(const tab of ['architecture','protocol','sharing','review']){
  await page.locator('#tab-'+tab).click();
  const sizes=await page.evaluate(()=>({body:document.documentElement.scrollWidth,window:innerWidth}));
  if(sizes.body>sizes.window+1)throw Error('horizontal overflow '+width+' '+tab+' '+JSON.stringify(sizes));
 }}
 await page.locator('#tab-architecture').click();await page.screenshot({path:path.join(out,'architecture-mobile.png'),fullPage:true});
 await page.emulateMedia({colorScheme:'dark'});await page.setViewportSize({width:1440,height:1100});
 await page.screenshot({path:path.join(out,'architecture-dark.png'),fullPage:true});
 await browser.close();
 const result={runtime:'Playwright / Microsoft Edge',node_selections:11,trace_cases:12,viewports:widths,
  horizontal_overflow:false,download_checked:true,console_errors:errors,ppa_run:false};
 fs.writeFileSync(path.join(__dirname,'VISUAL_CHECK.json'),JSON.stringify(result,null,2)+'\n');
 if(errors.length)throw Error(errors.join('\n'));
 console.log(JSON.stringify(result));
})().catch(e=>{console.error(e);process.exitCode=1});
