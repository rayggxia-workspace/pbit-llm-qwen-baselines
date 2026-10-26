"""Run one frozen synthetic full-model scheduling case, never model quality."""
import argparse,hashlib,json,os,pathlib,platform,sys,time,traceback
ROOT=pathlib.Path(__file__).resolve().parents[2]
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
 from architecture_tlm.clock500_resource_20261026.profiles import configuration
 from architecture_tlm.clock500_resource_20261026.clock_gating import ClockGatedScheduler
 c,m=configuration(case,a.bridge,a.output/'dram')
 scheduler=ClockGatedScheduler(c['trace_event_limit'],core_period_ns=1e9/c['core_hz'],enabled=c['clock_gating']['enabled'],idle_threshold_cycles=c['clock_gating']['idle_cycles'],wake_cycles=c['clock_gating']['wake_cycles'],installed_resources=['sc:'+str(i) for i in range(c['ffn']['engines'])]+['mac','vector','locality_accumulator','ffn_SC_coefficient16_restore','ffn_SC_bucket_shift_reduce'] if c['ffn']['mode']=='sc' else ['mac','vector'])
 execution=dict(case=case,source=source,config_sha256=hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest(),matrix_sha256=digest(a.matrix),bridge_sha256=digest(pathlib.Path(a.bridge)),python=platform.python_version(),platform=platform.platform(),executable=sys.executable,argv=sys.argv,slurm_job=os.environ.get('SLURM_JOB_ID'),slurm_array=os.environ.get('SLURM_ARRAY_JOB_ID'),slurm_index=os.environ.get('SLURM_ARRAY_TASK_ID'),quality_evaluation=False)
 write(a.output/'EXECUTION.json',execution);d=None;start=time.monotonic()
 try:
  d=FullDecode(c,m,scheduler=scheduler)
  if 'local_pipeline' in c:
   from architecture_tlm.ffn_local_pipeline_20261025.model import LocalPipelineFFN
   d.ffn_latest=LocalPipelineFFN(d)
  r=d.run();r['clock_gating']=scheduler.clock_gating_report(r['metrics']['elapsed_ns']);r.update(execution_commit=source['commit'],case=case,wall_seconds=time.monotonic()-start)
  b=sum(v for k,v in r['DRAM']['traffic'].items() if k.endswith('_bursts'))
  assert r['DRAM']['details']['status']=='finished' and b==r['DRAM']['details']['burst_count']
  if c['ffn']['mode']=='sc':assert r['FFN_activity']['SC_64x64_tiles']==3*m['hidden_size']*m['intermediate_size']//4096*m['num_hidden_layers']
  write(a.output/'RESULT.json',r)
  keys=['model','config','metrics','phase_ns','resource_busy_ns','attention_activity','FFN_activity','actions','energy_J','unpriced_actions','SRAM','execution_commit','case','wall_seconds','numerical_status','tile_pipeline','tile_pipelines','digital_operand_contract','stage_busy_ns','wait_ns','clock_gating','random_interface']
  summary={k:r[k] for k in keys if k in r}
  summary['DRAM']={k:v for k,v in r['DRAM'].items() if k!='details'}
  detail=r['DRAM']['details'];summary['DRAM']['details']={k:detail[k] for k in ['status','burst_count','macro_requests','capacity_bytes','configuration_sha256','service_ms','max_DMA_latency_ns','power_at_system_end','bridge_features','last_done_ns','host_transactions','host_request_bytes','response_accept_delay_ps','energy_valid','energy_boundary','stats'] if k in detail}
  summary['FFN_contract']=dict(r['FFN_contract'])
  if 'weight_pipeline' in summary['FFN_contract']:
   summary['FFN_contract']['weight_pipeline']={k:v for k,v in summary['FFN_contract']['weight_pipeline'].items() if k not in ('events','tickets','trace')}
  summary['raw_result_sha256']=digest(a.output/'RESULT.json')
  summary['scope']='derived timing/activity summary; synthetic decode, no PPL or measured PPA'
  if 'local_pipeline' in summary['FFN_contract']:
   summary['FFN_contract']['local_pipeline']={k:v for k,v in summary['FFN_contract']['local_pipeline'].items() if k!='records'}
  write(a.output/'RESULT_SUMMARY.json',summary)
  files={q.name:dict(bytes=q.stat().st_size,sha256=digest(q)) for q in sorted(a.output.iterdir()) if q.is_file()}
  write(a.output/'MANIFEST.json',dict(status='completed',case=case,files=files))
  print(json.dumps(dict(status='completed',case=case['name'],TPOT_ms=r['metrics']['TPOT_ms'],wall_seconds=r['wall_seconds'])),flush=True)
 except BaseException:
  write(a.output/'FAILURE.json',dict(status='failed',case=case,traceback=traceback.format_exc(),wall_seconds=time.monotonic()-start))
  if d is not None and d.dram.bridge is not None:d.dram.bridge.close()
  raise
if __name__=='__main__':main()
