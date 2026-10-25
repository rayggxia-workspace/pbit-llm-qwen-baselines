"""Run one frozen synthetic full-model scheduling case, never model quality."""
import argparse,hashlib,json,os,pathlib,platform,sys,time,traceback
ROOT=pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from architecture_tlm.unified_v6.config import load
from architecture_tlm.unified_v6.memory_profiles import apply
from architecture_tlm.unified_v6.model import FullDecode
from architecture_tlm.unified_v6.run import write

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('index',type=int);p.add_argument('--matrix',type=pathlib.Path,required=True);p.add_argument('--manifest',type=pathlib.Path,required=True);p.add_argument('--bridge',required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
 source=json.loads(a.manifest.read_text(encoding='utf-8'))
 for rel,record in source['files'].items():
  if digest(ROOT/rel)!=record['sha256']:raise ValueError('source bytes differ '+rel)
 rows=json.loads(a.matrix.read_text(encoding='utf-8'))['cases'];case=rows[a.index]
 if a.output.exists():raise ValueError('immutable run path exists')
 a.output.mkdir(parents=True)
 c,m=load('qwen3_4b');E=case.get('engines',8);chunk=case.get('digital_chunk',65536)
 c.update(context_tokens=case['context'],seed=case['seed'],digital_weight_chunk_bytes=chunk,weight_chunk_bytes=max(chunk,E*4096))
 c['ffn'].update(mode=case['ffn'],engines=E,local_weight_bytes=E*4096)
 c['attention']['mode']=case['attention']
 policy=case['policy'];c=apply(c,'balanced_ddr4' if policy=='legacy' else 'mature_ddr4',a.bridge,a.output/'dram')
 if policy=='shared_serial':c['dram']['scatter_gather']=False
 if policy=='legacy_sg':c['schedule_policy']='legacy'
 if 'sg_max_spans' in case:c['dram']['sg_max_spans']=case['sg_max_spans']
 execution=dict(case=case,source=source,config_sha256=hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest(),matrix_sha256=digest(a.matrix),bridge_sha256=digest(pathlib.Path(a.bridge)),python=platform.python_version(),platform=platform.platform(),executable=sys.executable,argv=sys.argv,slurm_job=os.environ.get('SLURM_JOB_ID'),slurm_array=os.environ.get('SLURM_ARRAY_JOB_ID'),slurm_index=os.environ.get('SLURM_ARRAY_TASK_ID'),quality_evaluation=False)
 write(a.output/'EXECUTION.json',execution);d=None;start=time.monotonic()
 try:
  d=FullDecode(c,m);r=d.run();r.update(execution_commit=source['commit'],case=case,wall_seconds=time.monotonic()-start)
  b=sum(v for k,v in r['DRAM']['traffic'].items() if k.endswith('_bursts'))
  assert r['DRAM']['details']['status']=='finished' and b==r['DRAM']['details']['burst_count']
  if case['ffn']=='sc':assert r['FFN_activity']['SC_64x64_tiles']==3*m['hidden_size']*m['intermediate_size']//4096*m['num_hidden_layers']
  write(a.output/'RESULT.json',r)
  keys=['model','config','metrics','phase_ns','resource_busy_ns','attention_activity','FFN_activity','actions','energy_J','unpriced_actions','SRAM','execution_commit','case','wall_seconds','numerical_status','tile_pipeline','tile_pipelines','digital_operand_contract']
  summary={k:r[k] for k in keys if k in r}
  summary['DRAM']={k:v for k,v in r['DRAM'].items() if k!='details'}
  detail=r['DRAM']['details'];summary['DRAM']['details']={k:detail[k] for k in ['status','burst_count','macro_requests','capacity_bytes','configuration_sha256','service_ms','max_DMA_latency_ns','power_at_system_end','bridge_features','last_done_ns'] if k in detail}
  summary['FFN_contract']=dict(r['FFN_contract'])
  if 'weight_pipeline' in summary['FFN_contract']:
   summary['FFN_contract']['weight_pipeline']={k:v for k,v in summary['FFN_contract']['weight_pipeline'].items() if k not in ('events','tickets','trace')}
  summary['raw_result_sha256']=digest(a.output/'RESULT.json')
  summary['scope']='derived timing/activity summary; synthetic decode, no PPL or measured PPA'
  write(a.output/'RESULT_SUMMARY.json',summary)
  files={q.name:dict(bytes=q.stat().st_size,sha256=digest(q)) for q in sorted(a.output.iterdir()) if q.is_file()}
  write(a.output/'MANIFEST.json',dict(status='completed',case=case,files=files))
  print(json.dumps(dict(status='completed',case=case['name'],TPOT_ms=r['metrics']['TPOT_ms'],wall_seconds=r['wall_seconds'])),flush=True)
 except BaseException:
  write(a.output/'FAILURE.json',dict(status='failed',case=case,traceback=traceback.format_exc(),wall_seconds=time.monotonic()-start))
  if d is not None and d.dram.bridge is not None:d.dram.bridge.close()
  raise
if __name__=='__main__':main()
