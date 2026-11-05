"""Verify parallel64 originals and summarize same-concurrency/cadence metrics."""
from pathlib import Path
import hashlib,json,math,statistics,tarfile,zipfile
HERE=Path(__file__).resolve().parent;R=HERE.parents[3];W=R.parents[1];P=R/'architecture_tlm/int8_parallel64_20261028';A=W/'project_archives/matrix204_parallel64_20261029'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 remote=json.loads((A/'REMOTE_ATTEST.json').read_text());packages=[];reports=[];transfers=[];rows=[];functions=[];failures=[]
 arcs=sorted(A.glob('par64_204_v*.zip'))
 for p in arcs:
  k=next(k for k in remote if k.endswith('/'+p.name));assert remote[k]==dict(sha256=sha(p),bytes=p.stat().st_size)
  with zipfile.ZipFile(p) as z:
   raw=z.read(p.stem+'/EXECUTION_MANIFEST.json');m=json.loads(raw)
   for n,h in m['files'].items():assert hashlib.sha256(z.read(p.stem+'/'+n)).hexdigest()==h,n
   if p==arcs[-1]:
    for n,h in m['files'].items():assert sha(P/n)==h,n
  packages.append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size,manifest_sha256=hashlib.sha256(raw).hexdigest(),members_verified=len(m['files'])))
 for tf in A.glob('par64_204_v*_TRANSFER.json'):
  for x in json.loads(tf.read_text()):
   p=Path(x['path']);assert sha(p)==x['sha256'] and remote[x['remote']]==dict(sha256=sha(p),bytes=p.stat().st_size)
   transfers.append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size,remote=x['remote']))
 for p in sorted(A.glob('*/reports.tar.gz')):
  with tarfile.open(p) as t:
   manifest=json.load(t.extractfile('RETURN_MANIFEST.json'))['files']
   for n,h in manifest.items():assert hashlib.sha256(t.extractfile(n).read()).hexdigest()==h,n
   r=json.load(t.extractfile('RESULT.json'));assert sha(p.parent/'RESULT.json')==manifest['RESULT.json']
   reports.append(dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size,members_verified=len(manifest),result_member_sha256=manifest['RESULT.json']))
   if r['stage']=='functional':functions.append(dict(directory=p.parent.name,case=r['case'],status=r['status'],functional=r['functional']));continue
   if r['status']!='calculated':failures.append(dict(directory=p.parent.name,case=r['case'],error=r.get('error')));continue
   assert len(r['windows'])==12 and all(w['all_mapped_pin_activity_verified'] and w['leaf_coverage_percent']==100 for w in r['windows'])
   gate=[]
   for seed in [17,503,1009]:
    log=t.extractfile('gate_%d/simulation.log'%seed).read().decode();assert 'FUNCTION_PASS transactions=164' in log
    rr=json.load(t.extractfile('gate_%d/REPLAY.json'%seed));gate.append(dict(seed=seed,transactions=164,VCD_sha256=rr['VCD_sha256']))
   if p.parent.name.startswith('ppa_38447584_'):
    failures.append(dict(directory=p.parent.name,case=r['case'],stage='power_calculated_original_hold_violation',windows=len(r['windows']),raw_area_um2=r['raw_area_um2'],area_55eq_um2=r['area_55eq_um2'],setup_slack_ns=min(w['setup_slack_ns'] for w in r['windows']),hold_slack_ns=min(w['hold_slack_ns'] for w in r['windows']),archive=str(p)));continue
   w0=r['windows'][0]
   row=dict(case=r['case'],raw_area_um2=r['raw_area_um2'],area_55eq_um2=r['area_55eq_um2'],mapped_sha256=r['mapped_sha256'],archive=str(p),setup_slack_ns=min(w['setup_slack_ns'] for w in r['windows']),hold_slack_ns=min(w['hold_slack_ns'] for w in r['windows']),review_flags=sorted({f for w in r['windows'] for f in w['review_flags']}),all_mapped_pin_activity_verified=True,gate_replays=gate,latency_cycles=w0['latency_cycles'],initiation_interval_cycles=w0['initiation_interval_cycles'],area_groups={k:dict(cells=g['cells'],raw_area_um2=g['area_um2'],area_55eq_um2=.81*g['area_um2']) for k,g in w0['groups'].items()},profiles={})
   assert math.isclose(row['area_55eq_um2'],.81*row['raw_area_um2'],rel_tol=1e-12)
   for mode in ['peak','paced','fullrange','idle']:
    ww=[w for w in r['windows'] if w['mode']==mode];assert len(ww)==3
    q={k:statistics.mean(w[k] for w in ww) for k in ['total_W','internal_W','switching_W','leakage_W','window_ns','operations']}
    q['seed_results']=[{k:w[k] for k in ['seed','total_W','gross_pJ_per_operation','operations','window_ns','cycles_per_operation']} for w in ww]
    if mode!='idle':q.update(energy_pJ=statistics.mean(w['gross_pJ_per_operation'] for w in ww),energy_std_pJ=statistics.pstdev(w['gross_pJ_per_operation'] for w in ww),cycles_per_operation=ww[0]['cycles_per_operation'])
    row['profiles'][mode]=q
   if 'REUSED_SYNTH.json' in t.getnames():row['reuse_proof']=json.load(t.extractfile('REUSED_SYNTH.json'))
   rows.append(row)
 assert len(rows)==2
 oldpath=R/'architecture_tlm/module_energy_20261028/results/FINAL_SUMMARY.json';old=json.loads(oldpath.read_text());sc=next(x for x in old['PPA'] if x['case']['name']=='bank54')
 reference=dict(path=str(oldpath),sha256=sha(oldpath),source_commit='080729c314e2e0e62efada3e32d4c27c7eac4bb5',case=sc['case'],area_55eq_um2=sc['area_55eq_um2'],raw_area_um2=sc['raw_area_um2'],power_W=sc['profiles']['replay']['total_W'],energy_pJ=sc['profiles']['replay']['energy_pJ_per_operation'],interval_ns=350,operands='Same original X/W frames; absW clipped127 and row f%8, per INPUT_REFERENCE. SC OR4/T32/drop-plane approximate, INT8 exact; no model-quality equivalence claim')
 current_functions=[f for f in functions if f['directory'].startswith('functional_38447776_')];assert len(current_functions)==2
 result=dict(date='2026-10-29',source_base='158e489816bde1547d07cd3f9e377b809055f63f',execution_source_manifest_sha256=sha(P/'EXECUTION_MANIFEST.json'),PVT='SS1.08V125C',clock_MHz=100,area_multiplier=.81,source_packages=packages,report_archives=reports,transfer_files_verified=len(transfers),functional=current_functions,functional_history=functions,failures_preserved=failures,PPA=sorted(rows,key=lambda x:-x['case']['AW']),SC_reference=reference,power_windows=24,total_PT_windows_including_initial_hold_violation=48,boundary='Same64 input lanes/M1,64 full signed8 multipliers and balanced reduction; registered22/32 output. No temporal multiplier sharing, external weight/input storage and sign/probability/RNG/format/physical broadcast/ICG/CTS/SDF/SPEF excluded. Paced clock remains free-running; do not call it optimal gated digital energy.')
 save(P/'results/FINAL_SUMMARY.json',result);save(HERE/'TRANSFER_VERIFICATION.json',dict(files=transfers,remote_source_sha_verified=True,all_report_members_verified=True))
 print('VERIFIED',len(packages),'packages',len(reports),'reports',len(transfers),'transfers')
 for x in result['PPA']:print(x['case']['name'],x['area_55eq_um2'],{k:(v['total_W'],v.get('energy_pJ')) for k,v in x['profiles'].items()},x['setup_slack_ns'],x['hold_slack_ns'],x['review_flags'],x['area_groups'])
if __name__=='__main__':main()
