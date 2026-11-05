from pathlib import Path
import subprocess,json,hashlib,runpy,sys,re
A=Path(__file__).resolve().parent;R=A.parent.parent/'pbit-llm-qwen-baselines';H='94d2b88cb6546262bdb0f2d1c61a150a50f84f47';D=A/'doc189';D.mkdir(exist_ok=False)
paths=subprocess.check_output(['git','-C',str(R),'ls-tree','-r','--name-only',H,'architecture_tlm/simulator_survey_20261025','work/rayggxia/187']).decode().splitlines();before={}
for p in paths:
 b=subprocess.check_output(['git','-C',str(R),'show',H+':'+p]);f=D/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b);before[p]=hashlib.sha256(b).hexdigest()
doc=D/'architecture_tlm/simulator_survey_20261025';src=json.loads((doc/'SOURCES.json').read_text(encoding='utf-8'));pdfs=[]
for x in src['local_pdfs']:
 p=Path(x['path']);b=p.read_bytes();assert hashlib.sha256(b).hexdigest()==x['sha256'];pdfs.append(x['record_id'])
for f in doc.glob('*.md'):
 for target in re.findall(r'\]\(([^)]+)\)',f.read_text(encoding='utf-8')):
  if target.startswith(('https://','#')):continue
  path,_,anchor=target.partition('#');q=f.parent/path;assert q.is_file(),(f,target)
  if anchor:assert 'id="'+anchor+'"' in q.read_text(encoding='utf-8')
# These two historical arithmetic/probe generators only write inside this
# extracted documentation snapshot. Other generators depend on old live HEADs.
for n in ['estimate_sc_digital.py','audit_stochastic_metrics.py']:
 runpy.run_path(str(D/'work/rayggxia/187'/n),run_name='__main__')
checks=[]
for p in ['SC_DIGITAL_ESTIMATE.json','STOCHASTIC_METRIC_AUDIT.json']:
 old=json.loads(subprocess.check_output(['git','-C',str(R),'show',H+':architecture_tlm/simulator_survey_20261025/'+p]));new=json.loads((doc/p).read_text(encoding='utf-8'));assert old==new,p;checks.append(p)
out=dict(status='passed',head=H,primary_source_sample=['https://arxiv.org/html/2411.15982v1','https://github.com/tukl-msd/DRAMPower','https://arxiv.org/html/2610.15873v1'],local_pdf_sha_verified=pdfs,exact_numeric_reproduction=checks,limitation='primary-source spot check plus published metadata/numeric audit; not a reproduction of 33 papers or current hardware proof; historical plans superseded by PR205 where dated')
(A/'AUDIT189.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('PASS documentation links, 4 PDF byte hashes and 2 exact numeric reproductions')
