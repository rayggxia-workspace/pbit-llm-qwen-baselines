"""Compare original global pool with hierarchical v1; does not overwrite baselines."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from system_decode import DecodeModel,load

ROOT=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--config',type=Path,default=ROOT/'configs/rng_hierarchy_v1.json')
    p.add_argument('--variant',choices=('dual_sc_sz','fixed_sc_exact'),default='dual_sc_sz')
    p.add_argument('--small',action='store_true',help='one layer / small vocabulary; same FFN dimensions')
    p.add_argument('--output',type=Path,default=ROOT/'results/rng_hierarchy_v1')
    p.add_argument('--bridge',type=Path,help='optional existing DRAMSys bridge executable')
    p.add_argument('--dramsys-config',type=Path,default=ROOT/'dramsys/ddr4_2ch_NoPowerDown.json')
    args=p.parse_args()
    cfg,evidence,shape=load()
    if args.small:shape.update(num_hidden_layers=1,vocab_size=1024);cfg['context_tokens']=128
    args.output.mkdir(parents=True,exist_ok=True)
    hierarchy=json.loads(args.config.read_text(encoding='utf-8'))
    results={}
    for architecture in ('global_pool','hierarchical_v1'):
        c=copy.deepcopy(cfg)
        c['rng']['architecture']=architecture
        if architecture=='hierarchical_v1':c['rng_hierarchy']=hierarchy
        if args.bridge:
            c['external_memory'].update(backend='dramsys',bridge_executable=str(args.bridge.resolve()),
                configuration=str(args.dramsys_config.resolve()),max_pending=32,
                output_prefix=str((args.output/architecture).resolve()))
        model=DecodeModel(c,args.variant,evidence,shape)
        try:r=model.run()
        finally:
            if hasattr(model.ext,'close'):model.ext.close()
        r['experiment_scope']='small one-layer integration' if args.small else 'full configured decode'
        r['actual_shape']=shape
        r['source_hashes']['rng_hierarchy_config']=hashlib.sha256(args.config.read_bytes()).hexdigest()
        (args.output/(architecture+'.json')).write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
        results[architecture]=r
        print(architecture,json.dumps(r['metrics']),flush=True)
    a,b=results.values()
    if a['actions']!=b['actions']:raise AssertionError('compute work changed')
    if a['traffic']!=b['traffic']:raise AssertionError('memory/replay traffic changed')
    summary=dict(scope='scenario comparison, NOT measured PPA or new numerical inference',
        cost_status=hierarchy['cost_status'],small=args.small,variant=args.variant,
        backend='DRAMSys' if args.bridge else 'simplified Link',
        operation_counts_identical=True,memory_traffic_identical=True,
        metrics={k:r['metrics'] for k,r in results.items()},
        speedup=a['metrics']['mean_TPOT_ms']/b['metrics']['mean_TPOT_ms'],
        rng=b['rng_hierarchy'])
    (args.output/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
