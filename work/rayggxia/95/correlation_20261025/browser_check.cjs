const {chromium}=require('C:/Users/86134/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage();const errors=[];const checks=[];
 page.on('pageerror',e=>errors.push(String(e)));
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:1000});
  await page.goto(pathToFileURL('C:/Users/86134/Documents/a_P_BIT/远端上传/rng_correlation_20261025.html').href);
  const s=await page.evaluate(()=>({width:innerWidth,bodyWidth:document.documentElement.scrollWidth,
    images:[...document.images].every(i=>i.complete&&i.naturalWidth>0),
    peakRows:[...document.querySelectorAll('details')].at(-1).querySelectorAll('tbody tr').length,
    download:document.querySelector('a[download]').href}));
  if(s.bodyWidth>width||!s.images||s.peakRows!==504)throw new Error(JSON.stringify(s));
  await page.screenshot({path:path.resolve('work/rayggxia/95/correlation_20261025/preview-'+width+'.png')});
  checks.push(s);
 }
 const headers=await page.locator('h2').allTextContents();if(headers.length!==7)throw new Error('section count');
 if(errors.length)throw new Error(errors.join('\n'));
 fs.writeFileSync('work/rayggxia/95/correlation_20261025/BROWSER_CHECK.json',JSON.stringify({status:'PASS',checks,errors},null,2)+'\n');
 await browser.close();console.log(JSON.stringify({status:'PASS',checks}));
})().catch(e=>{console.error(e);process.exit(1)});
