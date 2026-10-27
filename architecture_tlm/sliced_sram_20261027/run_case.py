"""Immutable representative Qwen3-4B layer experiment, actual DRAMSys."""
import argparse,hashlib,json,os,pathlib,platform,sys,time,traceback
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from architecture_tlm.scheduling_v2_20261027.profiles import configuration
from architecture_tlm.scheduling_v2_20261027.model import SchedulingDecode
from architecture_tlm.scheduling_v2_20261027.calendar import ReadyCalendar
from architecture_tlm.ffn_local_pipeline_20261025.model import LocalPipelineFFN
from architecture_tlm.unified_v6.run import write
from .model import SlicedDecode,configure


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('index',type=int);p.add_argument('--manifest',type=pathlib.Path,required=True)
    p.add_argument('--bridge',required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
    source=json.loads(a.manifest.read_text(encoding='utf-8'))
    for rel,v in source['files'].items():
        if digest(ROOT/rel)!=v['sha256']:raise ValueError('frozen source differs '+rel)
    if a.output.exists():raise ValueError('immutable output exists')
    a.output.mkdir(parents=True)
    modes=('legacy','descriptor','beats');kind=('sc','bf16')[a.index//3];mode=modes[a.index%3]
    case=dict(name=kind+'_'+mode,scope='one_layer',expanded_compute=True,expanded_sram=True,
        nonlinear_samples=128,clock_gating=False,ffn=kind,attention='screen_pv',early_next_dma=True,
        calendar=True,digital_prefill=True,cross_window_program=True,seed=0)
    c,m=configuration(case,a.bridge,a.output/'dram');c['trace_event_limit']=120
    if mode!='legacy':configure(c,mode=mode)
    scheduler=ReadyCalendar(120,core_period_ns=1e9/c['core_hz'],installed_resources=['mac','vector']+(['sc:'+str(i) for i in range(c['ffn']['engines'])] if kind=='sc' else []))
    execution=dict(case=case,source=source,config_sha256=hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest(),bridge_sha256=digest(pathlib.Path(a.bridge)),python=platform.python_version(),argv=sys.argv,
        slurm_job=os.environ.get('SLURM_JOB_ID'),slurm_array=os.environ.get('SLURM_ARRAY_JOB_ID'),slurm_index=os.environ.get('SLURM_ARRAY_TASK_ID'),model_quality=False,
        scope='one Qwen3-4B-shaped layer plus original full-vocabulary readout; not full36layer TPOT')
    write(a.output/'EXECUTION.json',execution);start=time.monotonic();d=None
    try:
        cls=SchedulingDecode if mode=='legacy' else SlicedDecode
        d=cls(c,m,scheduler=scheduler)
        if kind=='sc':d.ffn_latest=LocalPipelineFFN(d)
        r=d.run();r.update(case=case,execution_commit=source['commit'],wall_seconds=time.monotonic()-start)
        r['clock_gating']=scheduler.clock_gating_report(r['metrics']['elapsed_ns'])
        assert r['DRAM']['details']['status']=='finished'
        write(a.output/'RESULT.json',r)
        keys=['model','config','metrics','phase_ns','resource_busy_ns','attention_activity','FFN_activity','actions','energy_J','unpriced_actions','SRAM','execution_commit','case','wall_seconds','digital_operand_contract','stage_busy_ns','wait_ns','clock_gating','random_interface']
        summary={k:r[k] for k in keys if k in r}
        # Aggregates retain all actual counts; do not publish million-entry traces.
        summary['DRAM']={k:v for k,v in r['DRAM'].items() if k!='details'}
        detail=r['DRAM']['details'];summary['DRAM']['details']={k:detail[k] for k in ['status','burst_count','macro_requests','capacity_bytes','configuration_sha256','service_ms','energy_valid','energy_boundary','last_done_ns'] if k in detail}
        ff=dict(r['FFN_contract'])
        for k in ('weight_pipeline','local_pipeline'):
            if k in ff:ff[k]={a:b for a,b in ff[k].items() if a not in ('records','events','tickets','trace')}
        summary['FFN_contract']=ff;summary['raw_result_sha256']=digest(a.output/'RESULT.json');summary['scope']=execution['scope']
        write(a.output/'RESULT_SUMMARY.json',summary)
        files={q.name:dict(bytes=q.stat().st_size,sha256=digest(q)) for q in sorted(a.output.iterdir()) if q.is_file()}
        write(a.output/'MANIFEST.json',dict(status='completed',case=case,files=files))
        print(json.dumps(dict(status='completed',case=case['name'],elapsed_ms=r['metrics']['TPOT_ms'],wall_seconds=r['wall_seconds'])),flush=True)
    except BaseException:
        write(a.output/'FAILURE.json',dict(status='failed',case=case,traceback=traceback.format_exc()))
        if d is not None and d.dram.bridge is not None:d.dram.bridge.close()
        raise


if __name__=='__main__':main()
