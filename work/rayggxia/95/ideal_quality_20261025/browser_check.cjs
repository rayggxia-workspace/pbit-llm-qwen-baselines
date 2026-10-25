const { chromium } = require('C:/Users/86134/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  const page = await browser.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  const checks=[];
  for (const width of [1280,390]) {
    await page.setViewportSize({width,height:900});
    await page.goto(pathToFileURL(path.resolve('architecture_tlm/random_service/quality/results/ideal_20261025/REPORT.html')).href);
    const s=await page.evaluate(()=>({width:innerWidth,bodyWidth:document.documentElement.scrollWidth,
      images:[...document.images].every(i=>i.complete&&i.naturalWidth>0),
      cases:document.querySelectorAll('details tbody tr').length,title:document.title}));
    if (s.bodyWidth>width || !s.images || s.cases!==225) throw new Error(JSON.stringify(s));
    await page.screenshot({path:path.resolve('work/rayggxia/95/ideal_quality_20261025/preview-'+width+'.png')});
    checks.push(s);
  }
  if(errors.length)throw new Error(errors.join('\n'));
  fs.writeFileSync('work/rayggxia/95/ideal_quality_20261025/BROWSER_CHECK.json',JSON.stringify({status:'PASS',checks,errors},null,2)+'\n');
  await browser.close();
  console.log(JSON.stringify({status:'PASS',checks}));
})().catch(e=>{console.error(e);process.exit(1)});
