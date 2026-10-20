"""Read own immutable output directory through SSH; never submits jobs or overwrites remote data."""
import argparse
import json
from pathlib import Path, PurePosixPath
import subprocess


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--ssh-config',required=True);p.add_argument('--host',default='lab-server-ai')
    p.add_argument('--remote-root',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();root=PurePosixPath(a.remote_root)
    allowed=PurePosixPath('/home/Hongjie_Zeng/projects/pbit-qwen-joint-ffn-attention-20261019-issue50/outputs')
    if root.parent!=allowed or len(root.name)!=40 or any(c not in '0123456789abcdef' for c in root.name):
        raise ValueError('Only own frozen Issue50 output roots are admitted')
    script=f'''import hashlib,json,pathlib
o=pathlib.Path({str(root)!r}).resolve(strict=True);rows=[];files=[]
for f in sorted(o.rglob('*')):
 if not f.is_file():continue
 blob=f.read_bytes();rel=str(f.relative_to(o));files.append(dict(path=rel,bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest()))
 if f.suffix!='.json':continue
 d=json.loads(blob)
 if rel.startswith(('pilot/','suffix/','fallback/','full/','memory/')):
  stat=d.get('sampling_stats');d['sampling_summary']=stat.get('totals') if stat else None
  d['attention_last_sampler_stats']=[v.get('last_sampler_stats') for v in stat.get('layers',{{}}).values()] if stat else None
  d.pop('ffn_stats',None);d.pop('sampling_stats',None)
 rows.append(dict(path=rel,data=d))
print(json.dumps(dict(files=files,rows=rows)))
'''
    result=subprocess.run(['ssh','-F',a.ssh_config,a.host,'python3 -'],input=script.encode('utf-8'),
        capture_output=True,timeout=120)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8','replace'))
    value=json.loads(result.stdout)
    Path(a.output).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(files=len(value['files']),json_records=len(value['rows']),remote_root=str(root))))
if __name__=='__main__':main()
