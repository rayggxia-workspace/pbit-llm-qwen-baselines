import base64,gzip,hashlib,json,pathlib,subprocess,sys
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/ffn-local-pipeline-issue186-20261025');W=R/'work/jieruiz/186'
suffix=sys.argv[1] if len(sys.argv)>1 else ''
sub=json.loads((W/('LOCAL_PORTS'+suffix+'_SUBMISSION.json')).read_text(encoding='utf-8'))
SCRIPT=r'''import pathlib,json,hashlib,gzip,base64,sys
root=pathlib.Path(REMOTE);files={};done=[];failed=[];running=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for index in INDICES:
 f=root/'results'/('case_'+str(index));mf=f/'MANIFEST.json'
 logs=list((root/'logs').glob('*_'+str(index)+'.out'));log=logs[0] if logs else None
 if mf.exists():
  m=json.loads(mf.read_text());assert m['status']=='completed'
  for n in ('RESULT.json','RESULT_SUMMARY.json','EXECUTION.json'):assert sha(f/n)==m['files'][n]['sha256']
  for n in ('RESULT_SUMMARY.json','EXECUTION.json','MANIFEST.json'):files[f.name+'/'+n]=base64.b64encode((f/n).read_bytes()).decode()
  done.append(dict(index=index,case=m['case'],manifest_sha256=sha(mf)))
 elif log is not None and 'Traceback' in log.read_text():
  failed.append(dict(index=index,log=str(log),sha256=sha(log),tail=log.read_text()[-1800:]))
 else:running.append(index)
sys.stdout.buffer.write(gzip.compress(json.dumps(dict(remote=str(root),completed=done,failed=failed,unsealed=running,files=files)).encode()))
'''.replace('REMOTE',repr(sub['remote'])).replace('INDICES',repr(sub['indices']))
ssh=['C:/Windows/System32/OpenSSH/ssh.exe','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai']
raw=subprocess.check_output(ssh+['/usr/bin/python3 -'],input=SCRIPT.encode(),timeout=60);r=json.loads(gzip.decompress(raw))
out=R/('architecture_tlm/local_ports_20261027/results'+suffix.lower());out.mkdir(exist_ok=True)
for rel,data in r.pop('files').items():
 p=pathlib.PurePosixPath(rel);assert len(p.parts)==2 and p.parts[1] in ('RESULT_SUMMARY.json','EXECUTION.json','MANIFEST.json')
 dest=out.joinpath(*p.parts);dest.parent.mkdir(exist_ok=True);b=base64.b64decode(data)
 if dest.exists():assert dest.read_bytes()==b
 else:dest.write_bytes(b)
(W/('LOCAL_PORTS'+suffix+'_COLLECTION.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
sys.stdout.reconfigure(encoding='utf-8');print(json.dumps({'completed':len(r['completed']),'failed':r['failed'],'unsealed':r['unsealed']},ensure_ascii=False))
