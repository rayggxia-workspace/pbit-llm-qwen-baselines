import base64,datetime,hashlib,json,pathlib,subprocess
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/dual-gu-issue201-20261027');W=R/'work/jieruiz/201';D=R/'qwen3/results/dual_gu_20261027'
sub=json.loads((W/'SUBMISSION_2cd6d360.json').read_bytes())
c=json.loads((R/'qwen3/dual_gu/config.json').read_bytes())
paths=[c[k] for k in ('prepared','fixed_xz_calibration','fixed_gu_calibration')]
script='''import pathlib,json,base64,hashlib,sys
paths=PATHS
out={}
for i,p in enumerate(paths):
 b=pathlib.Path(p).read_bytes();out[str(i)]=dict(path=p,sha256=hashlib.sha256(b).hexdigest(),content=base64.b64encode(b).decode())
sys.stdout.write(json.dumps(out))
'''.replace('PATHS',repr(paths))
ssh=['C:/Windows/System32/OpenSSH/ssh.exe','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai']
out=json.loads(subprocess.check_output(ssh+['/usr/bin/python3 -'],input=script.encode(),timeout=45))
names=['prepared.json','fixed_xz_calibration.json','fixed_gu_calibration.json'];index={}
for i,n in enumerate(names):
 x=out[str(i)];b=base64.b64decode(x.pop('content'));assert hashlib.sha256(b).hexdigest()==x['sha256']
 p=D/'inputs'/n;p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():assert p.read_bytes()==b
 else:p.write_bytes(b)
 index[n]=x
for k,n in [('fixed_xz_calibration','fixed_xz_calibration.json'),('fixed_gu_calibration','fixed_gu_calibration.json')]:assert index[n]['sha256']==c[k+'_sha256']
(D/'inputs/INDEX.json').write_text(json.dumps(index,indent=2)+'\n',encoding='utf-8',newline='\n')
prep=json.loads((D/'inputs/prepared.json').read_bytes())
print(json.dumps({'inputs':index,'prepared_keys':list(prep),'model':prep.get('model'),'model_manifest_keys':list(prep.get('files',{}))[:10]},ensure_ascii=True))
