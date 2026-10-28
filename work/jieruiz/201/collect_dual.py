import base64,datetime,gzip,hashlib,json,pathlib,subprocess
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/dual-gu-issue201-20261027');W=R/'work/jieruiz/201';D=R/'qwen3/results/dual_gu_20261027';D.mkdir(parents=True,exist_ok=True)
sub=json.loads((W/'SUBMISSION_2cd6d360.json').read_text());val=json.loads((W/'VALIDATION_SUBMISSION_b0a87c86.json').read_text())
payload=dict(root=sub['root'],source=sub['commit'][:12],validation_job=val['pilot_job'],validation_sha=val['commit'][:8])
script=r'''import pathlib,json,hashlib,base64,gzip,sys
v=PAYLOAD;r=pathlib.Path(v['root']);p=r/'results'/v['source']/'pilot'/'shard3';files={};pilot=None
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if (p/'complete.json').exists():
 m=json.loads((p/'complete.json').read_text());assert m['status']=='completed'
 for n,s in m['documents'].items():assert sha(p/n)==s
 for f in p.glob('*.json'):files['pilot/'+f.name]=base64.b64encode(f.read_bytes()).decode()
 pilot=dict(status='completed',cases=m['cases'],complete_sha256=sha(p/'complete.json'))
progress=[]
for i in range(4):
 d=r/'results'/v['source']/'main'/('shard'+str(i));done=d/'complete.json';partial=[]
 if done.exists():
  m=json.loads(done.read_text());assert m['status']=='completed'
  for n,s in m['documents'].items():assert sha(d/n)==s
  for f in d.glob('*.json'):files['main/shard'+str(i)+'/'+f.name]=base64.b64encode(f.read_bytes()).decode()
  progress.append(dict(shard=i,status='completed',cases=m['cases'],complete_sha256=sha(done)))
 else:
  for f in sorted(d.glob('*.json')):
   if f.name.endswith('.sha256.json') or f.name=='provenance.json':continue
   side=f.with_suffix('.sha256.json')
   if side.exists():
    assert sha(f)==json.loads(side.read_text())['sha256'];x=json.loads(f.read_text())
    partial.append(dict(case=x.get('case'),ppl=x.get('perplexity'),seconds=x.get('seconds')))
  logs=list((r/'logs').glob('main-*_'+str(i)+'.out'))
  tail=logs[-1].read_text()[-1200:] if logs else ''
  progress.append(dict(shard=i,status='failed' if 'Traceback' in tail else 'unsealed',partial_cases=partial,log_tail=tail))
vl=r/'logs'/('pilot-'+v['validation_sha']+'-'+str(v['validation_job'])+'.out')
validation=dict(job=v['validation_job'],log=str(vl),status='unsealed')
if vl.exists():
 b=vl.read_bytes();validation.update(log_sha256=sha(vl),tail=b.decode()[-1800:])
 if b'Ran 18 tests' in b and b'\nOK\n' in b:validation['status']='passed18';files['validation.log']=base64.b64encode(b).decode()
sys.stdout.buffer.write(gzip.compress(json.dumps(dict(pilot=pilot,main=progress,validation=validation,files=files)).encode()))
'''.replace('PAYLOAD',repr(payload))
ssh=['C:/Windows/System32/OpenSSH/ssh.exe','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai']
r=json.loads(gzip.decompress(subprocess.check_output(ssh+['/usr/bin/python3 -'],input=script.encode(),timeout=60)))
for name,b64 in r.pop('files').items():
 p=D/name;p.parent.mkdir(parents=True,exist_ok=True);b=base64.b64decode(b64)
 if p.exists():assert p.read_bytes()==b
 else:p.write_bytes(b)
r['collected_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
r['scientific_source']=sub['commit']
r['validation_source']=val['commit']
(W/'COLLECTION.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(r,ensure_ascii=True))
