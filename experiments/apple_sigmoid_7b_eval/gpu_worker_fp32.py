from pathlib import Path
import json,os,subprocess,time,hashlib
P=Path('/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019');S=P/'source/run-v6';E=P/'env-eval-v4/bin/python'
assert os.environ.get('SLURM_JOB_ID') and os.environ.get('CUDA_VISIBLE_DEVICES','')!=''
os.environ.update(HF_HUB_OFFLINE='1',HF_DATASETS_OFFLINE='1',HF_HOME=str(P/'cache/huggingface'),PYTHONDONTWRITEBYTECODE='1')
status={'state':'RUNNING','job_id':os.environ['SLURM_JOB_ID'],'node':os.uname().nodename,'phases':[],'source_snapshot':'run-v6','started_at':time.time()}
def save():
 (P/'reports/gpu_fp32_status.json').write_text(json.dumps(status,indent=2)+'\n')
def run(label,args):
 status['active_phase']=label;save();print('PHASE',label,flush=True)
 subprocess.run(list(map(str,args)),check=True)
 status['phases'].append({'phase':label,'completed_at':time.time()});save()
try:
 import torch
 assert torch.cuda.device_count()==1,torch.cuda.device_count()
 status['gpu']=torch.cuda.get_device_name(0);status['torch']=torch.__version__;save()
 for kind in ['softmax','sigmoid']:
  cpu=json.loads((P/'reports'/f'{kind}-cpu-original-fp32.json').read_text());assert cpu['passed']
 assert json.loads((P/'reports/task_tokenization_audit.json').read_text())['passed']
 for kind in ['softmax','sigmoid']:
  # Explicitly disable TF32 before executing the BF16/PV-FP32 port preflight.
  code='import sys,torch; torch.backends.cuda.matmul.allow_tf32=False; sys.path.insert(0,"'+str(S)+'"); import preflight; preflight.main()'
  run(kind+'-gpu-parity',[E,'-B','-c',code,'--converted',P/'converted-original-fp32'/kind,'--kind',kind,'--reference',P/'reports'/f'{kind}-native-original-fp32.npz','--output',P/'reports'/f'{kind}-gpu-original-fp32.json','--device','cuda','--dtype','float32'])
 for phase in ['smoke','ppl','tasks']:
  for kind in ['softmax','sigmoid']:
   run(kind+'-'+phase,[E,'-B',S/'evaluate.py','--root',P,'--kind',kind,'--phase',phase,'--dtype','float32','--converted-root',P/'converted-original-fp32'])
 rows={}
 for kind in ['softmax','sigmoid']:
  pp=json.loads((P/'reports/float32'/kind/'ppl.json').read_text());acc=json.loads((P/'reports/float32'/kind/'six_task_summary.json').read_text());assert pp['complete'] and acc['complete'];rows[kind]={'ppl':pp,'tasks':acc}
 assert rows['softmax']['ppl']['token_ids_sha256']==rows['sigmoid']['ppl']['token_ids_sha256']
 (P/'reports/paired_fp32_quality_summary.json').write_text(json.dumps(rows,indent=2)+'\n')
 status.update(state='COMPLETED',completed=True,finished_at=time.time());save()
except BaseException as e:
 status.update(state='FAILED',error=repr(e),finished_at=time.time());save();raise
