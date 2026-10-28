"""Post-run parser; preserves original bytes and all timing/power warnings."""
from pathlib import Path
import hashlib,json,sys,re,tarfile
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(p,x):p.write_bytes((json.dumps(x,indent=2)+'\n').encode())
def val(pat,s):
 m=re.search(pat,s,re.M);assert m,pat;return float(m.group(1))
def main(root):
 r=Path(root);out=r/'collection';out.mkdir(exist_ok=False)
 specs=json.loads((r/'source/CASES.json').read_text());results=[]
 for c in specs:
  d=r/'results'/c['top'];complete=json.loads((d/'COMPLETE.json').read_text());dc=d/'dc'
  assert complete['netlist_sha256']==sha(dc/'mapped.v') and complete['sdc_sha256']==sha(dc/'mapped.sdc')
  inv=[x.split('\t') for x in (dc/'inventory.tsv').read_text().splitlines()[1:]]
  area={g:sum(float(x[2]) for x in inv if x[3]==g) for g in ('register','icg','logic')}
  counts={g:sum(x[3]==g for x in inv) for g in area}
  assert counts['register']==128*c['width'] and counts['icg']==c['gated']*32
  assert abs(sum(area.values())-float((dc/'area_um2.txt').read_text()))<1e-5
  windows=[]
  for item in complete['power']:
   p=d/item['directory'];log=(p/'pt.log').read_text(errors='replace');report=(p/'power.rpt').read_text()
   assert (p/'PT_COMPLETE').exists() and re.search(r'Dynamic Power Units\s*=\s*1 W',report) and re.search(r'Leakage Power Units\s*=\s*1 W',report)
   power={k:val(pattern,report) for k,pattern in dict(total_W=r'^Total Power\s*=\s*([0-9.eE+-]+)',
    switching_W=r'Net Switching Power\s*=\s*([0-9.eE+-]+)',internal_W=r'Cell Internal Power\s*=\s*([0-9.eE+-]+)',leakage_W=r'Cell Leakage Power\s*=\s*([0-9.eE+-]+)').items()}
   assert abs(power['total_W']-sum(power[k] for k in ('switching_W','internal_W','leakage_W')))<max(1e-8,power['total_W']*.005)
   net=val(r'Number of annotated nets\s*=.*?\(([0-9.]+)%\)',log);cell=val(r'Number of fully annotated leaf cells\s*=.*?\(([0-9.]+)%\)',log)
   assert net==cell==100.,(c['top'],net,cell)
   slacks={n:float((p/(n+'_ns.txt')).read_text()) for n in ('setup','hold')}
   for n in ('gate_setup','gate_hold'):
    if (p/(n+'_ns.txt')).exists():
     s=(p/(n+'_ns.txt')).read_text().strip();slacks[n]=None if s=='NA' else float(s)
   warnings=sorted(set(re.findall(r'Warning:.*',log)))
   checks=(p/'check_power.rpt').read_text(errors='replace')
   w=item['window'];dur=w['end']-w['start']
   windows.append(dict(seed=item['seed'],window=w,power=power,energy_pJ=power['total_W']*dur*1000,
    slacks_ns=slacks,annotated_nets_pct=net,annotated_cells_pct=cell,warnings=warnings,check_power_text=checks,
    report_sha256=sha(p/'power.rpt')))
  results.append(dict(case=c,raw_area_um2=sum(area.values()),area55_um2=sum(area.values())*.81,area_groups_raw_um2=area,
    counts=counts,checks=complete['checks'],windows=windows,execution=json.loads((d/'EXECUTION.json').read_text()),
    worst_setup_ns=min(x['slacks_ns']['setup'] for x in windows),worst_hold_ns=min(x['slacks_ns']['hold'] for x in windows)))
 assert len(results)==7 and sum(len(x['windows']) for x in results)==84 and sum(len(x['checks']) for x in results)==42
 save(out/'RESULTS.json',dict(results=results,source=json.loads((r/'source/SOURCE.json').read_text()),collector_sha256=sha(Path(__file__)),
  boundary='128-word bank + write decode + actual ICG; comparator variants add 128 parallel unsigned LT, external random input. No LUT/FP converter/max/RNG/arbiter/V/CTS/SPEF/SDF.',
  area_scale=.81,conditions='SS1.08V125C100MHz, raw SHARK geometry; synthetic 3seed activities. Load8 + sample160 includes burn32/S128, idle32 separately.'))
 files=[]
 for p in (r/'results').rglob('*'):
  if not p.is_file():continue
  if any(x in ('csrc','work') or x.endswith('.daidir') for x in p.parts):continue
  if p.suffix in ('.rpt','.log','.json','.txt','.tsv','.v','.sdc','.vcd'):files.append(p)
 files+=list(r.glob('SUBMIT*.json'))+list(r.glob('*.sh'))+[p for p in (r/'source').rglob('*') if p.is_file()]+[out/'RESULTS.json',Path(__file__)]
 files=sorted(set(files));index={str(p.relative_to(r)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in files}
 save(out/'RAW_INDEX.json',index);files.append(out/'RAW_INDEX.json')
 archives={}
 for name,selected in [('RAW',[p for p in files]),('REPORTS',[p for p in files if p.suffix not in ('.v','.vcd')])]:
  dest=out/(name+'.tar.gz')
  with tarfile.open(str(dest),'w:gz') as tar:
   for p in selected:tar.add(str(p),arcname=str(p.relative_to(r)),recursive=False)
  archives[name]=dict(path=str(dest),sha256=sha(dest),bytes=dest.stat().st_size)
 save(out/'COLLECTION.json',dict(files=len(index),archives=archives,results_sha256=sha(out/'RESULTS.json'),index_sha256=sha(out/'RAW_INDEX.json')))
 print(json.dumps(json.loads((out/'COLLECTION.json').read_text())))
if __name__=='__main__':main(sys.argv[1])
