"""Verify original INT8 packages/reports and derive complete-frame metrics."""
from pathlib import Path
import hashlib,json,math,re,statistics,tarfile,zipfile
HERE=Path(__file__).resolve().parent;R=HERE.parents[3];W=R.parents[1]
P=R/'architecture_tlm/int8_classic_ppa_20261028';A=W/'project_archives/matrix204_int8_classic_ppa_20261028'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 remote=json.loads((A/'REMOTE_ATTEST.json').read_text());packages=[];reports=[];transfers=[];rows=[];functions=[];failures=[]
 for p in sorted(A.glob('int8_204_v*.zip')):
  key=next(k for k in remote if k.endswith('/'+p.name));assert remote[key]==dict(sha256=sha(p),bytes=p.stat().st_size)
  with zipfile.ZipFile(p) as z:
   raw=z.read(p.stem+'/EXECUTION_MANIFEST.json');m=json.loads(raw)
   for n,h in m['files'].items():assert hashlib.sha256(z.read(p.stem+'/'+n)).hexdigest()==h,n
   if p.name==sorted(A.glob('int8_204_v*.zip'))[-1].name:
    for n,h in m['files'].items():assert sha(P/n)==h,n
  packages.append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size,manifest_sha256=hashlib.sha256(raw).hexdigest(),members_verified=len(m['files'])))
 for tf in sorted(A.glob('int8_204_v*_TRANSFER.json')):
  for item in json.loads(tf.read_text()):
   p=Path(item['path']);assert sha(p)==item['sha256'];assert remote[item['remote']]==dict(sha256=sha(p),bytes=p.stat().st_size)
   transfers.append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size,remote=item['remote']))
 for p in sorted(A.glob('*/reports.tar.gz')):
  with tarfile.open(p) as t:
   manifest=json.load(t.extractfile('RETURN_MANIFEST.json'))['files']
   for n,h in manifest.items():assert hashlib.sha256(t.extractfile(n).read()).hexdigest()==h,n
   r=json.load(t.extractfile('RESULT.json'));assert sha(p.parent/'RESULT.json')==manifest['RESULT.json']
   reports.append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size,members_verified=len(manifest),result_member_sha256=manifest['RESULT.json']))
   if r['stage']=='functional':functions.append(dict(directory=p.parent.name,case=r['case'],status=r['status'],functional=r['functional']));continue
   if r['status']!='calculated':failures.append(dict(directory=p.parent.name,case=r['case'],error=r.get('error')));continue
   assert len(r['windows'])==9 and all(w['all_mapped_pin_activity_verified'] and w['leaf_coverage_percent']==100 for w in r['windows'])
   gate=[];lat=[]
   for seed in [17,503,1009]:
    log=t.extractfile('gate_%d/simulation.log'%seed).read().decode();assert 'FUNCTION_PASS transactions=36' in log
    rr=json.load(t.extractfile('gate_%d/REPLAY.json'%seed));lat+=rr['frame_cycles'];gate.append(dict(seed=seed,frames=36,VCD_sha256=rr['VCD_sha256']))
   row=dict(case=r['case'],raw_area_um2=r['raw_area_um2'],area_55eq_um2=r['area_55eq_um2'],mapped_sha256=r['mapped_sha256'],archive=str(p),setup_slack_ns=min(w['setup_slack_ns'] for w in r['windows']),hold_slack_ns=min(w['hold_slack_ns'] for w in r['windows']),review_flags=sorted({f for w in r['windows'] for f in w['review_flags']}),all_mapped_pin_activity_verified=True,gate_replays=gate,latency_cycles_observed=sorted({x[1] for x in lat}),normal_latency_cycles=next(x[1] for x in lat if x[0]==4),profiles={})
   assert math.isclose(row['area_55eq_um2'],.81*row['raw_area_um2'],rel_tol=1e-12)
   for mode in ['matched','fullrange','idle']:
    ww=[w for w in r['windows'] if w['mode']==mode];assert len(ww)==3
    q={k:statistics.mean(w[k] for w in ww) for k in ['total_W','internal_W','switching_W','leakage_W','window_ns','operations']}
    q['seed_results']=[{k:w[k] for k in ['seed','total_W','gross_pJ_per_operation','operations','window_ns','cycles_per_operation']} for w in ww]
    if mode!='idle':q.update(energy_pJ=statistics.mean(w['gross_pJ_per_operation'] for w in ww),energy_std_pJ=statistics.pstdev(w['gross_pJ_per_operation'] for w in ww),cycles_per_operation=ww[0]['cycles_per_operation'])
    row['profiles'][mode]=q
   rows.append(row)
 assert len(rows)==2
 bfpath=R/'architecture_tlm/bf16_ppa_20261028/results/FINAL_SUMMARY.json';bf=json.loads(bfpath.read_text());b=next(x for x in bf['PPA'] if x['case']['name']=='dot64_4')
 reference=dict(path=str(bfpath),sha256=sha(bfpath),matched_BF16_energy_pJ=b['profiles']['int8']['energy_pJ'],matched_BF16_power_W=b['profiles']['int8']['total_W'],area_55eq_um2=b['area_55eq_um2'],interval_ns=300,quality='Same48 synthetic input frames; INT8 result /128 equals exact BF16/FP32 result. External output-format conversion omitted on both sides.')
 for x in rows:
  x['ratio_BF16_to_INT8']=dict(energy=reference['matched_BF16_energy_pJ']/x['profiles']['matched']['energy_pJ'],area=reference['area_55eq_um2']/x['area_55eq_um2'],interval=300/(x['profiles']['matched']['cycles_per_operation']*10))
 current_functions=[f for f in functions if f['directory'].startswith('functional_38445879_')];assert len(current_functions)==2 and all(f['status']=='pass' and len(f['functional'])==3 for f in current_functions)
 result=dict(date='2026-10-28',source_base='6435de8854d8ddb93375e03085ed1eea9c3f9002',execution_source_manifest_sha256=sha(P/'EXECUTION_MANIFEST.json'),PVT='SS1.08V125C',clock_MHz=100,area_multiplier=.81,source_packages=packages,report_archives=reports,transfer_files_verified=len(transfers),functional=current_functions,functional_history=functions,failures_preserved=failures,PPA=sorted(rows,key=lambda x:-x['case']['AW']),BF16_reference=reference,power_windows=18,boundary='N64 one-output compute core: four INT8 products with product pipeline, balanced integer reduction, output-stationary AW32/AW22 sum and control. Async control reset with4.5..5.5ns release contract; synchronous sum reset; product flops valid-masked and not reset. No input/weight memory, output conversion, RNG, real broadcast, ICG/CTS/SDF/SPEF. Synthetic inputs; no model/PPL or silicon signoff.')
 save(P/'results/FINAL_SUMMARY.json',result);save(HERE/'TRANSFER_VERIFICATION.json',dict(files=transfers,remote_source_sha_verified=True,all_report_members_verified=True))
 print('VERIFIED',len(packages),'execution packages',len(reports),'report archives',len(transfers),'transfers')
 for x in result['PPA']:print(x['case']['name'],x['area_55eq_um2'],x['profiles']['matched']['energy_pJ'],x['normal_latency_cycles'],x['profiles']['matched']['cycles_per_operation'],x['setup_slack_ns'],x['hold_slack_ns'],x['review_flags'])
if __name__=='__main__':main()
