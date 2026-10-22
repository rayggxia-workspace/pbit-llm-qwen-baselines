"""CPU Slurm step that persists the complete candidate list before blind access."""
from pathlib import Path
import argparse,hashlib,json,os,pwd,subprocess,sys
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 assert os.environ.get('SLURM_JOB_ID') and os.environ.get('CUDA_VISIBLE_DEVICES')==''
 u=pwd.getpwuid(os.getuid());home=Path(u.pw_dir).resolve();assert u.pw_name=='Weican_Chen' and home==Path('/home/Weican_Chen') and home.stat().st_uid==os.getuid()
 cfg=json.loads(Path(a.config).read_text(encoding='utf-8'));freeze=Path(cfg['freeze']).resolve();out=Path(a.output).resolve()
 paths=[Path(cfg[k]).resolve() for k in ['search_root','additional_search_root','baseline_search_root']]+[freeze,out]
 assert all(p.is_relative_to(home) for p in paths);out.mkdir(exist_ok=False,parents=True)
 command=[sys.executable,'-P','-u','-m','experiments.pbit_gate_pilot_20261022.blind_evaluate','freeze','--search-root',cfg['search_root'],'--additional-search-root',cfg['additional_search_root'],'--baseline-search-root',cfg['baseline_search_root'],'--output',str(freeze.parent)]
 subprocess.run(command,check=True)
 raw=freeze.read_bytes();receipt={'job':os.environ['SLURM_JOB_ID'],'source_commit':os.environ.get('GATE_SOURCE_COMMIT'),'freeze':str(freeze),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'model_count':len(json.loads(raw)['records']),'no_blind_dataset_loaded':True,'command':command}
 (out/'FREEZE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(receipt))
if __name__=='__main__':main()
