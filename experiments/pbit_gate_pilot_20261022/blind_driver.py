"""Allocated final evaluation dispatch for a previously frozen candidate set."""
from pathlib import Path
import argparse,json,os,subprocess,sys
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 assert os.environ.get('SLURM_JOB_ID') and os.environ.get('CUDA_VISIBLE_DEVICES') not in (None,'')
 cfg=json.loads(Path(a.config).read_text(encoding='utf-8'));freeze=Path(cfg['freeze']).resolve();assert freeze.is_relative_to(Path('/home/Weican_Chen').resolve())
 command=[sys.executable,'-P','-u','-m','experiments.pbit_gate_pilot_20261022.blind_evaluate','evaluate','--freeze',str(freeze),'--output',a.output]
 subprocess.run(command,check=True)
if __name__=='__main__':main()
