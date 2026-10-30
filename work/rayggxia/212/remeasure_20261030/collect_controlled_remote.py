"""Read only; transfer small sealed artifacts exactly, index large traces."""
import base64,hashlib,json,subprocess
from pathlib import Path
root=Path('/home/Hongjie_Zeng/projects/pbit-qwen3-gpu-decode-energy-20261029-issue212')
folder=root/'results/controlled_formal_58d36200ed5fd4f8_alloc2'
completed=folder/'COMPLETED.json'
if not completed.exists():
    log=root/'logs/i212_formal_58d362-3440.log'
    print(json.dumps(dict(status='not_completed',log_tail=log.read_text()[-2500:],
        queue=subprocess.check_output(['/opt/slurm/21.08.8/bin/squeue','-u','Hongjie_Zeng','-h','-o','%.12i %.10T %.10M %R'],text=True))))
else:
    end=json.loads(completed.read_text());assert end['status']=='completed'
    manifest_path=folder/'ARTIFACT_MANIFEST.json'
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest()==end['manifest_sha256']
    manifest=json.loads(manifest_path.read_text());artifacts=[]
    for name,item in manifest.items():
        p=(folder/name).resolve();assert folder.resolve() in p.parents
        raw=p.read_bytes();assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256'],name
        if p.suffix=='.json' and p.name!='TRACE.json' and len(raw)<400000:
            artifacts.append(dict(path=name,sha256=item['sha256'],bytes=len(raw),base64=base64.b64encode(raw).decode()))
    for p in [completed,manifest_path]:
        raw=p.read_bytes();artifacts.append(dict(path=p.name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),base64=base64.b64encode(raw).decode()))
    print(json.dumps(dict(status='completed',artifacts=artifacts,remote_result_directory=str(folder),large_trace_index=manifest)))
