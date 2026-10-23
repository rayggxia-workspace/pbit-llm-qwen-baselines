from pathlib import Path
import json,subprocess
from remote_probe import SSH,TARGET
ROOT=Path(__file__).resolve().parent
job='2783'
assert json.loads((ROOT/'FFN_SUBMISSION.json').read_text())['job_id']==job
p=subprocess.run(SSH+['/opt/slurm/21.08.8/bin/scontrol show job '+job],capture_output=True,text=True,timeout=40)
p.check_returncode();state=p.stdout
assert 'UserId=Weican_Chen(1002)' in state and 'Command='+TARGET+'/run_ffn.sbatch' in state
intent=dict(job_id=job,reason='user explicitly requested stopping at current progress and archiving completed and incomplete work; own Issue123 job only',before=state)
(ROOT/'STOP_2783_INTENT.json').write_text(json.dumps(intent,indent=2)+'\n',encoding='utf-8')
if 'JobState=RUNNING' in state or 'JobState=PENDING' in state:
    r=subprocess.run(SSH+['/opt/slurm/21.08.8/bin/scancel '+job],capture_output=True,text=True,timeout=40)
    (ROOT/'STOP_2783_RECEIPT.json').write_text(json.dumps(dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr),indent=2)+'\n',encoding='utf-8')
    r.check_returncode();print('cancel requested for verified own job',job)
else:print('already terminal; no cancellation',state)
