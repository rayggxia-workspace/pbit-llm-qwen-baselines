"""Collect sealed locality cases; verify remote raw SHA before downloading summaries."""
import base64,gzip,hashlib,json,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[3]
W=ROOT/'work/jieruiz/186'
submission=json.loads((W/'PIPELINE_SUBMISSION.json').read_text())
SCRIPT=r'''import pathlib,json,hashlib,gzip,base64,sys
root=pathlib.Path(REMOTE);files={};done=[];failed=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for folder in sorted((root/'results').glob('case_*')):
 if (folder/'FAILURE.json').exists():failed.append(json.loads((folder/'FAILURE.json').read_text()))
 mf=folder/'MANIFEST.json'
 if not mf.exists():continue
 m=json.loads(mf.read_text());assert m['status']=='completed'
 for name in ['RESULT.json','RESULT_SUMMARY.json','EXECUTION.json']:
  assert sha(folder/name)==m['files'][name]['sha256'],str(folder/name)
 for name in ['RESULT_SUMMARY.json','EXECUTION.json','MANIFEST.json']:
  files[folder.name+'/'+name]=base64.b64encode((folder/name).read_bytes()).decode()
 done.append(dict(index=int(folder.name[5:]),case=m['case'],manifest_sha256=sha(mf)))
sys.stdout.buffer.write(gzip.compress(json.dumps(dict(remote=str(root),completed=done,failed=failed,files=files)).encode()))
'''.replace('REMOTE',repr(submission['remote']))
r=json.loads(gzip.decompress(subprocess.check_output(['C:/Windows/System32/OpenSSH/ssh.exe','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','lab-server-ai','/usr/bin/python3 -'],input=SCRIPT.encode())))
out=ROOT/'architecture_tlm/ffn_local_pipeline_20261025/results'
out.mkdir(parents=True,exist_ok=True)
for rel,data in r.pop('files').items():
 p=pathlib.PurePosixPath(rel)
 assert len(p.parts)==2 and p.parts[0].startswith('case_') and p.parts[1] in ('RESULT_SUMMARY.json','EXECUTION.json','MANIFEST.json')
 dest=out.joinpath(*p.parts);dest.parent.mkdir(exist_ok=True);b=base64.b64decode(data)
 if dest.exists():assert dest.read_bytes()==b,'immutable result changed'
 else:dest.write_bytes(b)
(W/'PIPELINE_COLLECTION.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(completed=len(r['completed']),failed=len(r['failed']),names=[x['case']['name'] for x in r['completed']],failures=r['failed'])))
