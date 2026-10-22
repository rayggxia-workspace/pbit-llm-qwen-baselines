"""Bounded execution matrix, with per-case evidence and explicit failures."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import traceback

from . import ffn,attention
from .run import run_case,synthetic_fixture,digest,json_write,source_provenance


def worker(case):
    path=Path(case['fixture']) if case.get('fixture') else None
    bundle=json.loads(path.read_text(encoding='utf-8')) if path else synthetic_fixture()
    if case.get('candidate_count'):
        context=len(bundle['attention']['k'])
        count=case['candidate_count']
        bundle['attention']['candidate_ids']=[i*(context-1)//(count-1) for i in range(count)]
        bundle['provenance']={**bundle.get('provenance',{}),'candidate_override':count,
                              'candidate_rule':'uniform deterministic spread including endpoints; no learned screening'}
    cls=ffn.FFNConfig if case['operator']=='ffn' else attention.AttentionConfig
    try:
        result=run_case(case['operator'],bundle,cls(**case['config']),case['output'],
            fixture_sha256=digest(path.read_bytes()) if path else None,write_trace=case.get('trace',True))
        return {'name':case['name'],'passed':True,'summary':str(Path(case['name'])/'summary.json'),
                **{k:result[k] for k in ('operator','config','fixture_sha256','latency_ns','operations','numerical_validation',
                                       'mode_equivalence','equivalence_payload_sha256','output_memory_sha256')}}
    except Exception as error:
        folder=Path(case['output']);folder.mkdir(parents=True,exist_ok=True)
        failure={'name':case['name'],'passed':False,'error':repr(error),'traceback':traceback.format_exc(),
                 'case':case,'source':source_provenance()}
        json_write(folder/'FAILURE.json',failure)
        return failure


def make_cases(suite,fixture_dir,output):
    cases=[]
    layers=(None,) if suite=='smoke' else (0,12,23)
    seeds=(0,) if suite=='smoke' else (0,1,2)
    profiles=[(4,32,32),(2,32,32),(4,16,16),(4,64,64)]
    def add(operator,layer,config,label,trace=True,candidate_count=None):
        name=('synthetic' if layer is None else f'qwen_layer{layer}')+'_'+label
        cases.append({'name':name,'operator':operator,'config':config,'output':str(output/name),
            'fixture':str(fixture_dir/f'qwen_layer{layer}.json') if layer is not None else None,
            'trace':trace,'candidate_count':candidate_count})
    for layer in layers:
        for seed in seeds:
            for bins,samples,strata in profiles:
                add('ffn',layer,dict(bins=bins,samples=samples,strata=strata,seed=seed),
                    f'ffn_B{bins}T{samples}K{strata}_seed{seed}',trace=seed==0)
            for mode in ('exact','pv','winner','rejection'):
                if mode=='exact' and seed: continue
                add('attention',layer,dict(mode=mode,samples=32,seed=seed),
                    f'{mode}_N128_S32_seed{seed}' if layer is not None else f'{mode}_S32_seed{seed}',trace=seed==0)
    if suite=='real':
        for mode in ('winner','rejection'):
            add('attention',12,dict(mode=mode,samples=512,seed=0),f'{mode}_N512_S512_seed0',candidate_count=512)
    return cases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',choices=('smoke','real'),required=True)
    parser.add_argument('--fixture-dir',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=1)
    args=parser.parse_args()
    if args.output.exists(): raise FileExistsError('choose a fresh result directory')
    if args.suite=='real' and args.fixture_dir is None: parser.error('real suite requires --fixture-dir')
    if not 1<=args.workers<=8: parser.error('workers must be 1..8 within the actual scheduler allocation')
    args.output.mkdir(parents=True)
    cases=make_cases(args.suite,args.fixture_dir,args.output)
    json_write(args.output/'CASES.json',cases)
    results=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for future in as_completed([pool.submit(worker,case) for case in cases]):
            result=future.result();results.append(result)
            print(json.dumps({'case':result['name'],'passed':result['passed'],'latency_ns':result.get('latency_ns'),
                              'error':result.get('error')}),flush=True)
            json_write(args.output/'PARTIAL.json',sorted(results,key=lambda x:x['name']))
    summary={'suite':args.suite,'scope':'real cropped FFN and single query; not full model, PPL or physical PPA',
             'source':source_provenance(),'cases':sorted(results,key=lambda x:x['name']),
             'passed':sum(r['passed'] for r in results),'failed':sum(not r['passed'] for r in results)}
    json_write(args.output/'SUMMARY.json',summary)
    artifacts=[{'path':p.relative_to(args.output).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p.read_bytes())}
               for p in sorted(args.output.rglob('*')) if p.is_file()]
    json_write(args.output/'ARTIFACT_MANIFEST.json',{'artifacts':artifacts})
    if summary['failed']: raise SystemExit(1)


if __name__=='__main__': main()
