"""Compile one macro-backed 128-bank array; check actual macro + mapped logic."""
import hashlib,json,os,re,subprocess
from pathlib import Path

S=Path(os.environ['SB_SOURCE']);R=Path(os.environ['SB_ARRAY_RESULTS'])
def save(p,x):p.write_bytes((json.dumps(x,indent=2)+'\n').encode())
def call(args,d,log):
    with (d/log).open('w') as f:p=subprocess.run(args,cwd=str(d),stdout=f,stderr=subprocess.STDOUT)
    if p.returncode:raise RuntimeError('%s failed: %s'%(args[0],d/log))
def main():
    R.mkdir(exist_ok=False)
    lib=Path(os.environ['SB_MACRO_LIB'])
    name=re.search(r'library\s*\(\s*"?([^\s"\)]+)',lib.read_text()).group(1)
    lc=R/'lc';lc.mkdir()
    db=lc/'macro.db';os.environ['SB_MACRO_DB']=str(db)
    (lc/'compile.tcl').write_text('read_lib {%s}\nwrite_lib %s -format db -output {%s}\nexit\n'%(lib,name,db))
    call(['lc_shell','-f','compile.tcl'],lc,'lc.log');assert db.exists()
    dc=R/'dc';dc.mkdir();call(['dc_shell','-f',str(S/'dc.tcl')],dc,'dc.log');assert (dc/'COMPLETE').exists()
    os.environ.update(SB_NETLIST=str(dc/'mapped.v'),SB_SDC=str(dc/'mapped.sdc'))
    checks=[];windows=[]
    for phase in ['rtl','gate']:
        compile_dir=R/phase;compile_dir.mkdir()
        inputs=[str(S/'tb.sv'),str(S/'banks.sv') if phase=='rtl' else str(dc/'mapped.v'),os.environ['SB_MACRO_MODEL']]
        if phase=='gate':inputs.append(os.environ['SB_STD_MODEL'])
        call(['vcs','-full64','-sverilog','-timescale=1ns/1ps','+notimingcheck','-debug_access+all','-top','tb','-o','simv']+inputs,compile_dir,'vcs.log')
        for prob in [1,16]:
            for seed in [17,503,1009]:
                d=compile_dir/('p%d_s%d'%(prob,seed));d.mkdir()
                call([str(compile_dir/'simv'),'+SEED=%d'%seed,'+PROB32=%d'%prob],d,'sim.log')
                assert 'PASS frames=256 checked_bits=32768' in (d/'sim.log').read_text()
                checks.append(dict(phase=phase,prob32=prob,seed=seed,frames=256,bits=32768,directory=str(d.relative_to(R))))
                save(R/'PROGRESS.json',dict(checks=checks,windows=windows))
                if phase=='gate':
                    for win,start,end in [('load',10,650),('sequential',650,1930),('independent',1930,3210)]:
                        p=d/win;p.mkdir()
                        os.environ.update(SB_VCD=str(d/'activity.vcd'),SB_START=str(start),SB_END=str(end))
                        call(['pt_shell','-f',str(S/'pt.tcl')],p,'pt.log');assert (p/'COMPLETE').exists()
                        windows.append(dict(prob32=prob,seed=seed,window=win,start_ns=start,end_ns=end,directory=str(p.relative_to(R))))
                        save(R/'PROGRESS.json',dict(checks=checks,windows=windows))
    save(R/'COMPLETE.json',dict(checks=checks,windows=windows,netlist_sha256=hashlib.sha256((dc/'mapped.v').read_bytes()).hexdigest()))
if __name__=='__main__':
    try:main()
    except Exception as e:
        if R.exists():save(R/'FAILURE.json',dict(error=str(e)))
        raise
