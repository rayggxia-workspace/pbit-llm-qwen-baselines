"""Frozen full-model memory comparison. No model weights or GPUs required."""
import argparse,hashlib,json,pathlib,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from architecture_tlm.unified_v6.config import load
from architecture_tlm.unified_v6.memory_profiles import apply
from architecture_tlm.unified_v6.model import FullDecode
from architecture_tlm.unified_v6.run import write

# profile, engines, FFN, Attention, double_buffer. Algorithm remains T64.
CASES={
 'legacy_link':('legacy',8,'sc','exact',True),
 'prefetch_link':('prefetch',8,'sc','exact',True),
 'sram64_link':('sram64',8,'sc','exact',True),
 'ddr4_old':('ddr4',8,'sc','exact',True),
 'ddr4_wide':('ddr4',8,'sc','exact',True),
 'balanced_e8':('balanced_ddr4',8,'sc','exact',True),
 'balanced_e16':('balanced_ddr4',16,'sc','exact',True),
 'balanced_e32':('balanced_ddr4',32,'sc','exact',True),
 'balanced_e64':('balanced_ddr4',64,'sc','exact',True),
 'balanced_single':('balanced_ddr4',8,'sc','exact',False),
 'balanced_bf16':('balanced_ddr4',8,'bf16','exact',True),
 'balanced_w8':('balanced_ddr4',8,'w8','exact',True),
 'balanced_screen_pv':('balanced_ddr4',8,'sc','screen_pv',True),
 'balanced_screen_rejection':('balanced_ddr4',8,'sc','screen_rejection',True),
}

def main():
 p=argparse.ArgumentParser();p.add_argument('case',choices=CASES)
 p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--bridge')
 p.add_argument('--manifest',type=pathlib.Path,required=True);p.add_argument('--seed',type=int,default=0);a=p.parse_args()
 provenance=json.loads(a.manifest.read_text(encoding='utf-8'))
 for rel,expected in provenance['files'].items():
  if hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=expected['sha256']:raise ValueError('source mismatch '+rel)
 if a.output.exists():raise ValueError('immutable run directory already exists')
 a.output.mkdir(parents=True)
 profile,E,ffn,attn,db=CASES[a.case];c,m=load('qwen3_4b')
 c.update(context_tokens=2048,seed=a.seed,double_buffer=db,digital_weight_chunk_bytes=65536)
 c['ffn'].update(mode=ffn,engines=E,local_weight_bytes=E*4096)
 c['weight_chunk_bytes']=max(65536,E*4096)
 c['attention']['mode']=attn
 if a.case=='ddr4_wide':c=apply(c,'sram64')
 c=apply(c,profile,a.bridge,a.output/'dram')
 write(a.output/'EXECUTION.json',dict(case=a.case,seed=a.seed,source=provenance,
     config_sha256=hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest(),
     bridge_sha256=hashlib.sha256(pathlib.Path(a.bridge).read_bytes()).hexdigest() if a.bridge else None))
 start=time.monotonic();r=FullDecode(c,m).run();r['wall_seconds']=time.monotonic()-start
 r['execution_commit']=provenance['commit'];r['case']=a.case
 if r['DRAM']['backend']=='dramsys':
  d=r['DRAM']['details'];b=sum(v for k,v in r['DRAM']['traffic'].items() if k.endswith('_bursts'))
  if b!=d['burst_count']:raise ValueError('DRAMSys burst conservation failed')
  if d['status']!='finished':raise ValueError('DRAMSys incomplete')
 if ffn=='sc' and r['FFN_activity']['SC_64x64_tiles']!=656640:raise ValueError('SC tile conservation failed')
 write(a.output/'RESULT.json',r)
 files={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(a.output.iterdir()) if p.is_file()}
 write(a.output/'MANIFEST.json',dict(status='completed',case=a.case,seed=a.seed,files=files))
 print(json.dumps(dict(case=a.case,status='completed',TPOT_ms=r['metrics']['TPOT_ms'],wall_seconds=r['wall_seconds'])),flush=True)
if __name__=='__main__':main()
