"""Small end-to-end actual DRAMSys integration gate, no model-quality claim."""
import argparse, json, pathlib, sys, time
ROOT=pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from architecture_tlm.unified_v6.config import load
from architecture_tlm.unified_v6.memory_profiles import apply
from architecture_tlm.unified_v6.model import FullDecode
from architecture_tlm.unified_v6.run import write

def main():
 p=argparse.ArgumentParser();p.add_argument('--bridge',required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
 a.output.mkdir(parents=True,exist_ok=False);rows=[]
 for ffn,attn in [('bf16','exact'),('w8','exact'),('sc','exact'),('sc','screen_pv'),('sc','screen_rejection')]:
  for policy in ['balanced_ddr4','mature_ddr4']:
   c,m=load('qwen3_4b');m.update(hidden_size=256,intermediate_size=512,num_hidden_layers=2,num_attention_heads=4,num_key_value_heads=2,head_dim=64,vocab_size=1024)
   c.update(context_tokens=513,weight_chunk_bytes=32768,digital_weight_chunk_bytes=32768,trace_event_limit=20000)
   c['ffn']['mode']=ffn;c['attention'].update(mode=attn,candidate_blocks=4)
   name=ffn+'_'+attn+'_'+policy;out=a.output/name;out.mkdir()
   c=apply(c,policy,a.bridge,out/'dram');d=FullDecode(c,m);r=d.run()
   assert r['DRAM']['details']['status']=='finished'
   traffic=r['DRAM']['traffic'];assert sum(v for k,v in traffic.items() if k.endswith('_bursts'))==r['DRAM']['details']['burst_count']
   write(out/'RESULT.json',r)
   rows.append(dict(case=name,TPOT_ms=r['metrics']['TPOT_ms'],DRAM_bytes=sum(v for k,v in traffic.items() if k.endswith('_physical_bytes')),bursts=r['DRAM']['details']['burst_count'],source_frames=r['actions'].get('rng_frame'),FFN_activity=r['FFN_activity'],pipeline_counts={k:v.get('counts') for k,v in r.get('tile_pipeline',{}).items() if isinstance(v,dict)}))
   print(json.dumps(rows[-1]),flush=True)
 # Exact-data operators must keep all weights and K/V traffic; sampled-address timing may legitimately alter integrated-source schedules.
 for i in [0,2,4]:
  assert rows[i]['DRAM_bytes']==rows[i+1]['DRAM_bytes']
  assert rows[i]['FFN_activity']==rows[i+1]['FFN_activity']
 write(a.output/'RESULT.json',dict(status='completed',scope='small synthetic actual-DRAMSys integration gate',rows=rows))
if __name__=='__main__':main()
