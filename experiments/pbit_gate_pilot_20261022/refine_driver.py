"""Extend p-bit TRAIN/VAL optimization without recapturing or reading blind data."""
from pathlib import Path
import argparse,hashlib,json,os,platform,subprocess,sys,time,traceback,shutil
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 assert os.environ.get('SLURM_JOB_ID') and os.environ.get('GATE_SOURCE_COMMIT')
 personal=Path('/home/Weican_Chen').resolve();out=Path(a.output).resolve();assert out.is_relative_to(personal);out.mkdir(parents=True,exist_ok=False)
 cfg=json.loads(Path(a.config).read_text(encoding='utf-8'));dataset=Path(cfg['training_dataset']).resolve();capture=Path(cfg['capture_report']).resolve()
 assert dataset.is_relative_to(personal) and capture.is_relative_to(personal)
 assert sha(dataset)==cfg['training_dataset_sha256'] and sha(capture)==cfg['capture_report_sha256']
 cfg.update(source_commit=os.environ['GATE_SOURCE_COMMIT'],code_commit=os.environ['GATE_SOURCE_COMMIT'],code_repository='rayggxia-workspace/pbit-llm-qwen-baselines')
 runtime=out/'runtime_config.json';runtime.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (out/'capture').mkdir();shutil.copyfile(capture,out/'capture/capture.json')
 started=time.time();commands=[];status='failed'
 try:
  cmd=[sys.executable,'-P','-u','-m','experiments.pbit_gate_pilot_20261022.optimize','--config',str(runtime),'--dataset',str(dataset),'--output',str(out/'search')];commands.append(cmd)
  with (out/'optimize.stdout.txt').open('w',encoding='utf-8') as stdout,(out/'optimize.stderr.txt').open('w',encoding='utf-8') as stderr:
   result=subprocess.run(cmd,stdout=stdout,stderr=stderr)
  if result.returncode:raise RuntimeError('refine optimizer exit '+str(result.returncode))
  status='completed_trainval_only'
 except Exception:
  (out/'FAILURE.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
 finally:
  record={'status':status,'source_commit':cfg['source_commit'],'runtime_config_sha256':sha(runtime),'job':os.environ['SLURM_JOB_ID'],'node':platform.node(),'seconds':time.time()-started,'commands':commands,'blind_evaluated':False,'reused_training_dataset':str(dataset),'scope':'Longer pbit49 query-relative training on existing TRAIN/VAL only; no blind model evaluation.'}
  (out/'RUN.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  manifest={'files':[{'path':x.relative_to(out).as_posix(),'bytes':x.stat().st_size,'sha256':sha(x)} for x in sorted(out.rglob('*')) if x.is_file() and x.name!='MANIFEST.json']}
  (out/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
