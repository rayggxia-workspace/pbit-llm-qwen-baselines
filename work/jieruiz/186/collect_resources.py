"""Verify remote original hashes; retain compact derived timing records only."""
import base64,gzip,hashlib,json,pathlib,subprocess
R=pathlib.Path(__file__).resolve().parents[3];W=R/'work/jieruiz/186'
s=json.loads((W/'RESOURCE_SUBMISSION.json').read_text())
script=r"""import base64,gzip,hashlib,json,pathlib,sys
r=pathlib.Path(REMOTE);files={};derived={};done=[];failed=[];pending=[]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def keep(p):files[p.relative_to(r).as_posix()]=base64.b64encode(p.read_bytes()).decode()
gate=json.loads((r/'gate/GATE.json').read_text());assert gate['status']=='completed'
for row in gate['rows']:
 p=r/'gate'/(row['profile']+'_'+str(int(row['prefill'])))/'RESULT.json'
 assert sha(p)==row['sha256']
keep(r/'gate/GATE.json')
for i in range(16):
 p=r/'results'/('case_'+str(i));mf=p/'MANIFEST.json'
 if (p/'FAILURE.json').exists():failed.append(dict(index=i,failure=json.loads((p/'FAILURE.json').read_text())));keep(p/'FAILURE.json');continue
 if not mf.exists():pending.append(i);continue
 m=json.loads(mf.read_text());assert m['status']=='completed'
 for name,meta in m['files'].items():assert sha(p/name)==meta['sha256'],str(p/name)
 raw=json.loads((p/'RESULT.json').read_text())
 layers=sorted({x['layer'] for x in raw['phases'] if x.get('layer') is not None});assert layers==list(range(36))
 d=json.loads((p/'RESULT_SUMMARY.json').read_text());pipe=d['tile_pipeline']['digital']
 assert not(pipe['pending'] or pipe['active'] or pipe['staged'])
 assert pipe['counts']['issued']==pipe['counts']['filled']==pipe['counts']['retired']
 for owner in ('digital','sc'):d['tile_pipeline'][owner].pop('records',None)
 d['resource_busy_ns']={k:v for k,v in d['resource_busy_ns'].items() if not k.startswith('sram_bank:')}
 # Original records remain at the immutable remote location. Avoid duplicate traces.
 d['evidence']=dict(remote_result=str(p/'RESULT.json'),raw_sha256=sha(p/'RESULT.json'),remote_summary_sha256=sha(p/'RESULT_SUMMARY.json'),manifest_sha256=sha(mf),layers=layers,derived=True,omitted='bounded ticket records and per-bank busy list only')
 derived['results/case_'+str(i)+'/COMPACT.json']=d
 for name in ['MANIFEST.json','EXECUTION.json']:keep(p/name)
 done.append(dict(index=i,case=m['case'],manifest_sha256=sha(mf)))
for rel in ['gate.sbatch','run.sbatch']:
 keep(r/rel)
for p in (r/'logs').glob('*.out'):
 if p.stat().st_size<100000 and (p.name.startswith('gate') or len(done)==16):keep(p)
sys.stdout.buffer.write(gzip.compress(json.dumps(dict(remote=str(r),completed=done,failed=failed,pending=pending,files=files,derived=derived)).encode()))
""".replace('REMOTE',repr(s['remote']))
b=subprocess.check_output(['ssh','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai','/usr/bin/python3 -'],input=script.encode())
d=json.loads(gzip.decompress(b));out=R/'architecture_tlm/unified_v6/results/resources_20261025';out.mkdir(parents=True,exist_ok=True)
def save(rel,data):
 p=pathlib.PurePosixPath(rel);assert not p.is_absolute() and '..' not in p.parts
 dest=out.joinpath(*p.parts);dest.parent.mkdir(parents=True,exist_ok=True)
 if dest.exists():assert dest.read_bytes()==data,'immutable output differs '+rel
 else:dest.write_bytes(data)
for rel,enc in d.pop('files').items():save(rel,base64.b64decode(enc))
for rel,v in d.pop('derived').items():save(rel,(json.dumps(v,indent=2,ensure_ascii=False)+'\n').encode())
(W/'RESOURCE_COLLECTION.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(completed=len(d['completed']),pending=d['pending'],failed=d['failed'])))
