"""Verify frozen sources/report members and derive BF16 energy/area tables.

No EDA or network operations. All original bytes remain in project_archives.
"""
from pathlib import Path
import hashlib,json,math,re,statistics,tarfile,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];WS=ROOT.parents[1]
P=ROOT/'architecture_tlm/bf16_ppa_20261028';A=WS/'project_archives/matrix204_bf16_ppa_20261028'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 remote=json.loads((A/'REMOTE_ATTEST.json').read_text());packages=[];reports=[];transfers=[];rows=[];functional=[];failures=[];sta=[]
 for zpath in sorted(A.glob('bf16_204_*.zip')):
  name=zpath.stem
  key=next(k for k in remote if k.endswith('/'+zpath.name));assert remote[key]==dict(sha256=sha(zpath),bytes=zpath.stat().st_size)
  with zipfile.ZipFile(zpath) as z:
   raw=z.read(name+'/EXECUTION_MANIFEST.json');m=json.loads(raw)
   for n,h in m['files'].items():assert hashlib.sha256(z.read(name+'/'+n)).hexdigest()==h,n
   if '_v7_' in name:
    for n,h in m['files'].items():assert sha(P/n)==h,n
   if '_sta_' in name:assert sha(HERE/'reset_contract_sta.py')==m['files']['reset_contract_sta.py']
  packages.append(dict(path=str(zpath),sha256=sha(zpath),bytes=zpath.stat().st_size,manifest_sha256=hashlib.sha256(raw).hexdigest(),members_verified=len(m['files'])))
 for tf in sorted(A.glob('bf16_204_*_TRANSFER.json')):
  for item in json.loads(tf.read_text()):
   p=Path(item['path']);assert sha(p)==item['sha256'];assert remote[item['remote']]==dict(sha256=sha(p),bytes=p.stat().st_size)
   transfers.append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size,remote=item['remote']))
 for p in sorted(A.glob('*/reports.tar.gz')):
  with tarfile.open(p) as t:
   m=json.load(t.extractfile('RETURN_MANIFEST.json'))['files']
   for n,h in m.items():assert hashlib.sha256(t.extractfile(n).read()).hexdigest()==h,(str(p),n)
   r=json.load(t.extractfile('RESULT.json'));assert sha(p.parent/'RESULT.json')==m['RESULT.json']
   reports.append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size,members_verified=len(m),result_member_sha256=m['RESULT.json']))
   if p.parent.name.startswith('sta_'):
    sta.append(r);continue
   if r['stage']=='functional':
    functional.append(dict(directory=p.parent.name,case=r['case']['name'],status=r['status'],functional=r['functional']))
    if r['status']=='failed':failures.append(dict(directory=p.parent.name,case=r['case']['name'],error=r['error']))
    continue
   if r['status']!='calculated':failures.append(dict(directory=p.parent.name,case=r['case']['name'],error=r['error']));continue
   assert len(r['windows'])==9
   gates=[];frame_cycles=[]
   for seed in [17,503,1009]:
    log=t.extractfile('gate_%d/simulation.log'%seed).read().decode()
    match=re.search(r'FUNCTION_PASS (?:transactions|frames)=(\d+)',log);assert match,(p,seed)
    gates.append(dict(seed=seed,transactions=int(match[1])))
    if r['case']['name']=='dot64_4':
     replay=json.load(t.extractfile('gate_%d/REPLAY.json'%seed));frame_cycles+=replay['frame_cycles']
   row=dict(case=r['case'],raw_area_um2=r['raw_area_um2'],area_55eq_um2=r['area_55eq_um2'],mapped_sha256=r['mapped_sha256'],raw_setup_slack_ns=min(w['setup_slack_ns'] for w in r['windows']),raw_hold_slack_ns=min(w['hold_slack_ns'] for w in r['windows']),review_flags=sorted({f for w in r['windows'] for f in w['review_flags']}),all_mapped_pin_activity_verified=all(w['all_mapped_pin_activity_verified'] and w['leaf_coverage_percent']==100 for w in r['windows']),gate_replays=gates,profiles={})
   row['result_directory']=p.parent.name
   if 'REUSED_SYNTH.json' in t.getnames():row['reuse_proof']=json.load(t.extractfile('REUSED_SYNTH.json'))
   assert math.isclose(row['area_55eq_um2'],.81*row['raw_area_um2'],rel_tol=1e-12)
   for mode in ['normal','int8','idle']:
    ww=[w for w in r['windows'] if w['mode']==mode];assert len(ww)==3
    q={k:statistics.mean(w[k] for w in ww) for k in ['total_W','internal_W','switching_W','leakage_W','window_ns','operations']}
    q['seed_results']=[{k:w[k] for k in ['seed','total_W','gross_pJ_per_operation','operations','window_ns','cycles_per_operation']} for w in ww]
    if mode!='idle':q.update(energy_pJ=statistics.mean(w['gross_pJ_per_operation'] for w in ww),energy_std_pJ=statistics.pstdev(w['gross_pJ_per_operation'] for w in ww),cycles_per_operation=ww[0]['cycles_per_operation'])
    row['profiles'][mode]=q
   if frame_cycles:row['latency_cycles_observed']=sorted({x[1] for x in frame_cycles});row['normal_latency_cycles']=29;row['frame_interval_cycles']=30
   rows.append(row)
 assert len(rows)==5 and len(sta)==5
 for r in rows:
  s=next(x for x in sta if x['case']==r['case']['name']);assert s['mapped_sha256']==r['mapped_sha256']
  r['reset_contract_sta']=s
 f6=[x for x in functional if x['directory'].startswith('functional_38444739_')];assert len(f6)==5 and all(x['status']=='pass' and len(x['functional'])==3 for x in f6)
 result=dict(date='2026-10-28',source_base='99bf019c21ac1c9da226d636b5f7ea3d3097022f',execution_source_manifest_sha256=sha(P/'EXECUTION_MANIFEST.json'),PVT='SS1.08V125C',clock_MHz=100,area_multiplier=.81,source_packages=packages,report_archives=reports,transfer_files_verified=len(transfers),functional=f6,functional_history=functional,failures_preserved=failures,PPA=sorted(rows,key=lambda r:r['case']['name']),supplemental_sta=sta,power_windows=45,metadata_errata=['Frozen driver operation_definition says scalar for all tops. For dot64_4 each operation is one complete N64 dot product, 64 products; windows contain16 frames over480ns each, i.e.4800ns per profile. Power/time/operations numeric fields are correct.','The original shared reset constraints assume deassertion0.02..1ns from rising edge. FPnew async reset removal violates this. Separate STA on identical mapped bytes uses explicit reset release4.5..5.5ns, matching the falling-edge bench. No recovery/removal false path, data constraint change or power recomputation.'],boundary='Specialized FPnew BF16xBF16/FP32; non-fused folded DOT4 full N64 includes four FP32 contexts and final reduction. No SRAM, operand stream generation, RNG, quantization/format frontends, CTS/SDF/SPEF/physical wires. Synthetic3seeds, not LLM traces/PPL. Timing and power are prelayout, not silicon signoff.')
 result['metadata_errata'][0]=result['metadata_errata'][0].replace('480ns each','300ns each')
 result['source_provenance']='Scalar PPA v6; N64 PPA v7 reuses identical v6 mapped netlist with exact RTL/fixture/library-binding/constraint equality proof. Only TB time-type clipping and reuse driver changed.'
 for x in transfers:
  if 'bf16_204_v1_20261028_logs' in x['path']:
   failures.append(dict(directory=Path(x['path']).name,kind='EDA_before_bootstrap_failure',error='Default Python2 syntax rejection before EDA',artifact=x['path']))
 save(P/'results/FINAL_SUMMARY.json',result)
 save(HERE/'TRANSFER_VERIFICATION.json',dict(files=transfers,remote_source_sha_verified=True,all_report_members_verified=True))
 print('VERIFIED',len(packages),'execution packages',len(reports),'report archives',len(transfers),'transfers')
 for r in result['PPA']:
  print(r['case']['name'],r['area_55eq_um2'],{k:(v['total_W'],v.get('energy_pJ')) for k,v in r['profiles'].items()},r['reset_contract_sta']['setup_slack_ns'],r['reset_contract_sta']['hold_slack_ns'])
if __name__=='__main__':main()
