"""Full-shape one-FFN sensitivity, not a full decoder result."""
import copy,hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from architecture_tlm.unified_v6.config import load,tiny
from architecture_tlm.unified_v6.model import FullDecode
from architecture_tlm.unified_v6.run import source_record,write

def main():
 out=ROOT/'architecture_tlm/unified_v6/results/current_ffn_20261024_v2/sensitivity';out.mkdir(parents=True,exist_ok=False)
 write(out/'EXECUTION.json',source_record());rows=[]
 for name in ('default','nl_T32','nl_T128','nl20words','restore8lanes','restore32lanes','arrayII2','one_engine'):
  c,m=load('qwen3_4b');m['num_hidden_layers']=1;c['attention']['mode']='exact';f=c['ffn']
  if name=='nl_T32':f['nonlinear_samples']=32
  if name=='nl_T128':f['nonlinear_samples']=128
  if name=='nl20words':f['rng_nl']['words_per_cycle']=20
  if name=='restore8lanes':f['restore_lanes']=8
  if name=='restore32lanes':f['restore_lanes']=32
  if name=='arrayII2':f['sample_II_cycles']=2
  if name=='one_engine':f['engines']=1
  d=FullDecode(c,m);t=d.ffn_latest.gate_up(0,0);gu=t
  t=d.ffn_latest.encode_nonlinear(t);enc=t-gu
  t=d.ffn_latest.down(t,0);down=t-gu-enc;t=d.ffn_latest.final(t)
  rows.append(dict(case=name,scope='one complete FFN D2560 F9728; not end-to-end',
      core_cycles=t/d.period,elapsed_ms=t/1e6,gu_ms=gu/1e6,encoding_ms=enc/1e6,down_ms=down/1e6,
      config=c,contract=d.ffn_latest.report(),dram_traffic=dict(d.dram.traffic),
      stage_busy_ns=dict(d.s.by_stage),unpriced_actions=dict(d.e.missing)))
  print(name,t/1e6,flush=True)
 # Three independent seed fixtures exercise all retained Attention modes at tiny geometry.
 checks=[]
 for seed in (0,1,2):
  for mode in ('exact','pv','screen_pv','screen_winner','screen_rejection'):
   c,m=tiny();from architecture_tlm.unified_v6.ffn_latest import defaults
   c['ffn'].update(defaults());c['attention']['mode']=mode;c['seed']=seed
   c['random']['backend']='integrated_service';r=FullDecode(c,m).run()
   assert abs(sum(r['phase_ns'].values())-r['metrics']['elapsed_ns'])<1e-5
   checks.append(dict(seed=seed,attention=mode,elapsed_ns=r['metrics']['elapsed_ns'],
       sampled_addresses=r['row_receipts'],random_sha256=r['random_interface']['frame_output_sha256']))
 write(out/'RESULT.json',dict(scope='8 one-FFN sensitivities and 15 tiny whole-decoder fixtures',rows=rows,seed_checks=checks))
 write(out/'MANIFEST.json',dict(status='completed',files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob('*.json'))}))
if __name__=='__main__':main()
