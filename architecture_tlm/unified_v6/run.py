"""Run or compare complete decode schedules; output directories are immutable."""
import argparse
import copy
import datetime
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    __package__ = 'architecture_tlm.unified_v6'
from .config import load
from .model import FullDecode, MODES
from .core import sha

ROOT = Path(__file__).resolve().parents[2]


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def source_record():
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    paths = list((ROOT/'architecture_tlm/unified_v6').rglob('*.py'))
    paths += list((ROOT/'architecture_tlm/unified_v6/configs').glob('*.json'))
    paths += list((ROOT/'architecture_tlm/random_service').rglob('*.py'))
    paths += [ROOT/'architecture_tlm/random_service/shared64_mapping.json']
    paths += [ROOT/'architecture_tlm/unified_v6/SOURCE_INDEX.json']
    paths += [ROOT/'architecture_tlm'/p for p in ['parallel_sampler_v5.py',
        'winner_hold_tlm_v5.py','corrected_rejection_tlm_v5.py',
        'attention_reference_v3.py','screen_ising_tlm_v4.py',
        'sram_cacti_calibration_v1.py','cacti_memory.py','dramsys_backend.py',
        'llama7b/runtime/results/sram_calibration_v1_20261016/calibration.json']]
    files = {}
    for p in sorted(paths):
        rel = p.relative_to(ROOT).as_posix()
        recorded = subprocess.check_output(['git','show',head+':'+rel],cwd=ROOT)
        if recorded != p.read_bytes():
            raise ValueError('commit exact execution bytes first: '+rel)
        files[rel] = dict(sha256=sha(p), bytes=p.stat().st_size)
    return dict(commit=head,files=files,python=platform.python_version(),
                platform=platform.platform(),command=sys.argv,
                created_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())


def compare(rows):
    reference = {}
    for row in rows:
        if row['ffn']=='bf16' and row['attention']=='exact':
            reference[(row['model'],row['context'],row['seed'])] = row
    for row in rows:
        ref = reference.get((row['model'],row['context'],row['seed']))
        if ref:
            row['time_ratio_to_BF16_exact'] = row['TPOT_ms']/ref['TPOT_ms']
            row['K_read_ratio'] = row['K_physical_bytes']/ref['K_physical_bytes']
            row['V_read_ratio'] = row['V_physical_bytes']/ref['V_physical_bytes']
    return rows


