import base64,datetime,gzip,hashlib,json,pathlib,subprocess
S=pathlib.Path(__file__).parent
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/group64-scale-issue206-20261028');W=R/'work/jieruiz/206'
sub=json.loads(max(W.glob('SUBMISSION_*.json'),key=lambda p:p.stat().st_mtime).read_bytes());root=sub['root'];sha=sub['commit']
D=R/'qwen3/results/group_shared_20261028'/sha[:12]
script='''import base64,gzip,hashlib,json,pathlib,subprocess,sys
v=PAYLOAD;r=pathlib.Path(v['root']);files={};phases=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for phase,i in [('pilot',0)]+[('main',j) for j in range(4)]:
 d=r/'results'/v['source']/phase/('shard'+str(i));done=d/'complete.json';case=[]
 if done.exists():
  m=json.loads(done.read_bytes());assert m['status']=='completed'
  for n,h in m['documents'].items():assert sha(d/n)==h
  for f in d.glob('*.json'):files[phase+'/shard'+str(i)+'/'+f.name]=base64.b64encode(f.read_bytes()).decode()
  phases.append(dict(phase=phase,shard=i,status='completed',cases=m['cases'],complete_sha256=sha(done)))
 else:
  for f in sorted(d.glob('*.json')):
   if f.name=='provenance.json' or f.name.endswith('.sha256.json'):continue
   if f.with_suffix('.sha256.json').exists():
    x=json.loads(f.read_bytes());assert sha(f)==json.loads(f.with_suffix('.sha256.json').read_bytes())['sha256']
    case.append(dict(case=x.get('case'),ppl=x.get('perplexity'),seconds=x.get('seconds')))
  phases.append(dict(phase=phase,shard=i,status='unsealed',observed=case))
log=r/'logs'/('pilot-'+v['prefix']+'-'+v['pilot']+'.out');text=log.read_text(errors='replace') if log.exists() else ''
if log.exists():files['pilot_validation.log']=base64.b64encode(log.read_bytes()).decode()
logs=[]
for f in sorted((r/'logs').glob('main-'+v['prefix']+'-*.out')):logs.append(dict(path=str(f),tail=f.read_text(errors='replace')[-1000:]))
q=subprocess.run(['bash','-lc',"squeue -u Hongjie_Zeng -h -o '%i %T %j %M %R'"],capture_output=True,text=True)
queue='\\n'.join(x for x in q.stdout.splitlines() if 'group64scale206' in x)
out=dict(source=v['commit'],phases=phases,pilot_tail=text[-4000:],validation_failed=('FAILED (' in text or 'Traceback' in text),validation_passed=('Ran 28 tests' in text and '\\nOK\\n' in text),queue=queue,main_logs=logs,files=files)
sys.stdout.buffer.write(gzip.compress(json.dumps(out).encode()))
'''.replace('PAYLOAD',repr(dict(root=root,source=sha[:12],commit=sha,prefix=sha[:8],pilot=sub['pilot_job'])))
ssh=['C:/Windows/System32/OpenSSH/ssh.exe','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai']
out=json.loads(gzip.decompress(subprocess.check_output(ssh+['/usr/bin/python3 -'],input=script.encode(),timeout=60)))
for n,s in out.pop('files').items():
 p=D/n;p.parent.mkdir(parents=True,exist_ok=True);b=base64.b64decode(s)
 if p.exists() and n!='pilot_validation.log':assert p.read_bytes()==b
 else:p.write_bytes(b)
out['collected_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
(W/'COLLECTION.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
view=dict(out)
if not out['validation_failed']:view['pilot_tail']=out['pilot_tail'][-700:]
print(json.dumps(view,ensure_ascii=True))
