"""Allocation-only compact evidence from immutable TRAIN/VAL optimizer logs."""
from pathlib import Path
import argparse,hashlib,json,os
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 assert os.environ.get('SLURM_JOB_ID')
 cfg=json.loads(Path(a.config).read_text(encoding='utf-8'));home=Path('/home/Weican_Chen').resolve();out=Path(a.output).resolve();assert out.is_relative_to(home)
 rows=[]
 for origin in cfg['curve_source_roots']:
  root=Path(origin).resolve();assert root.is_relative_to(home)
  for path in sorted((root/'search').glob('*_training.json')):
   if path.name.endswith('_partial_training.json'):continue
   raw=path.read_bytes();data=json.loads(raw);steps=data['steps'];direct=[v for v in steps if v['stage']=='direct']
   thin=[v for v in steps if v['epoch']==1 or v['epoch']%100==0 or v is steps[-1]]
   checkpoints=[{'stage':c['stage'],'epoch':c['epoch'],'train':c['train'],'val':c['val'],'val_budget_pass':c['val_budget_pass']} for c in data['checkpoints']]
   rows.append({'source':str(path),'bytes':len(raw),'sha256':sha(raw),'id':path.name.removesuffix('_training.json'),'epochs_total':len(steps),'first_direct':direct[0] if direct else None,'last_direct':direct[-1] if direct else None,'min_Fb':min(v['Fb'] for v in steps),'max_abs_budget_error':max(abs(v.get('F',0)) for v in steps),'rejected_steps':sum(v['rejected'] for v in steps),'selection':data['selection'],'thin_steps':thin,'checkpoints':checkpoints})
 result={'job':os.environ['SLURM_JOB_ID'],'source_commit':os.environ.get('GATE_SOURCE_COMMIT'),'scope':'Derived from TRAIN/VAL logs only. No blind loading or selection.','models':rows}
 out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2);stream.write('\n')
 print(json.dumps({'models':len(rows),'output':str(out),'sha256':sha(out.read_bytes())}))
if __name__=='__main__':main()
