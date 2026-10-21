"""Reproducible standalone source/logic transactions and full Attention smoke.

Uses synthetic workload unless --input supplies actual score rows. No PPL or
physical source is simulated. Outputs require an empty destination directory.
"""
import argparse
import copy
import hashlib
import json
import math
import random
import re
import subprocess
from pathlib import Path
from screen_parallel_tlm_v5 import sampler, ScreenParallelLocal, ScreenParallelDigital
from parallel_sampler_v5 import DEFAULT, ENERGY_ACTIONS, AREA_KEYS


def write(path,obj):
    with path.open('w',encoding='utf-8',newline='\n') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write('\n')


def standalone(options,rows,output):
    results=[]
    ids=[r['id'] for r in rows]
    if len(set(ids))!=len(ids) or any(not isinstance(i,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',i) for i in ids):
        raise ValueError('unique filesystem-safe row IDs required')
    for row in rows:
        n=len(row['logits'])
        for kind,budgets in (('winner_hold',(256,512,1024)),('corrected_rejection',(128,512))):
            for budget in budgets:
                cfg=copy.deepcopy(options)
                if kind=='corrected_rejection':
                    cfg.update(burn_updates=0,winner_shift=0.)
                for seed in (11,29,47):
                    m=sampler(kind,cfg,n)
                    ids,r=m.request(0,row['logits'],budget,random.Random(seed),(0,0,0),row['candidate_ids'])
                    # Full local IDs/timestamps retained in small raw files.
                    name='{}_{}_s{}_seed{}.json'.format(row['id'],kind,budget,seed)
                    costs=m.finish(r['end_ns'])
                    write(output/name,dict(input_id=row['id'],seed=seed,config=m.cfg,
                                          receipt=r,module=costs))
                    results.append(dict(input_id=row['id'],n=n,kind=kind,samples=budget,seed=seed,
                        elapsed_cycles=r['elapsed_cycles'],time_ns=r['end_ns'],
                        frames=r['actions']['proposal_frames'],biased_bit_draws=r['actions'].get('biased_bit_draws',0),
                        fair_bit_draws=r['actions'].get('fair_bit_draws',0),unique_V_addresses=len(set(ids)),
                        physical_energy_J=costs['physical_energy_J'],
                        physical_area_mm2=costs['physical_area_mm2'],result_file=name))
    return results


def attention(options,context,samples,small,variant,output,bridge=None,trace=None,prebuilt=False):
    from run_screen_ising_v4 import setup
    results=[]
    for kind in ('winner_hold','corrected_rejection'):
        cfg,evidence,shape=setup(context=context)
        if small:
            shape.update(num_hidden_layers=1,vocab_size=1024)
        opts=copy.deepcopy(options)
        if kind=='corrected_rejection':opts.update(burn_updates=0,winner_shift=0.)
        cfg['parallel_sampler_v5']=dict(kind=kind,options=opts)
        cfg['screen_ising_v4']['samples']=samples
        if prebuilt:cfg['attention_v3']['summary_initialization']='prefill_prebuilt'
        if trace:cfg['attention_v3']['trace_file']=str(trace.resolve())
        if bridge:
            cfg['external_memory'].update(backend='dramsys',bridge_executable=str(bridge.resolve()),
                configuration=str((Path(__file__).parent/'dramsys/ddr4_2ch_NoPowerDown.json').resolve()),
                max_pending=32,output_prefix=str((output/(kind+'_dram')).resolve()))
        cls=ScreenParallelDigital if variant=='digital_bf16' else ScreenParallelLocal
        model=cls(cfg,variant,evidence,shape)
        try:d=model.run()
        finally:
            if hasattr(model.ext,'close'):model.ext.close()
        # Addresses remain available; strip voluminous inherited host events in
        # this small smoke result. Module events can be enabled independently.
        d['attention_v5'].pop('events',None)
        d.update(actual_shape=shape,small=small)
        write(output/(kind+'.json'),d)
        results.append(dict(kind=kind,context=context,samples=samples,small=small,
            mean_TPOT_ms=d['metrics']['mean_TPOT_ms'],
            sampler_frames=d['attention_v5']['sampler']['actions'].get('proposal_frames',0),
            physical_energy_J=None,physical_area_mm2=None,
            sampler_energy_J=d['attention_v5']['sampler']['physical_energy_J']))
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--config',type=Path,default=Path(__file__).parent/'configs/parallel_sampler_v5.json')
    p.add_argument('--input',type=Path,help='JSON rows: id/logits/candidate_ids; optional real score input')
    p.add_argument('--attention',action='store_true')
    p.add_argument('--context',type=int,default=512)
    p.add_argument('--samples',type=int,default=16)
    p.add_argument('--small',action='store_true')
    p.add_argument('--variant',choices=['digital_bf16','fixed_sc_exact','dual_sc_sz'],default='digital_bf16')
    p.add_argument('--bridge',type=Path)
    p.add_argument('--trace',type=Path)
    p.add_argument('--prebuilt-summary',action='store_true')
    args=p.parse_args()
    if args.output.exists() and any(args.output.iterdir()):raise SystemExit('output must be empty')
    args.output.mkdir(parents=True,exist_ok=True)
    config=json.loads(args.config.read_text(encoding='utf-8'))
    if args.attention:
        result=attention(config['options'],args.context,args.samples,args.small,args.variant,
                         args.output,args.bridge,args.trace,args.prebuilt_summary)
        inputs=dict(kind='synthetic inherited attention logits' if args.trace is None else 'user supplied Attention trace',
                    trace_sha256=hashlib.sha256(args.trace.read_bytes()).hexdigest() if args.trace else None)
    else:
        rows=json.loads(args.input.read_text(encoding='utf-8'))['rows'] if args.input else [
            dict(id='synthetic_flat512',logits=[0.]*512,candidate_ids=list(range(512))),
            dict(id='synthetic_two_peak512',logits=[12.,12.]+[0.]*510,candidate_ids=list(range(512))),
        ]
        result=standalone(config['options'],rows,args.output)
        inputs=dict(kind='user supplied rows' if args.input else 'synthetic diagnostic, NOT actual Qwen queries',
                    sha256=hashlib.sha256(args.input.read_bytes()).hexdigest() if args.input else None)
    write(args.output/'SUMMARY.json',dict(results=result,input=inputs,
        code_repository='rayggxia-workspace/pbit-llm-qwen-baselines',
        code_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).parent).decode().strip(),
        config_sha256=hashlib.sha256(args.config.read_bytes()).hexdigest(),
        scope='configured LT timing and functional sampler; not PPL, PT or physical source measurement'))
    manifest={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(args.output.glob('*.json'))}
    manifest['sources']={x:hashlib.sha256((Path(__file__).parent/x).read_bytes()).hexdigest() for x in (
        'parallel_sampler_v5.py','winner_hold_tlm_v5.py','corrected_rejection_tlm_v5.py',
        'screen_parallel_tlm_v5.py','screen_ising_tlm_v4.py','run_parallel_sampler_v5.py')}
    write(args.output/'MANIFEST.json',manifest)
    print(json.dumps(dict(cases=len(result),output=str(args.output)),ensure_ascii=False))


if __name__=='__main__':main()
