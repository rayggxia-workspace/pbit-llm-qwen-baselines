"""Collect immutable completed LLMCompass CPU results with byte SHA checks."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
META = Path(__file__).resolve().parent
DEST = ROOT/'architecture_tlm/unified_v6/results/llmcompass_20261025/final'


def main():
    sub = json.loads((META/'COMPASS_SUBMISSION.json').read_text(encoding='utf-8'))
    remote = sub['remote']; parent = str(Path(remote).parent).replace('\\','/')
    code = r'''
import base64,hashlib,json
from pathlib import Path
p=Path(REMOTE);root=p.parent
files={};states={}
def add(path,name):
 b=path.read_bytes()
 files[name]={'sha256':hashlib.sha256(b).hexdigest(),'size':len(b),'remote':str(path),'base64':base64.b64encode(b).decode()}
up=json.loads((root/'UPSTREAM.json').read_text())
changed=[name for name,h in up['files'].items() if hashlib.sha256((root/'upstream'/name).read_bytes()).hexdigest()!=h]
assert not changed,changed
for name in ['UPSTREAM.json','ENVIRONMENT.json']:add(root/name,name)
add(p/'SOURCE.json','SOURCE.json')
for i,case in enumerate(['a100_native','small_native_hbm256','small_native_hbm186','small_fabric32','small_native_ddr']):
 d=p/'results'/case
 if (d/'MANIFEST.json').is_file():
  m=json.loads((d/'MANIFEST.json').read_text());assert m['status']=='completed'
  for name,h in m['files'].items():assert hashlib.sha256((d/name).read_bytes()).hexdigest()==h
  states[case]='completed'
  for name in ['MANIFEST.json','RESULT.json','EXECUTION.json']:add(d/name,case+'/'+name)
 elif (d/'FAILURE.json').is_file():states[case]='failed';add(d/'FAILURE.json',case+'/FAILURE.json')
 else:states[case]='pending'
 for prefix in ['tests-'+str(i)+'.out','compass-'+JOB+'_'+str(i)+'.out','compass-'+JOB+'_'+str(i)+'.err']:
  f=p/prefix
  if f.is_file() and f.stat().st_size<150000:add(f,'logs/'+prefix)
print(json.dumps({'files':files,'states':states,'upstream_original_files_unchanged':not changed}))
'''.replace('REMOTE',repr(remote)).replace('JOB',repr(sub.get('job_id','3047')))
    proc = subprocess.run(['ssh','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes',
                           'lab-server-ai','python3 -'],input=code.encode(),capture_output=True,timeout=50)
    if proc.returncode:
        print(proc.stderr.decode());proc.check_returncode()
    payload=json.loads(proc.stdout)
    DEST.mkdir(parents=True,exist_ok=True)
    index={}
    for name,item in payload['files'].items():
        data=base64.b64decode(item.pop('base64'));assert hashlib.sha256(data).hexdigest()==item['sha256']
        path=DEST/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);index[name]=item
    if all(s=='completed' for s in payload['states'].values()):
        for case in payload['states']:
            ex=json.loads((DEST/case/'EXECUTION.json').read_text());rs=json.loads((DEST/case/'RESULT.json').read_text())
            assert ex['adapter_sha256']==sub['source']['files']['qwen_decode.py']['sha256']
            assert ex['model_config_sha256']==sub['source']['files']['model_qwen3_4b.json']['sha256']
            assert rs['inventory']['total_mac']==4626251776 and rs['model']['shape']['num_hidden_layers']==36
            assert rs['context_including_current']==2048 and rs['batch']==1
        status='completed'
    else:status='incomplete'
    report=dict(status=status,states=payload['states'],source_commit=sub['source']['commit'],remote=remote,
                upstream_original_files_unchanged=payload['upstream_original_files_unchanged'],files=index)
    (DEST/'COLLECTION.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2))
    if status!='completed':sys.exit(2)


if __name__=='__main__':main()
