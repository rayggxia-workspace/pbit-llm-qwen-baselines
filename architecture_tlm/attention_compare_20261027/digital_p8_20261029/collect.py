"""Postprocess immutable source/results; all quantities preserve original reports."""
from pathlib import Path
import hashlib,json,re,sys,zipfile
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(p,x):p.write_bytes((json.dumps(x,indent=2)+'\n').encode())
def val(pat,s):
 m=re.search(pat,s,re.M);assert m,pat;return float(m.group(1))
def main(root,version,indices=None,collection_label=None):
 r=Path(root);s=r/'snapshots'/version;rr=r/'results'/version;out=r/('collection_'+(collection_label or version));out.mkdir(exist_ok=False)
 cases=json.loads((s/'CASES.json').read_text());results=[]
 if indices is not None:cases=[cases[i] for i in indices]
 for c in cases:
  d=rr/('ppa_'+c['top']);pre=json.loads((rr/('preflight_'+c['top'])/'COMPLETE.json').read_text());done=json.loads((d/'COMPLETE.json').read_text())
  assert pre['source_sha256']==done['source_sha256']==sha(s/'SOURCE.json')
  dc=Path(done.get('dc_reference',str(d/'dc')))
  inv=[x.split('\t') for x in (dc/'inventory.tsv').read_text().splitlines()[1:]]
  area=sum(float(x[2]) for x in inv);assert abs(area-float((dc/'area_um2.txt').read_text()))<1e-5
  windows=[]
  for w in done['windows']:
   p=rr/w['path'];log=(p/'pt.log').read_text(errors='replace');report=(p/'power.rpt').read_text()
   assert (p/'PT_COMPLETE').exists() and re.search(r'Dynamic Power Units\s*=\s*1 W',report) and re.search(r'Leakage Power Units\s*=\s*1 W',report)
   powers={k:val(pattern,report) for k,pattern in dict(total_W=r'^Total Power\s*=\s*([0-9.eE+-]+)',switching_W=r'Net Switching Power\s*=\s*([0-9.eE+-]+)',internal_W=r'Cell Internal Power\s*=\s*([0-9.eE+-]+)',leakage_W=r'Cell Leakage Power\s*=\s*([0-9.eE+-]+)').items()}
   assert abs(powers['total_W']-sum(powers[k] for k in ('switching_W','internal_W','leakage_W')))<max(1e-8,powers['total_W']*.005)
   net=val(r'Number of annotated nets\s*=.*?\(([0-9.]+)%\)',log);cell=val(r'Number of fully annotated leaf cells\s*=.*?\(([0-9.]+)%\)',log)
   slacks={n:float((p/(n+'_ns.txt')).read_text()) for n in ('setup','hold')}
   for n in ('gate_setup','gate_hold'):
    if (p/(n+'_ns.txt')).exists():
     value=(p/(n+'_ns.txt')).read_text().strip();slacks[n]=None if value=='NA' else float(value)
   windows.append(dict(w,power=powers,energy_pJ=powers['total_W']*(w['end_ns']-w['start_ns'])*1000,
       slacks_ns=slacks,annotated_nets_pct=net,annotated_cells_pct=cell,
       warnings=sorted(set(re.findall(r'Warning:.*',log))),
       check_power_warnings=sorted(set(re.findall(r'Warning:.*',(p/'check_power.rpt').read_text(errors='replace')))),
       check_power_sha256=sha(p/'check_power.rpt'),report_sha256=sha(p/'power.rpt')))
  cycles=[]
  for check in done['checks']:
   cycles.extend(dict(seed=check['seed'],stall=check['stall'],query=int(i),front_cycles=int(f),full_cycles=int(n)) for i,f,n in re.findall(r'QUERY (\d+) front_cycles=(\d+) full_cycles=(\d+)',check['log']))
  results.append(dict(case=c,raw_area_um2=area,area55_mm2=area*.81/1e6,
      area_groups_raw_um2={g:sum(float(x[2]) for x in inv if x[3]==g) for g in ('register','logic','icg')},
      cell_counts={g:sum(x[3]==g for x in inv) for g in ('register','logic','icg')},cycles=cycles,windows=windows,
      rtl_checks=len(pre['checks']),gate_checks=len(done['checks']),netlist_sha256=sha(dc/'mapped.v'),sdc_sha256=sha(dc/'mapped.sdc')))
 assert len(results)==len(cases) and sum(len(x['windows']) for x in results)==sum(6 if x['mode']==0 else 9 for x in cases)
 runtime={}
 lib=Path('/public3/home/t6s011227/ICsprout_55LLULP1225_STD_0818/ICsprout55_SC9T_BASIC_SVT/0.1')
 for name,rel in [('standard_db','lib/ICsprout55_9TSVT_ss_v1p08_125c_basic_nldm.db'),('standard_model','verilog/ICsprout55_9TSVT_basic.v')]:
  p=lib/rel;runtime[name]=dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
 save(out/'RESULTS.json',dict(version=version,results=results,runtime_fingerprints=runtime,source_manifest_sha256=sha(s/'SOURCE.json'),area_scale=.81,
      boundary='FP32 converter + fixed approximate softmax + P8 bank + backend + compact Bivium + count stream; no V fetch/mapping/accumulation, CTS/SPEF/SDF, physical entropy or model PPL'))
 files=[]
 for p in r.rglob('*'):
  if not p.is_file() or any(x.startswith('collection_') or x in ('uploads','csrc','work') or x.endswith('.daidir') for x in p.relative_to(r).parts):continue
  parts=p.relative_to(r).parts
  if parts[0]=='results' and parts[1] not in ('v1',version):continue
  if len(parts)==1 and p.suffix=='.log':continue
  if collection_label and parts[0]=='results' and parts[1]==version and len(parts)>2:
   if parts[2].startswith('ppa_') and parts[2] not in ['ppa_'+c['top'] for c in cases]:continue
   if parts[2].startswith('slurm_38459583_') and int(parts[2].split('_')[-1].split('.')[0]) not in indices:continue
  if p.suffix in ('.rpt','.log','.json','.txt','.tsv','.v','.sdc','.vcd','.sv','.vh','.py','.sh','.tcl','.mem'):files.append(p)
 files += [out/'RESULTS.json'];files=sorted(set(files));index={str(p.relative_to(r)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in files}
 save(out/'RAW_INDEX.json',index);files.append(out/'RAW_INDEX.json');archives={}
 for name,selected in [('RAW',files),('REPORTS',[p for p in files if p.suffix not in ('.v','.vcd')])]:
  dest=out/(name+'.zip')
  with zipfile.ZipFile(str(dest),'w',zipfile.ZIP_DEFLATED) as z:
   for p in selected:z.write(str(p),str(p.relative_to(r)))
  archives[name]=dict(path=str(dest),sha256=sha(dest),bytes=dest.stat().st_size)
 save(out/'COLLECTION.json',dict(files=len(index),archives=archives,results_sha256=sha(out/'RESULTS.json'),index_sha256=sha(out/'RAW_INDEX.json')))
 print(json.dumps(json.loads((out/'COLLECTION.json').read_text())))
if __name__=='__main__':main(sys.argv[1],sys.argv[2],[int(x) for x in sys.argv[3].split(',')] if len(sys.argv)>3 else None,sys.argv[4] if len(sys.argv)>4 else None)
