"""Phase-two allocation driver: capture fresh documents and scan TRAIN/VAL only."""
from pathlib import Path
import argparse,hashlib,json,os,platform,subprocess,sys,time,traceback
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 assert os.environ.get('SLURM_JOB_ID') and os.environ.get('GATE_SOURCE_COMMIT')
 out=Path(a.output).resolve();assert out.is_relative_to(Path('/home/Weican_Chen').resolve());out.mkdir(parents=True,exist_ok=False)
 cfg=json.loads(Path(a.config).read_text(encoding='utf-8'));cfg.update(source_commit=os.environ['GATE_SOURCE_COMMIT'],code_commit=os.environ['GATE_SOURCE_COMMIT'],code_repository='rayggxia-workspace/pbit-llm-qwen-baselines')
 runtime=out/'runtime_config.json';runtime.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 started=time.time();commands=[];status='failed'
 try:
  stages=[['preflight','--config',str(runtime),'--output',str(out/'preflight'),'--gpu'],
          ['capture_teacher','--config',str(runtime),'--output',str(out/'capture')],
          ['optimize','--config',str(runtime),'--dataset',str(out/'capture/training_dataset.npz'),'--output',str(out/'search')]]
  for stage in stages:
   cmd=[sys.executable,'-P','-u','-m','experiments.pbit_gate_pilot_20261022.'+stage[0],*stage[1:]];commands.append(cmd)
   print('START '+stage[0],flush=True)
   with (out/(stage[0]+'.stdout.txt')).open('w',encoding='utf-8') as stdout,(out/(stage[0]+'.stderr.txt')).open('w',encoding='utf-8') as stderr:
    result=subprocess.run(cmd,stdout=stdout,stderr=stderr)
   if result.returncode:raise RuntimeError(stage[0]+' failed exit '+str(result.returncode))
   print('DONE '+stage[0],flush=True)
  status='completed_trainval_only'
 except Exception:
  (out/'FAILURE.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
 finally:
  record={'status':status,'source_commit':cfg['source_commit'],'runtime_config_sha256':sha(runtime),'job':os.environ['SLURM_JOB_ID'],'node':platform.node(),'seconds':time.time()-started,'commands':commands,'blind_evaluated':False,'scope':'Fresh frozen teacher; only TRAIN/VAL optimization. Blind artifact is separate and is not supplied to optimizer. No full student PPL or PPA.'}
  (out/'RUN.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  manifest={'files':[{'path':x.relative_to(out).as_posix(),'bytes':x.stat().st_size,'sha256':sha(x)} for x in sorted(out.rglob('*')) if x.is_file() and x.name!='MANIFEST.json']}
  (out/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
