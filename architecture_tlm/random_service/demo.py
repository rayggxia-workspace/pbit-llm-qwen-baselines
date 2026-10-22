"""Self-contained FFN replay / full-width 512-candidate source demonstrations."""
import argparse
import json
from pathlib import Path
from . import Endpoint, SeedWords, RandomNetwork, RandomPort, FullFrameArray, SigmoidTable

def run(source, reseed_cycles=100_000_000):
    ports={'ffn':Endpoint('lfsr32',reseed_cycles),
           'gf_experiment':Endpoint('lfsr32_shared64',reseed_cycles)}
    ports.update({'attn%02d'%i:Endpoint('bivium',reseed_cycles) for i in range(26)})
    n=RandomNetwork(ports,source)
    f=RandomPort(n,'ffn')
    f.command(1)
    q=[4*i for i in range(64)]
    first=[f.shared_input(q)['bits'] for _ in range(32)]
    f.command(2)
    second=[f.shared_input(q)['bits'] for _ in range(32)]
    f.command(3)
    assert first==second
    array=FullFrameArray(n,['attn%02d'%i for i in range(26)],512)
    lut=SigmoidTable()
    thresholds=lut.lookup([-i/64 for i in range(512)])
    frames=[array.draw_q(thresholds) for _ in range(8)]
    gf=RandomPort(n,'gf_experiment')
    gf.frame()
    n.tick()  # explicit sink drain
    r=n.report()
    r.update(ffn_replay_equal=True,ffn_frontend_operations=dict(f.counts),
             attention=dict(frames=len(frames),width=512,unused_native_lanes_per_frame=8,
                            first_valid_cycle=frames[0]['valid_cycle'],
                            last_valid_cycle=frames[-1]['valid_cycle'],lut_sha256=lut.sha256,
                            response='q/256 LUT approximation; not ideal sigmoid'),
             physical_entropy_certified=False,quality_ppl=None)
    return r

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--mode',choices=['os','fixture','trace'],default='os')
    ap.add_argument('--fixture-seed',type=int)
    ap.add_argument('--trace',type=Path)
    ap.add_argument('--word-interval',type=int,default=100)
    args=ap.parse_args()
    raw=json.loads(args.trace.read_text(encoding='utf-8')) if args.trace else {}
    src=SeedWords(args.mode,args.word_interval,10,args.fixture_seed,
                  raw.get('words'),raw.get('provenance'))
    if args.output.exists():raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    r=run(src)
    args.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:r[k] for k in ('cycles','elapsed_ns','ffn_replay_equal','attention','seed_source')},indent=2))

if __name__=='__main__':main()

