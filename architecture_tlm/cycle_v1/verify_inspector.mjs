// Exercise the generated inspector's real JS in a minimal DOM; no layout claim.
import fs from 'node:fs';
import vm from 'node:vm';
import crypto from 'node:crypto';
const file=process.argv[2];
const html=fs.readFileSync(file,'utf8');
const script=html.match(/<script>([\s\S]*)<\/script>/)[1];
const elements=new Map();
function element(){return {value:'',textContent:'',style:{},children:[],events:{},
    append(...items){this.children.push(...items)},replaceChildren(...items){this.children=items},
    addEventListener(name,fn){this.events[name]=fn}}}
const document={getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id)},
                createElement(){return element()}};
document.getElementById('left').value='0';
const context=vm.createContext({document});
vm.runInContext(script,context,{timeout:10000});
const count=document.getElementById('grid').children.length;
if(!count) throw new Error('initial rendering empty');
const bar=document.getElementById('grid').children[0].children[1].children[0];
bar.onclick();
const detail=JSON.parse(document.getElementById('detail').textContent);
if(!detail.id||!detail.resource||!Array.isArray(detail.dependencies))throw new Error('click details missing');
document.getElementById('filter').value='sram';
document.getElementById('filter').events.input();
const filtered=document.getElementById('grid').children.length;
if(!filtered||filtered>count)throw new Error('resource filtering failed');
document.getElementById('right').value='0';
document.getElementById('right').events.input();
if(document.getElementById('grid').children.length!==0)throw new Error('invalid range did not clear grid');
document.getElementById('filter').value='';
document.getElementById('reset').onclick();
if(document.getElementById('grid').children.length!==count)throw new Error('reset failed');
console.log(JSON.stringify({passed:true,rows:count,filtered_sram_rows:filtered,
    click_details:true,range_guard:true,reset:true,sha256:crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'),
    scope:'generated JavaScript functional check with minimal DOM; browser layout not inspected'}));
