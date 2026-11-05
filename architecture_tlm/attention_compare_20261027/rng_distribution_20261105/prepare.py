"""Freeze existing captured scores; no model execution or PPL claim."""
from pathlib import Path
import hashlib,json,re,subprocess,random,importlib.util,sys
import numpy as np
P=Path(__file__).resolve().parent;R=P.parents[2];WS=R.parents[1]
A=WS/'project_archives/attention_rng198_20261105';A.mkdir(parents=True,exist_ok=True)
B=P.parent/'sampler_gate_hold_20261105'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
source=json.loads((B/'INPUT_SOURCE.json').read_bytes());sel=Path(source['selected_path'])
assert sha(sel)==source['selected_sha256']
for n,v in source['capture']['files'].items():assert sha(Path(source['capture']['local'])/n)==v['sha256']
lut={int(a):int(b) for a,b in re.findall(r"8'd(\d+):sigmoid=8'd(\d+)",(B/'sigmoid.vh').read_text())}
rows=[]
synthetic=[('uniform',[0.]*128),('two_peaks',[0.,0.]+[-8.]*126),('four_peaks',[0.]*4+[-4.]*124),('ramp',np.linspace(-8,0,128).tolist()),('single_peak',[-8.]*127+[0.]),('gaussian',np.random.default_rng(198).normal(0,2,128).tolist())]
for name,z in synthetic:rows.append(dict(id=name,kind='synthetic',logits=z))
for r in sorted(json.loads(sel.read_bytes()),key=lambda x:(x['layer'],x['kv_group'])):
 for h,z in enumerate(r['logits']):rows.append(dict(id=f'L{r["layer"]}_H{r["kv_group"]*4+h}',kind='captured',logits=z,layer=r['layer'],head=r['kv_group']*4+h))
for r in rows:
 q=[max(-2048,min(2047,round(x*16))) for x in r['logits']];r['threshold']=[lut[min(max(q)-x,255)] for x in q]
 z=np.asarray(r['logits']);e=np.exp(z-z.max());r['softmax']=(e/e.sum()).tolist()
 p=np.asarray(r['threshold'])/256.;odds=p/(1-p);r['pi_p8']=(odds/odds.sum()).tolist()
save(A/'rows_private.json',rows)
(A/'rows.txt').write_bytes((str(len(rows))+'\n'+''.join(r['id']+' '+' '.join(map(str,r['threshold']))+'\n' for r in rows)).encode())
sym={f'state[{i}]':1<<i for i in range(32)};words=[];nxt={}
for line in (B/'rng_shared64_map.sv').read_text().splitlines():
 m=re.match(r'\s*assign ([gt]\d+) = (.*);',line)
 if m:
  v=0
  for term in m[2].split('^'):v^=sym[term.strip()]
  sym[m[1]]=v
 m=re.match(r'\s*assign random_word\[\d+ \+: 8\] = \{(.*)\};',line)
 if m:words.extend(sym[x.strip()] for x in reversed(m[1].split(',')))
 m=re.match(r'\s*assign next_state\[(\d+)\] = (.*);',line)
 if m:nxt[int(m[1])]=sym[m[2].strip()]
assert len(words)==512 and len(nxt)==32
table=np.zeros((4,256,9),dtype='<u8')
def gf(s):
 w=sum(((s&m).bit_count()&1)<<i for i,m in enumerate(words));ns=sum(((s&nxt[j]).bit_count()&1)<<j for j in range(32));return w,ns
for k in range(4):
 for b in range(256):
  w,ns=gf(b<<(8*k))
  for j in range(8):table[k,b,j]=(w>>(j*64))&((1<<64)-1)
  table[k,b,8]=ns
table.tofile(A/'gf_tables.bin')
spec=importlib.util.spec_from_file_location('old',P.parent/'digital_p8_20261029/generate.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
def limbs(s):
 a=s&((1<<93)-1);b=s>>93
 return [a&((1<<64)-1),a>>64,b&((1<<64)-1),b>>64]
tests=[];expected=[];rnd=random.Random(198)
for s in [0]+[1<<i for i in range(32)]+[rnd.getrandbits(32) for _ in range(100)]:
 w,ns=gf(s);tests.append('G '+str(s));expected.append(['G',ns]+[(w>>(8*j))&255 for j in range(64)])
for s in [0]+[1<<i for i in range(177)]+[rnd.getrandbits(177) for _ in range(100)]:
 w,ns=old.bivium(s);tests.append('B '+' '.join(map(str,limbs(s))));expected.append(['B',w&127]+limbs(ns))
oracle=json.loads((B/'ORACLE.json').read_bytes())
for seed in [17,503,1009]:
 for g in range(8):
  folder=B/'fixtures/ab_both'/f's{seed}_g{g}';seedwords=[int(x,16) for x in (folder/'seed.mem').read_text().split()]
  bs=0
  for x in seedwords[2:8]:bs=((bs<<32)|x)&((1<<177)-1)
  for _ in range(5):_,bs=old.bivium(bs)
  qs=sorted([q for q in oracle['queries'] if q['top']=='ab_both' and q['seed']==seed and q['kv_group']==g],key=lambda q:q['query'])
  scores=[int(x,16) for x in (folder/'score.mem').read_text().split()];scores=[x-4096 if x>=2048 else x for x in scores]
  thresholds=[]
  for i in range(12):
   q=scores[i*128:(i+1)*128];thresholds +=[lut[min(max(q)-x,255)] for x in q]
  tests.append('Q '+' '.join(map(str,seedwords[:2]+limbs(bs)+[12]+thresholds)))
  expected.append(['Q']+[v for q in qs for v in q['outputs']])
(A/'verify.txt').write_bytes(('\n'.join(tests)+'\n').encode());save(A/'verify_expected.json',expected)
save(A/'INPUT_MANIFEST.json',dict(parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),source=source,inputs={str(p):sha(p) for p in [sel,B/'sigmoid.vh',B/'rng_shared64_map.sv',B/'rng_bivium_map.sv',B/'ORACLE.json',Path(source['model_manifest_path'])]},derived={p.name:sha(p) for p in [A/'rows.txt',A/'rows_private.json',A/'gf_tables.bin',A/'verify.txt']},scope='Offline fixed captured-score RNG diagnostic, no V tensors available, no new model/BF16/PPL/RTL/PPA',modes=['iid_iid','gf_iid','iid_biv','gf_biv','shared_lfsr1_iid','shared_iid_iid','shared_lfsr8_iid'],short=dict(replicates=128,samples=[16,32,64,128,256],initial=0,burn=0),long=dict(replicates=8,samples=32768,burn=4096,rows=[0,1,2,3,4,5,6,7,38,39,70,71]),lfsr='right-shift Galois 0x80200003; low8 broadcast; advance1 and advance8',iid='C++ mt19937_64 separate candidate/fair streams; numerical IID reference, not physical entropy'))
print('Prepared',len(rows),'rows;',len(expected),'verification cases;',A)
