import argparse
import hashlib
import json
import random
from pathlib import Path
from reference import evaluate,accumulate,pack

ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--quick',action='store_true');a=ap.parse_args()
    out=ROOT/'vectors';out.mkdir(exist_ok=True);rng=random.Random(20261016);counts={}
    with (out/'conversions.hex').open('w') as full,(out/'pipeline.hex').open('w') as pipe:
        for kind in range(18):
            rows=[]
            def emit(data,aux=0,coef=0,ea=0,eb=0):
                value,flags=evaluate(kind,data,aux,coef,ea,eb)
                line=f'{kind:x} {data:016x} {aux:08x} {coef:06x} {ea&65535:04x} {eb&65535:04x} {value:016x} {flags:x}\n'
                full.write(line)
                if len(rows)<256:pipe.write(line)
                rows.append(1)
            if kind in (0,2,7):
                for ea in ((-16,-8,0) if kind==0 else (0,)):
                    for data in range(0,65536,257 if a.quick else 1):emit(data,ea=ea)
            elif kind in (1,3,6,11,15,16,17):
                edge=[0,0x80000000,1,0x007fffff,0x00800000,0x3f000000,0x3f800000,
                    0x3f808000,0x3f818000,0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,
                    0x7fc00000,0x7f800001,0x00800001,0x80800000]
                for data in edge:
                    for aux in edge:emit(data,aux,ea=-8)
                for _ in range(1000 if a.quick else (100000 if kind==11 else 16000)):
                    data=rng.getrandbits(32);aux=rng.getrandbits(32)
                    if kind==11 and rng.randrange(4)==0:aux=data^0x80000000
                    emit(data,aux,ea=rng.choice([-32768,-200,-149,-126,-32,-16,-8,0,8,100,32767]))
            else:
                w=32 if kind in (4,8,9,12,14) else 64
                edge=[0,1,2,3,5,127,128,255,256,(1<<(w-1))-1,1<<(w-1),(1<<w)-1]
                for data in edge:
                    for e in (-32768,-200,-149,-126,-32,-16,-8,-1,0,1,8,100,127,32767):
                        emit(data,coef=0xffffff,ea=e,eb=-24)
                for _ in range(1000 if a.quick else 10000):
                    emit(rng.getrandbits(w),coef=rng.getrandbits(24),
                        ea=rng.choice([-220,-150,-149,-140,-126,-80,-32,-24,-16,-8,-1,0,1,24,90,150]),
                        eb=rng.choice([-64,-48,-24,-8,0,24]))
            counts[str(kind)]=len(rows)
    frames=[([(100000000,1,0),(1,1,0),(-100000000,1,0)],-24)]
    for length in (1,14,76):
        for common in (-8,-16,-24,-32,-48):
            for _ in range(3 if a.quick else 12):
                terms=[(rng.randrange(-33000000,33000001),rng.randrange(1<<23,1<<24),
                    rng.choice([-48,-40,-32,-24])) for _ in range(length)]
                frames.append((terms,common))
    different=0
    with (out/'accum.hex').open('w') as f:
        for terms,common in frames:
            refs=[accumulate(terms,common,None)]+[accumulate(terms,common,w) for w in (32,40,64)]
            if refs[0][0]!=refs[-1][0]:different+=1
            for i,(n,m,e) in enumerate(terms):
                exp=' '.join(f'{v:08x} {flags:x}' for v,flags in refs)
                f.write(f'{int(i==0):x} {int(i==len(terms)-1):x} {n&0xffffffff:08x} {m:06x} {e&65535:04x} {common&65535:04x} {exp}\n')
    meta=dict(seed=20261016,quick=a.quick,conversions=counts,total=sum(counts.values()),
        accumulation_frames=len(frames),float_vs_fixed64_different_frames=different,
        cancellation_example=dict(float=accumulate(frames[0][0],-24,None)[0],
            fixed64=accumulate(frames[0][0],-24,64)[0],explanation='1e8 + 1 - 1e8'),
        warning='differences are arithmetic-order/quantization effects, NOT PPL results',
        sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('*.hex')})
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(meta,indent=2))
if __name__=='__main__':main()
