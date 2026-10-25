"""Read one sampled-channel job; no mutation or automatic retry/submission."""
from pathlib import Path
import argparse,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[5]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
if a.out.exists():raise FileExistsError('Immutable observation already exists')
remote=r'''/usr/bin/python3 -B - <<'PY'
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess
root=Path('/public3/home/t6s011227/analog_pbit_20261016/sampled_readout_v1');r=root/'results/38398237'
x=dict(job=38398237,observed_utc=datetime.utcnow().isoformat()+'Z',remote_results=str(r),cases=[],sacct=subprocess.check_output(['sacct','-j','38398237','--format=JobID,State,Elapsed,AllocCPUS,TotalCPU,ExitCode','-P']).decode())
for name in ['metadata.json','pdk_comparison.json','numerical_screen.json','reference_lock.json','remaining_cost_estimate.json']:
 if (r/name).exists():x[name]=json.loads((r/name).read_text())
if (r/'summary.json').exists():
 s=json.loads((r/'summary.json').read_text());x['summary_status']=s['status'];x['details']=s['details']
 for row in s['cases']:
  d=dict(case=row['case'],kind=row['kind'],status=row['status'],elapsed_s=row.get('simulator_elapsed_s'),error=row.get('check_error'))
  if row.get('metrics'):
   m=row['metrics'];keys=['actual_samples','P1','invalid_Q','Q_MID','capture_MID','hold_invalid_saved_points','hold_changed_saved_points','read_invalid','wrong_known_stable_inputs','required_gate']
   d['metrics']={k:m[k] for k in keys if k in m}
   if 'critical_cycle' in m:d['critical_cycle']=m['critical_cycle']
  x['cases'].append(d)
x['active_cases']=[p.name for p in r.iterdir() if p.is_dir() and (p/'command.json').exists() and not (p/'status.json').exists()] if r.exists() else []
for suffix in ['out','err']:
 p=root/('logs/study-38398237.'+suffix)
 if p.exists():x['log_'+suffix+'_tail']='\n'.join(p.read_text(errors='replace').splitlines()[-15:])
print(json.dumps(x,indent=2))
PY'''
r=subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'local_tools/paracloud_client/client.py'),'exec',remote,'--timeout','40'],capture_output=True,timeout=85)
if r.returncode:raise RuntimeError('Read failed; no success receipt: '+r.stderr.decode('utf-8','replace'))
x=json.loads(r.stdout);a.out.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(x['sacct']);print('STATUS',x.get('summary_status'),'CASES',len(x['cases']))
for row in x['cases']:print(json.dumps(row,ensure_ascii=False))
print('ACTIVE',x['active_cases']);print('ERROR_LOG',x.get('log_err_tail',''))
