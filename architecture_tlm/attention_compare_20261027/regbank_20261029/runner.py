"""One Slurm array element: matched RTL/DC/gate/PT, immutable source."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,re,time,shutil
S=Path(os.environ['RB_SOURCE']);R=Path(os.environ['RB_ROOT'])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_bytes((json.dumps(x,indent=2)+'\n').encode())
def call(args,d,log):
    with (d/log).open('wb') as f:r=subprocess.run(args,cwd=str(d),stdout=f,stderr=subprocess.STDOUT)
    text=(d/log).read_text(errors='replace')
    assert r.returncode==0 and not re.search(r'^\s*(?:Error:|Error-|Fatal:)',text,re.M),(args[0],log)
def main():
    m=json.loads((S/'SOURCE.json').read_text())
    for n,h in m['files'].items():assert sha(S/n)==h,n
    c=json.loads((S/'CASES.json').read_text())[int(os.environ['SLURM_ARRAY_TASK_ID'])]
    d=R/'results'/c['top'];d.mkdir(exist_ok=False)
    os.environ.update(RB_TOP=c['top'],RB_GATED=str(c['gated']),RB_LOAD='.02' if c['compare'] else '.002')
    save(d/'EXECUTION.json',dict(case=c,job=os.environ['SLURM_JOB_ID'],source_sha256=sha(S/'SOURCE.json'),
        db_sha256=sha(Path(os.environ['RB_DB'])),models_sha256=sha(Path(os.environ['RB_MODEL'])),start=time.time(),
        frequency_MHz=100,corner='SS',voltage=1.08,temperature=125,output_load_pF=float(os.environ['RB_LOAD']),
        input_delay_min_ns=.2,input_delay_max_ns=1.,setup_uncertainty_ns=.5,hold_uncertainty_ns=.05,sdf=False,spef=False,cts=False))
    checks=[];powers=[]
    try:
        dc=d/'dc';dc.mkdir()
        reuse=Path(os.environ['RB_REUSE_ROOT'])/'results'/c['top'] if os.environ.get('RB_REUSE_ROOT') else None
        reused=reuse is not None and (reuse/'COMPLETE.json').exists()
        if reused:
            old=json.loads((reuse/'COMPLETE.json').read_text())
            oldsrc=json.loads((reuse.parents[1]/'source/SOURCE.json').read_text())
            for name in ['bank.sv','tb.sv',c['top']+'.sv','dc.tcl','common.tcl']:
                assert m['files'][name]==oldsrc['files'][name],name
            assert old['netlist_sha256']==sha(reuse/'dc/mapped.v') and old['sdc_sha256']==sha(reuse/'dc/mapped.sdc')
            for p in (reuse/'dc').iterdir():
                if p.is_file():shutil.copyfile(str(p),str(dc/p.name))
            checks=old['checks']
            save(d/'REUSED.json',dict(directory=str(reuse),netlist_sha256=old['netlist_sha256'],sdc_sha256=old['sdc_sha256'],
                reason='Only PT root input slew correction; identical RTL/vectors/DC/netlist/SDC and previous RTL/gate proof reused'))
            os.environ.update(RB_NETLIST=str(dc/'mapped.v'),RB_SDC=str(dc/'mapped.sdc'))
        # RTL references the genuine ICG vendor model, even before synthesis.
        for phase in (['gate'] if reused else ['rtl','gate']):
            if phase=='gate' and not reused:
                call(['dc_shell','-f',str(S/'dc.tcl')],dc,'dc.log');assert (dc/'DC_COMPLETE').exists()
                inventory=[line.split('\t') for line in (dc/'inventory.tsv').read_text().splitlines()[1:]]
                assert sum(x[3]=='register' for x in inventory)==128*c['width']
                assert sum(x[3]=='icg' for x in inventory)==32*c['gated']
                os.environ.update(RB_NETLIST=str(dc/'mapped.v'),RB_SDC=str(dc/'mapped.sdc'))
            build=d/(phase+'_build');build.mkdir()
            inputs=[os.environ['RB_MODEL']]+([str(S/'bank.sv'),str(S/(c['top']+'.sv'))] if phase=='rtl' else [str(dc/'mapped.v')])
            if not reused:
                call(['vcs','-full64','-sverilog','-timescale=1ns/1ps','-top','tb','-o',str(build/'simv'),
                    '+define+RB_W='+str(c['width']),'+define+RB_CMP='+str(c['compare']),'+define+RB_TOP='+c['top']]+inputs+[str(S/'tb.sv')],build,'compile.log')
            for seed in [17,503,1009]:
                run=d/(phase+'_'+str(seed));run.mkdir()
                vec=S/'vectors'/c['top']/str(seed);meta=json.loads((vec/'META.json').read_text())
                assert sha(vec/'vectors.txt')==meta['vectors_sha256']
                cmd=[str(build/'simv'),'+VECTORS='+str(vec/'vectors.txt')]
                if phase=='gate':cmd+=['+VCD='+str(run/'activity.vcd')]
                if reused:
                    assert oldsrc['files']['vectors/'+c['top']+'/'+str(seed)+'/vectors.txt']==meta['vectors_sha256']
                    for name in ['sim.log','activity.vcd']:shutil.copyfile(str(reuse/(phase+'_'+str(seed))/name),str(run/name))
                    assert any(x['phase']=='gate' and x['seed']==seed and x['log_sha256']==sha(run/'sim.log') for x in checks)
                else:
                    call(cmd,run,'sim.log');assert 'PASS cycles=212' in (run/'sim.log').read_text()
                    checks.append(dict(phase=phase,seed=seed,cycles=212,checked=meta['counts']['checked'],compared_bits=meta['counts']['compared_bits'],log_sha256=sha(run/'sim.log')))
                if phase=='gate':
                    for win in meta['windows']:
                        p=run/win['name'];p.mkdir()
                        os.environ.update(RB_VCD=str(run/'activity.vcd'),RB_START=str(win['start']),RB_END=str(win['end']))
                        call(['pt_shell','-f',str(S/'pt.tcl')],p,'pt.log');assert (p/'PT_COMPLETE').exists()
                        powers.append(dict(seed=seed,window=win,directory=str(p.relative_to(d))))
                        save(d/'PROGRESS.json',dict(checks=len(checks),power_windows=len(powers)))
        save(d/'COMPLETE.json',dict(case=c,checks=checks,power=powers,netlist_sha256=sha(dc/'mapped.v'),sdc_sha256=sha(dc/'mapped.sdc')))
    except Exception as e:save(d/'FAILURE.json',dict(error=str(e)));raise
    print('COMPLETE',c['top'],flush=True)
if __name__=='__main__':main()
