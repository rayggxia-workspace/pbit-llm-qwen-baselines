"""Freeze/submit CPU-only adapter snapshot; never edit an executing snapshot."""
from pathlib import Path
import base64
import datetime
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent


def main():
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    parent='/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/compass_2e015fd2'
    run=parent+'/run_'+head[:8]
    items={name:'architecture_tlm/unified_v6/probes/llmcompass/'+name for name in ['qwen_decode.py','test_contract.py']}
    items.update({'model_qwen3_4b.json':'architecture_tlm/unified_v6/configs/model_qwen3_4b.json','run.sh':'work/jieruiz/186/compass_run.sh'})
    payload={};meta={}
    for name,path in items.items():
        data=(ROOT/path).read_bytes()
        assert data==subprocess.check_output(['git','show',head+':'+path],cwd=ROOT)
        payload[name]=base64.b64encode(data).decode()
        meta[name]=dict(repository_path=path,sha256=hashlib.sha256(data).hexdigest())
    manifest=dict(commit=head,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=meta,
                  upstream_commit='2e015fd2ee750e6cad8d7152df52551e5b41ef20')
    script="set -eu\npython3 - <<'PY'\nfrom pathlib import Path\nimport json,base64\np=Path("+repr(run)+")\np.mkdir(exist_ok=False)\n(p/'source').mkdir()\npayload=json.loads("+repr(json.dumps(payload))+ ")\nfor name,data in payload.items(): (p/'source'/name).write_bytes(base64.b64decode(data))\n(p/'SOURCE.json').write_text("+repr(json.dumps(manifest,indent=2)+'\n')+")\nPY\ncd "+run+"\nsbatch --parsable --output=compass-%A_%a.out --error=compass-%A_%a.err source/run.sh "+run+"\n"
    r=subprocess.run(['ssh','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai','bash -l -s'],input=script.encode(),capture_output=True,timeout=40)
    print(r.stdout.decode(),r.stderr.decode());r.check_returncode()
    record=dict(remote=run,source=manifest,receipt=r.stdout.decode(),job_id=r.stdout.decode().strip().split(';')[0])
    (OUT/'COMPASS_SUBMISSION.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
