"""Allocated stronger max4 controls and compact training-curve evidence."""
from pathlib import Path
import argparse,hashlib,json,os,platform,shutil,subprocess,sys,time,traceback
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 assert os.environ.get('SLURM_JOB_ID') and os.environ.get('GATE_SOURCE_COMMIT')
 home=Path('/home/Weican_Chen').resolve();out=Path(a.output).resolve();assert out.is_relative_to(home);out.mkdir(parents=True,exist_ok=False)
 cfg=json.loads(Path(a.config).read_text(encoding='utf-8'));dataset=Path(cfg['training_dataset']).resolve();capture=Path(cfg['capture_report']).resolve()
 assert dataset.is_relative_to(home) and capture.is_relative_to(home)
 assert sha(dataset)==cfg['training_dataset_sha256'] and sha(capture)==cfg['capture_report_sha256']
 cfg.update(source_commit=os.environ['GATE_SOURCE_COMMIT'],code_commit=os.environ['GATE_SOURCE_COMMIT'],code_repository='rayggxia-workspace/pbit-llm-qwen-baselines')
 runtime=out/'runtime_config.json';runtime.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (out/'capture').mkdir();shutil.copyfile(capture,out/'capture/capture.json')
 started=time.time();commands=[];status='failed'
 try:
  stages=[['baseline_extension','--config',str(runtime),'--dataset',str(dataset),'--output',str(out/'search')],['curve_summary','--config',str(runtime),'--output',str(out/'CURVE_SUMMARY.json')]]
  for stage in stages:
   cmd=[sys.executable,'-P','-u','-m','experiments.pbit_gate_pilot_20261022.'+stage[0],*stage[1:]];commands.append(cmd)
   with (out/(stage[0]+'.stdout.txt')).open('w',encoding='utf-8') as stdout,(out/(stage[0]+'.stderr.txt')).open('w',encoding='utf-8') as stderr:
    result=subprocess.run(cmd,stdout=stdout,stderr=stderr)
   if result.returncode:raise RuntimeError(stage[0]+' failed exit '+str(result.returncode))
  status='completed_trainval_only'
 except Exception:
  (out/'FAILURE.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
 finally:
  record={'status':status,'source_commit':cfg['source_commit'],'runtime_config_sha256':sha(runtime),'job':os.environ['SLURM_JOB_ID'],'node':platform.node(),'seconds':time.time()-started,'commands':commands,'blind_evaluated':False,'no_model_training':True,'scope':'TRAIN-fitted low-temperature/hard-threshold max4 controls; VAL reporting only.'}
  (out/'RUN.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  manifest={'files':[{'path':x.relative_to(out).as_posix(),'bytes':x.stat().st_size,'sha256':sha(x)} for x in sorted(out.rglob('*')) if x.is_file() and x.name!='MANIFEST.json']}
  (out/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
