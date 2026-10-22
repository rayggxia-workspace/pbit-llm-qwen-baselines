"""Audit analysis provenance, module paths, units and exact integer alternative."""
import collections,hashlib,json,random,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];D=ROOT/'architecture_tlm/digital_ppa_v1';OUT=Path(__file__).resolve().parent
C=collections.Counter();bindings=[]
def check(g,b,msg):
 C[g]+=1
 if not b:raise AssertionError(msg)
def gitblob(ref,p):return subprocess.check_output(['git','show',ref+':'+p],cwd=ROOT,stderr=subprocess.DEVNULL)
def main():
 s=json.loads((OUT/'SOURCE_INDEX.json').read_text(encoding='utf-8'));tasks=json.loads((D/'LATEST_TLM_RTL_REQUESTS.json').read_text(encoding='utf-8'))['tasks']
 for e in s['files']:
  b=gitblob(e['commit'],e['path']);check('source_git_sha',len(b)==e['bytes'] and hashlib.sha256(b).hexdigest()==e['sha256'],e['path'])
 check('task_schema',len(tasks)==11 and len(set(t['id'] for t in tasks))==11,'unique tasks')
 for t in tasks:
  check('task_schema',bool(t['boundary'] and t['return_units'] and t['TLM'] and t['warning']),t['id'])
  for name,status in t['top_status'].items():check('proposed_labels',status.startswith('PROPOSED')==name.startswith('proposed_'),t['id'])
  for p in t['existing']:
   if p.startswith('C:/'):
    b=Path(p).read_bytes();bindings.append(dict(path=p,commit=None,sha256=hashlib.sha256(b).hexdigest(),binding='local interface reference only; not delivered RTL'))
   elif p.endswith('/rtl'):
    b=subprocess.check_output(['git','ls-tree','-r',s['TLM'],'--',p],cwd=ROOT);check('path_exists',bool(b),p);bindings.append(dict(path=p,commit=s['TLM'],binding='existing source directory'))
   else:
    found=False
    for ref in [s['TLM'],s['RTL']]:
     try:b=gitblob(ref,p);found=True;break
     except subprocess.CalledProcessError:pass
    check('path_exists',found,p);bindings.append(dict(path=p,commit=ref,sha256=hashlib.sha256(b).hexdigest()))
 m=s['metrics'];check('width_and_units',m['tile_count_state_bits']==49152 and m['wave_count_state_bits']==393216,'count state')
 check('width_and_units',m['alternative_tile_state_bits']==5120 and m['tile_count_state_bits']/m['alternative_tile_state_bits']==9.6,'binsum state')
 check('width_and_units',-(1<<19)<=-64*128*32 and 64*128*32<1<<19,'signed20 bound')
 check('width_and_units',64*128> (1<<13)-1 and 64*128 < (1<<14),'sample partial needs15signed bits')
 check('width_and_units',m['single_issue_64B_at_100MHz_GBs']==6.4 and m['immediate_weight_feed_if_no_retention_GBs']==3276.8 and m['SRAM_ports_peak_GBs']==20.48,'bandwidth')
 check('width_and_units',m['theoretical_511x9_LUT_bits']==4599 and m['program_64_lanes_bits_per_cycle']==576,'LUT/config width')
 # Independent exact-integer arithmetic check only, not RTL or PPL.
 for seed in [17,503,1009]:
  rng=random.Random(seed)
  for trial in range(12):
   bins=[rng.randrange(4) for _ in range(64)];sign=[rng.randrange(2) for _ in range(64)];q=[rng.randrange(257) for _ in range(64)]
   hits=[0]*64
   for stratum in range(32):
    threshold=stratum*8+rng.randrange(8)
    for i in range(64):hits[i]+=threshold<q[i]
   for col in range(8):
    weights=[rng.randrange(-128,128) for _ in range(64)]
    if trial==0:weights=[-128]*64;sign=[1]*64;q=[256]*64;hits=[32]*64
    direct=[sum(((-1)**sign[i])*weights[i]*hits[i] for i in range(64) if bins[i]==bn) for bn in range(4)]
    planes=[]
    for bn in range(4):
     v=0
     for p in range(8):
      bitw=-(1<<p) if p==7 else 1<<p
      pc=sum(hits[i] for i in range(64) if bins[i]==bn and sign[i]==0 and ((weights[i]&255)>>p)&1)
      nc=sum(hits[i] for i in range(64) if bins[i]==bn and sign[i]==1 and ((weights[i]&255)>>p)&1)
      check('counter_bound',0<=pc<=2048 and 0<=nc<=2048,'plane counts');v+=(pc-nc)*bitw
     planes.append(v)
    check('exact_per_bin_identity',direct==planes and all(-(1<<19)<=x<(1<<19) for x in direct),'four-bin exact identity')
 template=json.loads((D/'PPA_RETURN_TEMPLATE.json').read_text(encoding='utf-8'))
 check('template_not_result',template['status']=='TEMPLATE_NOT_MEASURED' and template['power']['total_uW'] is None,'unknown remainsnull')
 body=(D/'LATEST_TLM_RTL_GAPS_ZH.md').read_text(encoding='utf-8')
 for t in tasks:check('document_coverage',t['id'] in body,t['id'])
 result=dict(status='PASS',checks=sum(C.values()),groups=dict(C),bindings=bindings,
  source_index_sha256=hashlib.sha256((OUT/'SOURCE_INDEX.json').read_bytes()).hexdigest(),
  files={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [D/'LATEST_TLM_RTL_GAPS_ZH.md',D/'LATEST_TLM_RTL_REQUESTS.json',D/'PPA_RETURN_TEMPLATE.json']},
  scope='read-only source/paths/units and exact-integer mathematical check; no newRTL/EDA/TLM/model run')
 with (OUT/(sys.argv[1] if len(sys.argv)>1 else 'VALIDATION.json')).open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps(dict(status='PASS',checks=result['checks'],groups=dict(C))))
if __name__=='__main__':main()
