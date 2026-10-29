import base64,datetime,gzip,hashlib,json,pathlib,subprocess
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/group64-scale-issue206-20261028');W=R/'work/jieruiz/206'
sub=json.loads(max(W.glob('GROUP_SWEEP_SUBMISSION_*.json'),key=lambda p:p.stat().st_mtime).read_bytes());sha=sub['commit'];D=R/'qwen3/results/group_shared_20261028'/sha[:12]
code='''import base64,gzip,hashlib,json,pathlib,subprocess,sys
v=PAYLOAD;r=pathlib.Path(v['root']);files={};phases=[]
cpu=r/'logs'/('size-cpu-'+v['prefix']+'-'+v['cpu']+'.out');tt=cpu.read_text(errors='replace') if cpu.exists() else '';passed='Ran 71 tests' in tt and '\\nOK (skipped=10)\\n' in tt
if passed or 'FAILED (' in tt:files['cpu_validation.log']=base64.b64encode(cpu.read_bytes()).decode()
for label,count,stem in [('gate',3,'size-gate-'+v['prefix']+'-'+v['gate']+'.out')]+[('shard'+str(i),6,'size-'+v['prefix']+'-'+v['array']+'_'+str(i)+'.out') for i in range(6)]:
 d=r/'results'/v['source']/'group_size_levels'/label;done=d/'complete.json';log=r/'logs'/stem;text=log.read_text(errors='replace') if log.exists() else ''
 if done.exists():
  m=json.loads(done.read_bytes());assert m['status']=='completed' and m['cases']==count
  for n,h in m['documents'].items():assert hashlib.sha256((d/n).read_bytes()).hexdigest()==h
  for f in d.glob('*.json'):files['group_size_levels/'+label+'/'+f.name]=base64.b64encode(f.read_bytes()).decode()
  if log.exists():files['group_size_levels/'+label+'/execution.log']=base64.b64encode(log.read_bytes()).decode()
  phases.append(dict(phase=label,status='completed',cases=m['cases'],complete_sha256=hashlib.sha256(done.read_bytes()).hexdigest()))
 else:
  obs=[]
  for f in sorted(d.glob('*.json')):
   if f.name=='provenance.json' or f.name.endswith('.sha256.json'):continue
   x=json.loads(f.read_bytes());obs.append(dict(case=x.get('case'),ppl=x.get('perplexity'),seconds=x.get('seconds')))
  failed='Traceback' in text or 'FAILED (' in text
  if failed:
   for f in d.glob('*.json'):files['group_size_levels_failed/'+label+'/'+f.name]=base64.b64encode(f.read_bytes()).decode()
   if log.exists():files['group_size_levels_failed/'+label+'/execution.log']=base64.b64encode(log.read_bytes()).decode()
  phases.append(dict(phase=label,status='failed' if failed else 'unsealed',observed=obs,log_tail=text[-900:]))
out=dict(source=v['commit'],phases=phases,files=files,cpu_passed=passed,cpu_tail=tt[-700:],queue=subprocess.check_output(['bash','-lc',"squeue -u Hongjie_Zeng -h -o '%i %T %j %M'"],text=True))
sys.stdout.buffer.write(gzip.compress(json.dumps(out).encode()))
'''.replace('PAYLOAD',repr(dict(root=sub['root'],source=sha[:12],prefix=sha[:8],cpu=sub['cpu_job'],gate=sub['gate_job'],array=sub['array'],commit=sha)))
ssh=['C:/Windows/System32/OpenSSH/ssh.exe','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai']
x=json.loads(gzip.decompress(subprocess.check_output(ssh+['/usr/bin/python3 -'],input=code.encode(),timeout=60)))
compressed=[]
for n,b64 in x.pop('files').items():
 p=D/n;p.parent.mkdir(parents=True,exist_ok=True);b=base64.b64decode(b64)
 if p.exists():assert p.read_bytes()==b
 elif p.with_suffix(p.suffix+'.gz').exists():assert gzip.decompress(p.with_suffix(p.suffix+'.gz').read_bytes())==b
 elif len(b)>1800000:p.with_suffix(p.suffix+'.gz').write_bytes(gzip.compress(b,mtime=0))
 else:p.write_bytes(b)
 if not p.exists():
  z=p.with_suffix(p.suffix+'.gz');compressed.append(dict(original=n,original_sha256=hashlib.sha256(b).hexdigest(),original_bytes=len(b),gzip_file=str(z.relative_to(D)).replace('\\','/'),gzip_sha256=hashlib.sha256(z.read_bytes()).hexdigest(),remote_original=sub['root']+'/results/'+sha[:12]+'/'+n))
if compressed:(D/'COMPRESSED_ARTIFACTS.json').write_text(json.dumps(compressed,indent=2)+'\n',encoding='utf-8',newline='\n')
x['collected_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
(W/('GROUP_SWEEP_COLLECTION_'+sha[:8]+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(x,ensure_ascii=True))
