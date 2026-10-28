import base64,gzip,hashlib,json,pathlib,subprocess,datetime
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/group64-scale-issue206-20261028');W=R/'work/jieruiz/206';s=json.loads((W/'TUNE_SANITY_SUBMISSION.json').read_bytes());D=R/'qwen3/results/group_shared_20261028/d825f7d6e075'/('sanity-'+s['commit'][:12])
code='''import pathlib,json,base64,gzip,hashlib,sys
v=PAYLOAD;p=pathlib.Path(v['output']);log=pathlib.Path(v['log']);files={};status='unsealed'
if (p/'complete.json').exists():
 c=json.loads((p/'complete.json').read_bytes());assert c['status']=='completed'
 for n,h in c['documents'].items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h
 for f in p.glob('*.json'):files[f.name]=base64.b64encode(f.read_bytes()).decode()
 status='completed'
t=log.read_bytes() if log.exists() else b''
if status=='completed' or b'Traceback' in t:files['execution.log']=base64.b64encode(t).decode()
if b'Traceback' in t:status='failed'
sys.stdout.buffer.write(gzip.compress(json.dumps(dict(status=status,files=files,log_tail=t[-3500:].decode(errors='replace'))).encode()))
'''.replace('PAYLOAD',repr(s))
ssh=['C:/Windows/System32/OpenSSH/ssh.exe','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai'];x=json.loads(gzip.decompress(subprocess.check_output(ssh+['/usr/bin/python3 -'],input=code.encode(),timeout=45)))
D.mkdir(parents=True,exist_ok=True)
for n,b in x.pop('files').items():
 p=D/n;raw=base64.b64decode(b)
 if p.exists():assert p.read_bytes()==raw
 else:p.write_bytes(raw)
x.update(probe_commit=s['commit'],job=s['job'],collected_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());(W/'TUNE_SANITY_COLLECTION.json').write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8',newline='\n')
if x['status']=='completed':
 y=json.loads((D/'sanity.json').read_bytes());assert y['probe_source_sha256']==s['probe_sha256'] and len(y['rows'])==16 and all(r['direct_mean_equal'] for r in y['rows']) and sum(r['parent_finite_equal'] is True for r in y['rows'])==8
 print(json.dumps(dict(status='completed',job=s['job'],source=s['commit'],finite_parent_equal=8,direct_mean_equal=16,zero_difference=True)))
else:print(json.dumps(x))
