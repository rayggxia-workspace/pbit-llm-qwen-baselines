"""DC -> zero-delay VCS functional check -> clipped/scalar VCD -> PT.
No proprietary library is included. Original outputs remain in a new directory.
"""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sim'))
from vectors import make
from wave import clip
from scalar_vcd import scalarize,verify_pt

def save(p,x):
    with p.open('w',encoding='utf-8',newline='\n') as f:json.dump(x,f,indent=2);f.write('\n')

def main():
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,required=True);x=a.parse_args()
    out=x.out.resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env['CIM_ROOT']=str(ROOT);env['PPA_SOURCE']=str(ROOT/'flow')
    kind,n,m,t,k,ext=[int(env['CIM_'+s]) for s in ['KIND','N','M','T','K','EXT']]
    if kind not in range(4) or env['PPA_CORNER'] not in ['ss','tt']:raise ValueError('bad kind/corner')
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and p.suffix in ['.py','.sv','.tcl','.sh']}
    save(out/'SOURCE.json',hashes)
    save(out/'CONFIG.json',{key:env[key] for key in env if key.startswith(('CIM_','PPA_')) or key in ['STD_DB','STD_MODEL','BUF_REF','LOAD_PF','INPUT_SLEW_NS']})
    def run(cmd,cwd,log):
        with (cwd/log).open('w') as f:
            f.write('COMMAND '+repr(cmd)+'\n');f.flush()
            subprocess.run(cmd,cwd=str(cwd),env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    net=out/'net';net.mkdir();run(['dc_shell','-f',str(ROOT/'flow/dc.tcl')],net,'dc.log')
    if not (net/'SYNTH_COMPLETE').exists():raise RuntimeError('DC did not complete')
    env['NET_DIR']=str(net)
    g=out/'gate';g.mkdir();v=make(g/'vectors',n,m,t,k,ext,kind,1)
    cmd=['vcs','-full64','-sverilog','-top','tb','-o',str(g/'simv'),'+define+MAPPED']
    cmd+=['+define+%s=%d'%p for p in [('KIND',kind),('N',n),('M',m),('T',t),('K',k),('EXT',ext)]]
    run(cmd+[str(net/'mapped.v'),env['STD_MODEL'],str(ROOT/'sim/tb.sv')],g,'compile.log')
    run([str(g/'simv'),'+DIR='+str(g/'vectors'),'+CYCLES='+str(v['cycles']),'+VCD='+str(g/'raw.vcd')],g,'sim.log')
    if 'CIM_PASS' not in (g/'sim.log').read_text():raise RuntimeError('gate functional comparison failed')
    prefix='tb/'+['full','source','gates','qprobe'][kind]+'/dut';env['STRIP_PATH']=prefix
    if kind<=1:
        wanted=['clk','seed_ready','seed_error','frame_ready','ext_ready','sample_valid','done']
        wanted+=['sample_bits[%d]'%i for i in range(n)]+['threshold[%d]'%i for i in range(8)]
    else:wanted=[]
    if kind in [0,2,3]:wanted+=['%s[%d]'%('local_q' if kind==3 else 'products',i) for i in range(n*m*8)]
    windows=[]
    for w in v['windows']:
        d=out/w['name'];d.mkdir()
        r=clip(g/'raw.vcd',d/'clipped.vcd',w['start_ns'],w['end_ns'])
        s=scalarize(d/'clipped.vcd',d/'scalar.vcd',prefix=prefix,wanted=wanted)
        save(d/'ACTIVITY.json',dict(window=w,clip=r,scalar=s));env['ACTIVITY_VCD']=str(d/'scalar.vcd')
        run(['pt_shell','-f',str(ROOT/'flow/pt.tcl')],d,'pt.log')
        if not (d/'POWER_CALCULATED').exists():raise RuntimeError('PT did not complete')
        save(d/'ACTIVITY_CHECK.json',verify_pt(s,d/'output_activity.tsv'));windows.append(w)
    save(out/'COMPLETE.json',dict(status='power_calculated_requires_report_review',windows=windows,
         boundary='SNG/drive/raw gate only; no SRAM/accumulator/CTS/layout. Inspect slack, coverage and out-of-table warnings.'))
    print('Complete:',out)

if __name__=='__main__':main()