def compact(model, context, seed, ffn, attention, result):
    traffic = result['DRAM']['traffic']
    # Fused descriptors contain equal K and V sizes. Separate append/summary
    # traffic stays visible and is never claimed as a K/V-read saving.
    fused = traffic.get('KV_fused_physical_bytes',0)
    return dict(model=model,context=context,seed=seed,ffn=ffn,attention=attention,
        TPOT_ms=result['metrics']['TPOT_ms'],
        priced_subtotal_mJ=result['metrics']['priced_subtotal_mJ_per_token'],
        physical_energy_J=None,physical_area_mm2=None,
        K_physical_bytes=traffic.get('K_selected_physical_bytes',0)+fused//2,
        V_physical_bytes=traffic.get('V_sparse_union_physical_bytes',0)+fused//2,
        summary_bytes=sum(v for k,v in traffic.items() if k.startswith('summary_') and k.endswith('_physical_bytes')),
        SRAM_peak_bytes=result['SRAM']['reserved_peak_bytes'],
        SRAM_macro_area_mm2=result['SRAM']['area_mm2'],
        unpriced_action_types=len(result['unpriced_actions']),
        random_stream_storage_bytes=result['random_interface']['random_stream_SRAM_bytes'],
        rng_backend=result['random_interface']['backend'],
        rng_calibrated_endpoint_mJ=result['random_interface'].get('calibrated_endpoint_two_state_energy_J',0)*1000,
        rng_calibrated_endpoint_area_mm2=result['random_interface'].get('calibrated_endpoint_area_mm2',0),
        QK_positions=result['attention_activity']['QK_logical_positions'],
        possible_QK_positions=result['attention_activity']['possible_QK_positions'])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',choices=['qwen','qwen3_4b','llama1','llama2'],default='qwen3_4b')
    p.add_argument('--context',type=int,default=2048)
    p.add_argument('--decode',type=int,default=1)
    p.add_argument('--seed',type=int,default=0)
    p.add_argument('--ffn',choices=['bf16','w8','sc'],default='sc')
    p.add_argument('--attention',choices=MODES,default='screen_rejection')
    p.add_argument('--samples',type=int)
    p.add_argument('--ffn-samples',type=int)
    p.add_argument('--ffn-profile',choices=['latest','legacy'],default='latest')
    p.add_argument('--nonlinear-samples',type=int,choices=[32,64,128],default=64)
    p.add_argument('--strata',type=int)
    p.add_argument('--bins',type=int,default=4)
    p.add_argument('--trace',type=Path)
    p.add_argument('--config',type=Path,help='complete v6 config JSON override')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--suite',action='store_true',help='same-resource five/six-method comparison')
    p.add_argument('--models',nargs='+',choices=['qwen','qwen3_4b','llama1','llama2'])
    p.add_argument('--contexts',nargs='+',type=int)
    p.add_argument('--seeds',nargs='+',type=int,default=[0,1,2])
    p.add_argument('--include-winner',action='store_true')
    p.add_argument('--rng-backend',choices=['integrated_service','local_prng_interface'],default=None)
    a = p.parse_args(argv)
    if a.output.exists():
        raise ValueError('use a new output directory; preserve archived bytes')
    if a.context<1 or a.decode<1 or (a.ffn_samples is not None and a.ffn_samples<1):
        raise ValueError('positive context/decode/sampling required')
    sources = source_record()
    a.output.mkdir(parents=True)
    write(a.output/'EXECUTION.json',sources)
    rows=[]
    models=a.models or [a.model]
    contexts=a.contexts or [a.context]
    seeds=a.seeds if a.suite else [a.seed]
    modes=[('bf16','exact'),('w8','exact'),('sc','exact'),('sc','pv'),
           ('sc','screen_exact'),('sc','screen_pv'),('sc','screen_rejection')]
    if a.include_winner:
        modes.append(('sc','screen_winner'))
    if not a.suite:
        modes=[(a.ffn,a.attention)]
    for model in models:
        for context in contexts:
            for seed in seeds:
                for ffn,attention in modes:
                    cfg,shape=load(model,legacy=a.ffn_profile=='legacy')
                    if a.config:
                        cfg=json.loads(a.config.read_text(encoding='utf-8'))
                    cfg.update(context_tokens=context,decode_tokens=a.decode,seed=seed)
                    cfg['ffn'].update(mode=ffn,bins=a.bins)
                    if a.ffn_samples is not None:cfg['ffn']['samples']=a.ffn_samples
                    if a.strata is not None:cfg['ffn']['strata']=a.strata
                    if a.ffn_profile=='latest':cfg['ffn']['nonlinear_samples']=a.nonlinear_samples
                    cfg['attention'].update(mode=attention,samples=a.samples,trace_file=str(a.trace) if a.trace else None)
                    if a.rng_backend:cfg['random']['backend']=a.rng_backend
                    if cfg['random']['backend']=='integrated_service':cfg['random']['clock_hz']=cfg['core_hz']
                    identity='%s_L%d_seed%d_%s_%s'%(model,context,seed,ffn,attention)
                    result=FullDecode(cfg,shape).run()
                    result['execution_commit']=sources['commit']
                    result['config_sha256']=hashlib.sha256(json.dumps(cfg,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                    # Ordinary repeated baselines have identical scheduling but
                    # are executed, not silently inherited from old tables.
                    folder=a.output/model
                    folder.mkdir(exist_ok=True)
                    write(folder/(identity+'.json'),result)
                    rows.append(compact(model,context,seed,ffn,attention,result))
                    print(json.dumps(dict(case=identity,status='completed',TPOT_ms=result['metrics']['TPOT_ms'])),flush=True)
    rows=compare(rows)
    write(a.output/'SUMMARY.json',dict(scope='new synthetic conditional TLM, not PPL/PT/GPU',rows=rows,
        metrics_warning='priced subtotal coverage differs across methods; NEVER compare it as total energy',
        context='total causal length includes current query; prior context-1 KV tokens pre-exist',
        quality_warning='FFN B4/T32/K32 numerical evidence exists; new parallel samplers have local QKV evidence only, no inherited combined PPL'))
    manifest={str(p.relative_to(a.output)).replace('\\','/'):
        dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(a.output.rglob('*')) if p.is_file()}
    write(a.output/'ARTIFACT_MANIFEST.json',manifest)
    return rows


if __name__=='__main__':
    main()
