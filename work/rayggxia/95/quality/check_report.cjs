const {chromium}=require('C:/Users/86134/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs');const path=require('path');const {pathToFileURL}=require('url');
(async()=>{const root=path.resolve(__dirname,'../../../..');const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.goto(pathToFileURL(path.join(root,'architecture_tlm/random_service/quality/results/20261023/REPORT.html')).href);
for(const width of [1440,768,390]){await page.setViewportSize({width,height:1000});
if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('overflow '+width);}
if(await page.locator('img').count()!==2)throw Error('figures missing');
if(!await page.locator('img').evaluateAll(xs=>xs.every(x=>x.complete&&x.naturalWidth>0)))throw Error('figure load');
await page.locator('summary').click();if(await page.locator('details tbody tr').count()!==189)throw Error('case table');
await page.setViewportSize({width:1440,height:1100});await page.screenshot({path:path.join(__dirname,'report-preview.png'),fullPage:false});
await browser.close();if(errors.length)throw Error(errors.join('\n'));
fs.writeFileSync(path.join(__dirname,'BROWSER_CHECK.json'),JSON.stringify({viewports:[1440,768,390],figures:2,cases:189,errors},null,2)+'\n');
console.log('report browser checks passed');})();
