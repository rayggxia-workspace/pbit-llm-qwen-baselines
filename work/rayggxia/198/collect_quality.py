"""Fetch only this task's small JSON/log evidence; verify bytes before summarizing."""
import base64,gzip,hashlib,json,pathlib,subprocess,sys
R=pathlib.Path(__file__).resolve().parents[3];W=pathlib.Path(__file__).resolve().parent
source=json.loads((W/'QUALITY_SOURCE.json').read_bytes());sha=sys.argv[1] if len(sys.argv)>1 else source['commit'][:12]
ssh=['C:/Windows/System32/OpenSSH/ssh.exe','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai']
script='''import pathlib,json,hashlib,base64,gzip,sys,subprocess
root=pathlib.Path('/home/Hongjie_Zeng/projects/attention-sparq-ising-issue198-20261028')
out={}
for path in sorted((root/'results'/SHA).rglob('*')):
 if path.is_file() and path.suffix in ('.json','.sha256'):
  b=path.read_bytes();out[str(path.relative_to(root))]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'data':base64.b64encode(b).decode()}
for path in sorted((root/'logs').glob(SHA+'*')):
 b=path.read_bytes();out[str(path.relative_to(root))]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'data':base64.b64encode(b).decode()}
sys.stdout.buffer.write(gzip.compress(json.dumps(out).encode()))
'''.replace('SHA',repr(sha))
raw=subprocess.check_output(ssh+['bash -lc "python3 -"'],input=script.encode(),timeout=60)
out=json.loads(gzip.decompress(raw));archive=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/project_archives/attention_compare_issue198_20261027/quality')/sha
index={}
for rel,item in out.items():
 data=base64.b64decode(item.pop('data'));assert hashlib.sha256(data).hexdigest()==item['sha256']
 path=archive/rel;path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists() and path.read_bytes()!=data:
  assert rel.startswith('logs/'),'immutable result changed'
  old=path.read_bytes();oldpath=path.with_name(path.name+'.'+hashlib.sha256(old).hexdigest()[:12]);oldpath.write_bytes(old)
 path.write_bytes(data);index[rel]=item
summary={}
for path in (archive/'results'/sha).rglob('*.json'):
 value=json.loads(path.read_bytes());side=path.with_suffix('.json.sha256')
 if side.exists():assert hashlib.sha256(path.read_bytes()).hexdigest()==side.read_text().strip()
 if 'perplexity' in value:
  summary[str(path.relative_to(archive/'results'/sha))]={k:value[k] for k in ['perplexity','scored_tokens','seconds']}
record={'source_prefix':sha,'archive':str(archive),'files':index,'summary':summary}
(W/f'QUALITY_COLLECTION_{sha}.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(summary,indent=2))
