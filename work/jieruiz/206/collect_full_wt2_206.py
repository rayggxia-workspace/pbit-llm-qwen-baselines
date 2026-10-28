"""Collect completed immutable seals only; never submit/restart a task."""
import datetime,hashlib,io,json,pathlib,subprocess,tarfile
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/group64-scale-issue206-20261028');W=R/'work/jieruiz/206'
v=json.loads(sorted(W.glob('FULL_WT2_SUBMISSION_*.json'))[-1].read_bytes());dest=R/'qwen3/results/group_shared_20261028'/v['commit'][:12]/'full_wt2'
ssh=['C:/Windows/System32/OpenSSH/ssh.exe','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai']
remote='''import hashlib,io,json,pathlib,sys,tarfile
v=PAYLOAD;base=pathlib.Path(v['expected_results']);files={}
for c in sorted(base.glob('*/complete.json')):
 d=json.loads(c.read_bytes());assert d['status']=='completed'
 for n,h in d['documents'].items():
  p=c.parent/n;assert hashlib.sha256(p.read_bytes()).hexdigest()==h
 for p in c.parent.glob('*.json'):files[str(p.relative_to(base))]=p.read_bytes()
 if c.parent.name=='gate':log=pathlib.Path(v['root'])/'logs'/('full-gate-'+v['commit'][:8]+'-'+v['gate_job']+'.out')
 else:log=pathlib.Path(v['root'])/'logs'/('full-'+v['commit'][:8]+'-'+v['array']+'_'+str(d['task'])+'.out')
 if log.exists():files[c.parent.name+'/slurm.log']=log.read_bytes()
cpu=pathlib.Path(v['root'])/'logs'/('full-cpu-'+v['commit'][:8]+'-'+v['cpu_job']+'.out')
if cpu.exists() and b'Ran 77 tests' in cpu.read_bytes() and b'OK (skipped=10)' in cpu.read_bytes():files['cpu/slurm.log']=cpu.read_bytes()
with tarfile.open(fileobj=sys.stdout.buffer,mode='w:gz') as t:
 for n,b in files.items():
  z=tarfile.TarInfo(n);z.size=len(b);t.addfile(z,io.BytesIO(b))
'''.replace('PAYLOAD',repr(v))
b=subprocess.check_output(ssh+['/usr/bin/python3 -'],input=remote.encode(),timeout=60)
written={}
with tarfile.open(fileobj=io.BytesIO(b),mode='r:gz') as t:
 for m in t.getmembers():
  assert m.isfile() and '..' not in pathlib.PurePosixPath(m.name).parts and not m.name.startswith('/')
  p=dest/m.name;data=t.extractfile(m).read();p.parent.mkdir(parents=True,exist_ok=True)
  if p.exists():assert p.read_bytes()==data,('sealed file changed',p)
  else:p.write_bytes(data)
  written[m.name]=hashlib.sha256(data).hexdigest()
done=[p.parent.name for p in sorted(dest.glob('*/complete.json'))]
receipt=dict(collected_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source=v['commit'],remote=v['expected_results'],completed=done,files_sha256=written)
(W/('FULL_WT2_COLLECTION_'+v['commit'][:8]+'.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(completed=done,main_completed=len([x for x in done if x.startswith('task')]),expected_main=18,files=len(written),bytes_received=len(b))),flush=True)
