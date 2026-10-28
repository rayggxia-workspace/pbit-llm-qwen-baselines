import argparse,base64,datetime,gzip,json,pathlib,subprocess
a=argparse.ArgumentParser();a.add_argument("--prefix");args=a.parse_args()
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/group64-scale-issue206-20261028');W=R/'work/jieruiz/206'
sub=json.loads((next(W.glob('POT_SUBMISSION_'+args.prefix+'*.json')) if args.prefix else max(W.glob('POT_SUBMISSION_*.json'),key=lambda p:p.stat().st_mtime)).read_bytes());sha=sub['commit'];D=R/'qwen3/results/group_shared_20261028'/sha[:12]
code='''import base64,gzip,hashlib,json,pathlib,sys,subprocess
v=PAYLOAD;r=pathlib.Path(v['root']);files={};phases=[]
test=r/'logs'/('pot-test-'+v['prefix']+'-'+v['test']+'.out');testtext=test.read_text(errors='replace') if test.exists() else ''
if ('Ran 33 tests' in testtext or 'Ran 34 tests' in testtext) and '\\nOK\\n' in testtext:files['validation.log']=base64.b64encode(test.read_bytes()).decode()
for i in range(4):
 d=r/'results'/v['source']/'pot_weight'/('shard'+str(i));done=d/'complete.json'
 log=r/'logs'/('pot-'+v['prefix']+'-'+v['job']+'_'+str(i)+'.out');text=log.read_text(errors='replace') if log.exists() else ''
 if done.exists():
  m=json.loads(done.read_bytes());assert m['status']=='completed' and m['cases']==(9 if i==0 else 8)
  for n,h in m['documents'].items():assert hashlib.sha256((d/n).read_bytes()).hexdigest()==h
  for f in d.glob('*.json'):files['pot_weight/shard'+str(i)+'/'+f.name]=base64.b64encode(f.read_bytes()).decode()
  if log.exists():files['pot_weight/shard'+str(i)+'/execution.log']=base64.b64encode(log.read_bytes()).decode()
  phases.append(dict(shard=i,status='completed',cases=m['cases'],complete_sha256=hashlib.sha256(done.read_bytes()).hexdigest()))
 else:
  if 'Traceback' in text or 'FAILED (' in text:
   for f in d.glob('*.json'):files['pot_weight_failed/shard'+str(i)+'/'+f.name]=base64.b64encode(f.read_bytes()).decode()
   if log.exists():files['pot_weight_failed/shard'+str(i)+'/execution.log']=base64.b64encode(log.read_bytes()).decode()
  observed=[]
  for f in d.glob('*.json'):
   if f.name=='provenance.json' or f.name.endswith('.sha256.json'):continue
   x=json.loads(f.read_bytes());observed.append(dict(case=x.get('case'),ppl=x.get('perplexity'),seconds=x.get('seconds')))
  phases.append(dict(shard=i,status='failed' if ('Traceback' in text or 'FAILED (' in text) else 'unsealed',observed=observed,log_tail=text[-1500:]))
out=dict(source=v['commit'],kind='clarified PoT W8 per64x64;shared x/g/u per64',phases=phases,files=files,test_passed=('Ran 33 tests' in testtext or 'Ran 34 tests' in testtext) and '\\nOK\\n' in testtext,
 queue=subprocess.check_output(['bash','-lc',"squeue -u Hongjie_Zeng -h -o '%i %T %j %M'"],text=True))
sys.stdout.buffer.write(gzip.compress(json.dumps(out).encode()))
'''.replace('PAYLOAD',repr(dict(root=sub['root'],source=sha[:12],prefix=sha[:8],job=sub['array'],test=sub['test_job'],commit=sha)))
ssh=['C:/Windows/System32/OpenSSH/ssh.exe','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai']
x=json.loads(gzip.decompress(subprocess.check_output(ssh+['/usr/bin/python3 -'],input=code.encode(),timeout=60)))
for n,b64 in x.pop('files').items():
 p=D/n;p.parent.mkdir(parents=True,exist_ok=True);b=base64.b64decode(b64)
 if p.exists():assert p.read_bytes()==b
 else:p.write_bytes(b)
x['collected_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();(W/('POT_COLLECTION_'+sha[:8]+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(x,ensure_ascii=True))
