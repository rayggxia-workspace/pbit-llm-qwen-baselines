"""Read-only server status. No inference, scheduler writes or snapshot edits."""
import json,pathlib,shlex,subprocess,sys
sys.stdout.reconfigure(encoding='utf-8')
SCRIPT=r'''
import pathlib,json,hashlib,datetime,subprocess,collections
p=pathlib.Path('/home/Hongjie_Zeng/projects/pbit-llama2-task-accuracy-20261020-issue73')
old='022db6828c0caba96ae3d620f80b27c1ae3774b9';new='309ca9c1629c364142ffdce474d5f6138da929c1'
old_ids={0,4,5,6,13,17,18,19}
suite=json.loads((p/'outputs'/old/'suite.json').read_text());rows=[]
for i in range(26):
 task=suite['tasks'][i//13];cfg=suite['configurations'][i%13];commit=old if i in old_ids else new
 f=p/'outputs'/commit/'full'/(task+'_'+cfg['name']+'.json')
 row=dict(index=i,task=task,configuration=cfg['name'],commit=commit,path=str(f))
 if f.exists():
  raw=f.read_bytes();d=json.loads(raw);a=d.get('document_artifact',{});doc=f.with_suffix('.documents.jsonl')
  valid=d.get('status')=='completed' and d.get('n_documents')==({'piqa':1838,'arc_easy':2376}[task]) and d.get('code_commit')==commit and d.get('task')==task and d.get('configuration')==cfg
  sha=hashlib.sha256(doc.read_bytes()).hexdigest() if doc.exists() else None
  seal=doc.exists() and sha==a.get('sha256') and doc.stat().st_size==a.get('bytes') and str(doc)==a.get('path')
  audit=d.get('execution_audit',{})
  layer_ok=audit.get('every_scored_target_used_32_decode_layers') is True
  row.update(status='completed' if valid and seal and layer_ok else 'invalid',declared_status=d.get('status'),documents_sha256=sha,document_seal=seal,layer_guard=layer_ok,result_sha256=hashlib.sha256(raw).hexdigest(),metrics=d.get('metrics'),seconds=d.get('elapsed_seconds'),slurm_job_id=d.get('slurm_job_id'))
 else:row.update(status='missing')
 rows.append(row)
q=subprocess.run(['/opt/slurm/21.08.8/bin/squeue','-r','-h','-u','Hongjie_Zeng','-o','%i|%T|%M|%j|%R'],capture_output=True,text=True)
result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),counts=dict(collections.Counter(r['status'] for r in rows)),results=rows,queue=q.stdout,queue_error=q.stderr,read_only=True,scope='sealed JSON + documents SHA + declared 32-layer guard; final official-metric oracle separate')
print(json.dumps(result))
'''
cmd=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=20','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','lab-server-ai','/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python -B -c '+shlex.quote(SCRIPT)]
r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',timeout=100)
if r.returncode:print(r.stderr);raise SystemExit(r.returncode)
d=json.loads(r.stdout)
out=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/llama73_status_20261022.json')
out.write_bytes((json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps(dict(utc=d['utc'],counts=d['counts'],queue=d['queue'],invalid=[x for x in d['results'] if x['status']!='completed'],local_receipt=str(out)),ensure_ascii=False))
