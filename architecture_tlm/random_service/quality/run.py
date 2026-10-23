"""Reproducible layer diagnostics using unchanged RandomNetwork and cores."""
import argparse, hashlib, json, platform, sys, time
from pathlib import Path
import numpy as np
from ..model import Endpoint, RandomNetwork, SeedWords
from ..backends import PROFILES
from .metrics import bit_metrics, word_metrics, probes
from .prepare_physical import digest


def write(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def condition(bits,mode):
    b=np.asarray(bits,dtype=np.uint8)
    if mode=='raw':return b.copy()
    if mode=='vn':
        pair=b[:len(b)//2*2].reshape(-1,2)
        return pair[pair[:,0]!=pair[:,1],0].copy()
    if mode=='xor8':return np.bitwise_xor.reduce(b[:len(b)//8*8].reshape(-1,8),axis=1)
    raise ValueError(mode)


def pack(bits):
    b=np.asarray(bits,dtype=np.uint8);n=len(b)//32
    return (b[:n*32].reshape(n,32).astype(np.uint64)*(np.uint64(1)<<np.arange(32,dtype=np.uint64))).sum(axis=1).tolist()


def synthetic(kind,seed,n=180000):
    rng=np.random.default_rng(seed)
    if kind=='iid_fixture':return rng.integers(0,2,n,dtype=np.uint8)
    if kind=='biased_markov':
        candidate=rng.random(n)<.6;refresh=rng.random(n)<.1
        x=np.empty(n,dtype=np.uint8);x[0]=candidate[0]
        for i in range(1,n):x[i]=candidate[i] if refresh[i] else x[i-1]
        return x
    raise ValueError(kind)


def simulate(kind,words,frames,period,duplicate=False):
    width=PROFILES[kind]['state_bits'];beats=(width+31)//32
    if duplicate:words=words[:beats]*2  # deliberate same initial packet; no reseed
    source=SeedWords(mode='trace',interval_cycles=1,startup_cycles=0,words=words,
        provenance='quality replay; pre-collected diagnostic material, NOT a physical entropy approval')
    net=RandomNetwork({'a':Endpoint(kind,period),'b':Endpoint(kind,period)},source)
    arrays={'a':[],'b':[]};cycles=[];failure=None
    for cycle in range(frames*8+2000):
        # Atomic requests align accepted sample indices AND wall-clock edges.
        ready=all(p.signals()['req_ready'] and not net.ingress[k].valid for k,p in net.ports.items())
        req={k:[128]*p.profile['lanes'] for k,p in net.ports.items()} if ready else {}
        try:out=net.tick(req)
        except RuntimeError as e:failure=str(e);break
        if out['a']['accepted'] != out['b']['accepted']:raise AssertionError('unpaired requests')
        if out['a']['accepted']:
            cycles.append(cycle)
            for k in arrays:arrays[k].append(out[k]['words'])
        if len(arrays['a'])==frames:break
    else:failure='bounded experiment timed out (including zero-seed starvation)'
    report=net.report();events=report['seed_events']
    material=[e['seed_hex'] for e in events if not e['rejected']]
    seed_stats=dict(loads=len(material),unique_states=len(set(material)),
        repeated_state_loads=len(material)-len(set(material)),
        zero_rejections=sum(e['rejected'] for e in events),
        bus_words=len(source.transcript),state_bits=width,
        caveat='small seed sample; number of distinct states is not an entropy estimate')
    a=np.array(arrays['a'],dtype=np.uint8);b=np.array(arrays['b'],dtype=np.uint8)
    result=dict(status='complete' if len(a)==frames else 'incomplete',failure=failure,
        counts={k:dict(p.counts) for k,p in net.ports.items()},cycles=net.cycle,
        seed_stats=seed_stats,seed_events=events)
    if len(a)>128:
        result.update(output=word_metrics(a),probes=probes(a,b))
    return result,a,b,np.asarray(cycles,dtype=np.int64)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--physical',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--raw-out',type=Path,required=True)
    ap.add_argument('--frames',type=int,default=4096);args=ap.parse_args()
    if args.frames<256 or args.frames%128:raise ValueError('frames must be >=256 and divisible by 128')
    if args.out.exists() or args.raw_out.exists():raise FileExistsError('immutable output already exists')
    args.out.mkdir(parents=True);args.raw_out.mkdir(parents=True)
    root=Path(__file__).resolve().parents[2]
    source_paths=list(Path(__file__).parent.glob('*.py'))+[root/'random_service'/x for x in ('backends.py','model.py','shared64_mapping.json')]
    # root here is architecture_tlm, bind the exact files executed, not a guessed Git commit.
    manifest={str(p.relative_to(root.parent)):digest(p) for p in sorted(source_paths)}
    config=dict(frames=args.frames,seeds=[401,503,607],physical_sampling_s=5e-7,
        conditioners=['raw','vn'],backends=list(PROFILES),reseed_cycles=[0,1024],
        clock_ns=10,physical_time_mode='pre-collected trace; 1 qualified word per clock is a diagnostic replay setting',
        baseline_commit='6966739a5223680888bf0315f7bb4f73423a1ae6',
        application_scope='synthetic fixed-threshold AND / K32 shared-input W8 toy reduction / proposal frame, no LLM')
    write(args.out/'CONFIG.json',config);write(args.out/'SOURCE_MANIFEST.json',manifest)
    physical=json.loads((args.physical/'manifest.json').read_text(encoding='utf-8'))
    if digest(args.physical/'bits.npz')!=physical['npz_sha256']:raise ValueError('physical bit cache changed')
    inputs=[];physical_metrics=[]
    with np.load(args.physical/'bits.npz') as data:
        for r in physical['records']:
            bits=data[r['key']]
            if hashlib.sha256(bits.tobytes()).hexdigest()!=r['bits_sha256']:raise ValueError('bits changed')
            for interval in (1e-7,5e-7,1e-6,2e-6):
                stride=round(interval/r['dt_s']);sample=bits[::stride]
                physical_metrics.append(dict(key=r['key'],interval_s=interval,metrics=bit_metrics(sample)))
            inputs.append((r['kind'],r['seed'],bits[::round(5e-7/r['dt_s'])].copy(),'Spectre replay'))
    for name in ('iid_fixture','biased_markov'):
        for seed in config['seeds']:inputs.append((name,seed,synthetic(name,seed),'synthetic control'))
    stages=[];rows=[];started=time.monotonic()
    for name,seed,raw,evidence in inputs:
        for mode in config['conditioners']:
            conditioned=condition(raw,mode)
            stages.append(dict(source=name,seed=seed,evidence=evidence,conditioner=mode,
                raw=bit_metrics(raw),conditioned=bit_metrics(conditioned),
                retained_ratio=len(conditioned)/len(raw),raw_samples=len(raw),
                conditioned_samples=len(conditioned),packed_words=len(conditioned)//32,
                tail_bits_discarded=len(conditioned)%32,
                health_note='monitored only; no qualified-health hardware or NIST compliance claimed'))
            for kind in config['backends']:
                for period in config['reseed_cycles']:
                    case=f'{name}-{seed}-{mode}-{kind}-r{period}'
                    result,a,b,cycles=simulate(kind,pack(conditioned),args.frames,period)
                    npz=args.raw_out/(case+'.npz');np.savez_compressed(npz,a=a,b=b,accepted_cycles=cycles)
                    rows.append(dict(case_id=case,source=name,seed=seed,evidence=evidence,conditioner=mode,
                        backend=kind,reseed_cycles=period,duplicate_seed=False,
                        raw_artifact=dict(path=str(npz),sha256=digest(npz),bytes=npz.stat().st_size),**result))
        print(name,seed,len(rows),round(time.monotonic()-started,1),flush=True)
    for seed in config['seeds']:
        for kind in config['backends']:
            result,a,b,cycles=simulate(kind,pack(synthetic('iid_fixture',seed)),args.frames,0,True)
            case=f'duplicate-{seed}-{kind}';npz=args.raw_out/(case+'.npz')
            np.savez_compressed(npz,a=a,b=b,accepted_cycles=cycles)
            rows.append(dict(case_id=case,source='duplicate_seed_control',seed=seed,evidence='intentional fault',
                conditioner='raw',backend=kind,reseed_cycles=0,duplicate_seed=True,
                raw_artifact=dict(path=str(npz),sha256=digest(npz),bytes=npz.stat().st_size),**result))
    write(args.out/'PHYSICAL_INPUT.json',physical)
    write(args.out/'STAGES.json',dict(physical_sampling=physical_metrics,conditioning=stages))
    write(args.out/'RESULTS.json',dict(config_sha256=digest(args.out/'CONFIG.json'),
        source_manifest_sha256=digest(args.out/'SOURCE_MANIFEST.json'),
        environment=dict(python=sys.version,numpy=np.__version__,platform=platform.platform()),
        cases=rows,seconds=time.monotonic()-started,
        scope='diagnostic only; no entropy-rate certification, PPL, new Spectre/RTL/PPA; deterministic PRNG adds no physical entropy'))
    print(json.dumps(dict(cases=len(rows),complete=sum(r['status']=='complete' for r in rows),seconds=time.monotonic()-started)))

if __name__=='__main__':main()
