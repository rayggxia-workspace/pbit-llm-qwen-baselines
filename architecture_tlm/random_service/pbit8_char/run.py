"""Portable functional/activity characterization. Python >=3.8; no EDA launch."""
import argparse
from decimal import Decimal, localcontext, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import sys
from generate_lut import ROOT, render, probability

TOPS = ['pbit_compare8_lt', 'pbit_compare8_q256', 'pbit_sigmoid8_lut',
        'pbit_sigmoid8_reg', 'pbit_sample8_reg']
MODES = ['idle', 'fixed50', 'random', 'sweep', 'cadence64']

def save(p, x):
    p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode())

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def golden(code):
    with localcontext() as c:
        c.prec=80
        p=Decimal(256)/(1+(-Decimal(code)/8).exp())
        return int(p.to_integral_value(rounding=ROUND_HALF_UP))

def vectors(out, mode, seed, cycles=4096):
    rng=random.Random(seed)
    rows=[]; r,q,d=0,128,0
    for i in range(cycles+16):
        enabled = mode!='idle' and (mode!='cadence64' or i%64==0)
        if enabled:
            r=rng.randrange(256)
            q=rng.randrange(257)
            d=rng.randrange(-128,128)
            if mode=='fixed50': q,d=128,0
            if mode=='sweep': q,d=i%257,(i%256)-128
        rows.append((r,q,d,int(enabled),golden(d)))
    (out/'vectors.txt').write_bytes((''.join(' '.join(map(str,row))+'\n' for row in rows)).encode())
    return dict(mode=mode,seed=seed,cycles=cycles,warmup=16,
                enabled=sum(row[3] for row in rows[16:]),vectors_sha256=sha(out/'vectors.txt'),
                stimulus='Python MT19937 synthetic external input, not DUT PRNG/physical entropy',
                input_rule='hold all inputs when disabled; fixed50 changes r8 only')

def call(cmd, cwd, log):
    p=subprocess.run(list(map(str,cmd)),cwd=str(cwd),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
    log.write_bytes(p.stdout)
    if p.returncode: raise RuntimeError(str(log)+': '+p.stdout.decode(errors='replace'))
    return p.stdout.decode(errors='replace')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--iverilog',default='iverilog')
    ap.add_argument('--vvp',default='vvp')
    ap.add_argument('--ivl-dir',type=Path)
    ap.add_argument('--vectors-only',action='store_true')
    ap.add_argument('--mode',choices=MODES,default='random')
    ap.add_argument('--seed',type=int,default=17)
    a=ap.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    if a.vectors_only:
        save(out/'CONFIG.json',vectors(out,a.mode,a.seed));return
    if (ROOT/'rtl/pbit_sigmoid8_lut.sv').read_text()!=render(): raise AssertionError('Regenerate LUT')
    values=[golden(c) for c in range(-128,128)]
    assert values==[probability(c) for c in range(-128,128)]
    assert values==sorted(values) and values[128]==128 and values[0]==0 and values[-1]==256
    assert all(values[128-c]+values[128+c]==256 for c in range(128))
    # Existing service is optional in standalone ZIP; explicitly report whether checked.
    repo=ROOT.parents[2];sys.path.insert(0,str(repo))
    service_match=False
    if (ROOT.parent/'service.py').is_file():
        from architecture_tlm.random_service.service import SigmoidTable
        table=SigmoidTable(.125)
        assert values==[table.values[c] for c in range(-128,128)]
        service_match=True
    rtl=sorted((ROOT/'rtl').glob('*.sv'))
    iv=[a.iverilog]+(['-B',str(a.ivl_dir)] if a.ivl_dir else [])
    vv=[a.vvp]+(['-M',str(a.ivl_dir)] if a.ivl_dir else [])
    (out/'golden.hex').write_bytes((''.join('%03x\n'%golden(u if u<128 else u-256) for u in range(256))).encode())
    call(iv+['-g2012','-s','tb_exhaustive','-o',out/'exhaustive.vvp']+rtl+[ROOT/'tb/tb_exhaustive.sv'],out,out/'compile_exhaustive.log')
    log=call(vv+[out/'exhaustive.vvp'],out,out/'exhaustive.log')
    assert 'EXHAUSTIVE_PASS' in log
    runs=[]
    for case,top in enumerate(TOPS):
        exe=out/(top+'.vvp')
        call(iv+['-g2012','-DCASE='+str(case),'-s','tb_activity','-o',exe]+rtl+[ROOT/'tb/tb_activity.sv'],out,out/(top+'_compile.log'))
        for seed in (17,503,1009):
            for mode in MODES:
                d=out/(top+'_'+mode+'_'+str(seed));d.mkdir()
                cfg=vectors(d,mode,seed)
                log=call(vv+[exe],d,d/'simulation.log')
                m=re.search(r'ACTIVITY_PASS cycles=(\d+) enabled=(\d+) start_ns=([\d.]+) end_ns=([\d.]+)',log)
                if not m: raise AssertionError(log)
                n,en,start,end=map(float,m.groups())
                assert n==cfg['cycles'] and en==cfg['enabled'] and end-start==40960
                cfg.update(top=top,case=case,clock_ns=10.0,start_ns=start,end_ns=end,
                           duration_ns=end-start,vcd_sha256=sha(d/'activity.vcd'),functional='pass',
                           power='not_run',area_um2=None,total_uW=None)
                save(d/'CONFIG.json',cfg);runs.append(cfg)
    sources={p.relative_to(ROOT).as_posix():sha(p) for p in ROOT.rglob('*')
             if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.sv','.tcl')}
    save(out/'SOURCE_MANIFEST.json',sources)
    save(out/'RESULT.json',dict(status='RTL_FUNCTIONAL_ONLY',runs=runs,
        exhaustive_compare_inputs=131072,exhaustive_lut_addresses=256,exhaustive_lut_random_pairs=65536,
        decimal_oracle_precision=80,existing_service_all_256_match=service_match,
        source_manifest_sha256=sha(out/'SOURCE_MANIFEST.json'),synthesis='not_run',sta='not_run',power='not_run'))
    print('PASS: exhaustive compare/LUT, %d activity cases, %d measured cycles; PPA not run' % (len(runs),sum(c['cycles'] for c in runs)))

if __name__=='__main__':main()
