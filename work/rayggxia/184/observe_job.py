"""Read scheduler and small per-case evidence for the one normal-readout job."""
from pathlib import Path
import argparse,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[5]
WORK=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
if a.out.exists():raise FileExistsError('Observation is immutable')
remote=r'''/usr/bin/python3 -B - <<'PY'
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess
root=Path('/public3/home/t6s011227/analog_pbit_20261016/normal_readout_v1')
r=root/'results/38387635'
obs=dict(job=38387635,observed_utc=datetime.utcnow().isoformat()+'Z',
 sacct=subprocess.check_output(['sacct','-j','38387635','--format=JobID,State,Elapsed,AllocCPUS,TotalCPU,ExitCode','-P']).decode(),
 remote_results=str(r),cases=[])
for name in ['metadata.json','candidate_selection.json','frozen_reference.json','numerical_screen.json','pdk_comparison.json']:
 if (r/name).exists():
  value=json.loads((r/name).read_text())
  obs[name]=dict(sha256=hashlib.sha256((r/name).read_bytes()).hexdigest(),content=value)
if (r/'spectre_version.txt').exists():obs['spectre_version']=(r/'spectre_version.txt').read_text()
if (r/'summary.json').exists():
 s=json.loads((r/'summary.json').read_text());obs['summary_status']=s['status'];obs['details']=s['details']
 for c in s['cases']:
  row=dict(case=c['case'],status=c['status'],error=c.get('check_error'),elapsed_s=c.get('simulator_elapsed_s'))
  if (r/c['case']/'bias_diagnostics.json').exists():row['bias']=json.loads((r/c['case']/'bias_diagnostics.json').read_text())['devices']
  if c['setting']['kind']=='step' and c.get('metrics'):row['step']=c['metrics']
  if c['setting']['kind']=='noise' and c.get('metrics'):
   row['noise']=dict(P1=c['metrics']['p1'],MID=c['metrics']['midrail_fraction'],actual_samples=c['metrics']['actual_sample_bits'])
  obs['cases'].append(row)
obs['active_case_folders']=[p.name for p in r.iterdir() if p.is_dir() and (p/'command.json').exists() and not (p/'status.json').exists()] if r.exists() else []
for kind in ['out','err']:
 path=root/('logs/study-38387635.'+kind)
 if path.exists():obs['log_'+kind+'_tail']='\n'.join(path.read_text(errors='replace').splitlines()[-15:])
print(json.dumps(obs,indent=2))
PY'''
proc=subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'local_tools/paracloud_client/client.py'),'exec',remote,'--timeout','40'],capture_output=True,timeout=85)
if proc.returncode:raise RuntimeError('Read-only observation failed; no successful receipt written: '+proc.stderr.decode('utf-8','replace'))
obs=json.loads(proc.stdout)
a.out.write_text(json.dumps(obs,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(obs['sacct']);print('SUMMARY',obs.get('summary_status'),'CASES',len(obs['cases']))
for c in obs['cases']:
 if c.get('noise') or c['status']=='FAILED_CHECK':print(json.dumps(c,ensure_ascii=False))
print('ACTIVE',obs['active_case_folders'])
print('SELECTED',json.dumps(obs.get('details',{}).get('selected'),ensure_ascii=False));print('ERR',obs.get('log_err_tail',''))
