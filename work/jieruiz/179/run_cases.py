"""Frozen task scenarios, one process per case; all full models unless labelled."""
import argparse,hashlib,json,pathlib,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from architecture_tlm.unified_v6.config import load
from architecture_tlm.unified_v6.model import FullDecode
from architecture_tlm.unified_v6.run import source_record,write

CASES={
 'qwen3_full_bf16_exact':('qwen3_4b','bf16','exact',False,2048,64,0),
 'qwen3_full_oldsc_exact':('qwen3_4b','sc','exact',True,2048,64,0),
 'qwen3_full_latest64_exact':('qwen3_4b','sc','exact',False,2048,64,0),
 'qwen3_full_latest128_exact':('qwen3_4b','sc','exact',False,2048,128,0),
 'qwen3_full_latest64_screen_pv':('qwen3_4b','sc','screen_pv',False,2048,64,0),
 'qwen3_full_latest64_screen_rejection':('qwen3_4b','sc','screen_rejection',False,2048,64,0),
 'qwen3_full_latest64_8k_pv':('qwen3_4b','sc','pv',False,8192,64,0),
}

def main():
 p=argparse.ArgumentParser();p.add_argument('case',choices=CASES);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
 model,ffn,attn,legacy,L,T,seed=CASES[a.case];c,m=load(model,legacy=legacy)
 c.update(context_tokens=L,seed=seed);c['ffn']['mode']=ffn;c['ffn']['nonlinear_samples']=T;c['attention']['mode']=attn
 if a.output.exists():raise ValueError('immutable run destination exists')
 a.output.mkdir(parents=True)
 execution=source_record();execution['runner_sha256']=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
 execution['case']=a.case;write(a.output/'EXECUTION.json',execution)
 started=time.time();r=FullDecode(c,m).run();r['wall_seconds']=time.time()-started
 r['execution_commit']=execution['commit'];r['config_sha256']=hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()
 write(a.output/'RESULT.json',r)
 write(a.output/'MANIFEST.json',{'status':'completed','case':a.case,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(a.output.glob('*.json'))}})
 print(a.case,'completed',r['metrics']['TPOT_ms'],'ms/token','wall',r['wall_seconds'],flush=True)
if __name__=='__main__':main()
