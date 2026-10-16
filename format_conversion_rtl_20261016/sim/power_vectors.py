"""Finite, deterministic representative stimuli; no RTL RNG cost included."""
import json
import random
from pathlib import Path
from reference import evaluate,accumulate

ROOT=Path(__file__).resolve().parents[1]
def main():
    out=ROOT/'vectors';out.mkdir(exist_ok=True);rng=random.Random(41016)
    for k in range(18):
        with (out/f'power_case{k}.hex').open('w') as f:
            for i in range(4096):
                if k in (0,2,7):data=(rng.randrange(2)<<15)|(rng.randrange(120,133)<<7)|rng.getrandbits(7)
                elif k in (1,3,6,11,15,16,17):data=(rng.randrange(2)<<31)|(rng.randrange(120,135)<<23)|rng.getrandbits(23)
                else:data=rng.randrange(-33000000,33000001)&((1<<64)-1)
                aux=(rng.randrange(2)<<31)|(rng.randrange(120,135)<<23)|rng.getrandbits(23)
                coef=0xc17a23 # immutable positive coefficient for standalone probes
                ea=-5 if k in (0,1,2) else -8 if k==3 else -24
                if k in (8,9,12):ea=-40
                if k==10:ea=-8
                if k in (15,16):ea=-9
                if k==17:data=(rng.randrange(115,127)<<23)|rng.getrandbits(23);ea=-32
                eb=-24
                expected,flags=evaluate(k,data,aux,coef,ea,eb)
                f.write(f'0 0 {data:016x} {aux:08x} {coef:06x} {ea&65535:04x} {eb&65535:04x} {expected:016x} {flags:x}\n')
    for length in (14,76):
        with (out/f'power_accum{length}.hex').open('w') as f:
            for _ in range(64):
                terms=[(rng.randrange(-33000000,33000001),rng.randrange(1<<23,1<<24),-40) for i in range(length)]
                refs=[accumulate(terms,-24,None)]+[accumulate(terms,-24,w) for w in (32,40,64)]
                for i,(n,m,e) in enumerate(terms):
                    extra=' '.join(f'{v:016x} {flags:x}' for v,flags in refs)
                    f.write(f'{int(i==0)} {int(i==length-1)} {n&0xffffffff:016x} 00000000 {m:06x} {e&65535:04x} ffe8 {extra}\n')
    (out/'power_stimulus.json').write_text(json.dumps(dict(seed=41016,
        nature='synthetic finite representative inputs, NOT captured Qwen traces',
        probability_cases='fixed S=8 for A8, varying finite inputs',
        scaled_cases='positive 24bit coefficient; coeff_exp=-40, common_lsb=-24',
        no_rtl_rng=True,accumulation_lengths=[14,76]),indent=2)+'\n')
if __name__=='__main__':main()
