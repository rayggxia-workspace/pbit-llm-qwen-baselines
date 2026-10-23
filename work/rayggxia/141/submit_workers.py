"""Submit two dependent experiment arrays after a verified preparation."""
import hashlib,json,os,subprocess
from pathlib import Path
root=Path('/home/Hongjie_Zeng/projects/pbit-qwen-sampler-ppl-20261023-issue141')
sha='7a286ec140de6846006c96456275377fd22b4943'
out=root/'outputs'/sha
ready=json.loads((out/'READY.json').read_text())
assert ready['status']=='passed' and ready['code_commit']==sha
for path in [out/'READY.json',out/'PLAN.json',out/'kernel_validation.json',out/'bf16_vectorized_full.json']:
    assert hashlib.sha256(path.read_bytes()).hexdigest()==path.with_suffix(path.suffix+'.sha256').read_text().strip()
receipt_path=root/'workers-submission.json'
if receipt_path.exists():raise FileExistsError('workers already submitted; inspect receipt before retry')
snapshot=root/'snapshots'/sha
env=dict(os.environ,PBIT_PROJECT_ROOT=str(root),PBIT_SNAPSHOT=str(snapshot),PBIT_CODE_COMMIT=sha,PBIT_ACTION='worker')
receipt=dict(code_commit=sha,prepare_job='2803',phase_status='submitting',jobs=[])
receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
for phase in ('suffix','full'):
    cmd=['/opt/slurm/21.08.8/bin/sbatch','--parsable','--array=0-15%2','--export=ALL',
        '--output='+str(root/'logs'/(phase+'-%A_%a.out'))]
    if phase=='full':cmd+=['--dependency=afterok:'+receipt['jobs'][0]['job_id']]
    cmd+=[str(snapshot/'experiments/qwen_parallel_sampler_ppl_20261023/run.sbatch')]
    r=subprocess.run(cmd,env=dict(env,PBIT_PHASE=phase),text=True,capture_output=True,check=True)
    receipt['jobs'].append(dict(phase=phase,job_id=r.stdout.strip(),command=cmd))
    receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
receipt['phase_status']='submitted'
receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
