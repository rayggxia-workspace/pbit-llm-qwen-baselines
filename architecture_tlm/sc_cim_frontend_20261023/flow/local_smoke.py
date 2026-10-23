"""Small real RTL/wave checks; no licensed EDA and no physical buffer model."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sim'))
from vectors import make
from wave import clip
from scalar_vcd import scalarize,digest


def main():
    a=argparse.ArgumentParser()
    a.add_argument('--iverilog',required=True);a.add_argument('--vvp',required=True)
    a.add_argument('--ivl-lib',required=True);a.add_argument('--out',type=Path,required=True)
    x=a.parse_args();out=x.out.resolve();out.mkdir(parents=True,exist_ok=False)
    x.iverilog=str(Path(x.iverilog).resolve());x.vvp=str(Path(x.vvp).resolve());x.ivl_lib=str(Path(x.ivl_lib).resolve())
    records=[]
    for kind in range(4):
        d=out/('kind%d'%kind);d.mkdir();v=make(d/'vectors',4,2,32,32,0,kind,17)
        exe=d/'sim.vvp'
        cmd=[x.iverilog,'-B',x.ivl_lib,'-g2012','-s','tb','-o',str(exe),'-DN=4','-DM=2','-DT=32','-DK=32','-DEXT=0','-DKIND=%d'%kind]
        cmd += [str(p) for p in sorted((ROOT/'rtl').glob('*.sv'))]+[str(ROOT/'sim/tb.sv')]
        for name,argv in [('compile',cmd),('simulation',[x.vvp,'-M',x.ivl_lib,str(exe),'+DIR='+str(d/'vectors'),'+CYCLES='+str(v['cycles']),'+VCD='+str(d/'raw.vcd')])]:
            p=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True,timeout=60,cwd=str(d))
            (d/(name+'.log')).write_bytes((repr(argv)+'\n'+p.stdout).encode('utf-8'))
            if p.returncode or (name=='simulation' and 'CIM_PASS' not in p.stdout):raise RuntimeError(p.stdout)
        wanted=[]
        if kind<=1:wanted=['clk','seed_ready','seed_error','frame_ready','ext_ready','sample_valid','done']+['sample_bits[%d]'%i for i in range(4)]+['threshold[%d]'%i for i in range(8)]
        if kind in [0,2,3]:wanted+=['%s[%d]'%('local_q' if kind==3 else 'products',i) for i in range(64)]
        windows=[]
        for w in v['windows']:
            c=d/(w['name']+'.vcd');s=d/(w['name']+'_scalar.vcd')
            clip(d/'raw.vcd',c,w['start_ns'],w['end_ns'])
            r=scalarize(c,s,prefix='tb/'+['full','source','gates','qprobe'][kind]+'/dut',wanted=wanted)
            if r['xz_signals'] or r['duration_ns']!=w['end_ns']-w['start_ns']:raise ValueError('Bad window')
            windows.append(dict(name=w['name'],signals=len(r['expected_activity']),duration_ns=r['duration_ns']))
        records.append(dict(kind=kind,cycles=v['cycles'],windows=windows))
    result=dict(status='RTL_AND_WAVE_PASS_NOT_PPA',cases=records,
                source_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in sorted((ROOT/'rtl').glob('*.sv'))})
    (out/'VALIDATION.json').write_bytes((json.dumps(result,indent=2)+'\n').encode('utf-8'))
    print('PASS: 4 RTL cases, 48 X/Z-clean scalarized windows; no DC/VCS/PT')


if __name__=='__main__':main()
