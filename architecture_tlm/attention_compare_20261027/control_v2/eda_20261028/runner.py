"""Python3.6-compatible frozen EDA driver. No credentials or private defaults."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

SNAP=Path(os.environ['AC_SNAPSHOT'])
ROOT=Path(os.environ['AC_RUN_ROOT'])

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_bytes((json.dumps(d,indent=2,ensure_ascii=False)+'\n').encode())
def call(args,work,log):
    with (work/log).open('wb') as f:
        p=subprocess.run(args,cwd=str(work),stdout=f,stderr=subprocess.STDOUT)
    if p.returncode:raise RuntimeError('command failed: '+str(args[0])+'; '+log)

def rows(path):
    return [line.split() for line in path.read_text(errors='replace').splitlines()
            if line.startswith('P ') or line.startswith('C ')]

def replay(case,work):
    top=case['top'];trace_entries=json.loads((SNAP/'vectors/TRACES.json').read_text())[top]
    # Exactly one successful baseline synthesis per top; no stale/failed fallback.
    candidates=[p.parent for p in (ROOT/'results').glob('*_dc_'+top+'/SYNTHESIS_COMPLETE.txt')]
    assert len(candidates)==1,candidates
    dc=candidates[0]
    original=json.loads((ROOT/'snapshots/v2/SOURCE.json').read_text())
    for f in (SNAP/'rtl').glob('*.sv'):
        assert digest(f)==original['files']['rtl/'+f.name]['sha256'],f
    os.environ.update(AC_NETLIST=str(dc/'mapped.v'),AC_SDC=str(dc/'mapped.sdc'))
    defs=['+define+AC_TOP='+top]+(['+define+AC_WINNER'] if case['kind']=='winner' else [])
    checks=[];power=[]
    for phase in ['rtl','gate']:
        build=work/('build_'+phase);build.mkdir()
        if phase=='rtl':
            inputs=[str(SNAP/'rtl'/f) for f in ['ac_scan.sv','ac_winner.sv','ac_rejection.sv','nr_singleton_tree.sv',top+'.sv']]
        else:inputs=[os.environ['AC_MODELS'],str(dc/'mapped.v')]
        command=['vcs','-full64','-sverilog','-timescale=1ns/1ps','+define+SYNTHESIS','-top','tb_eda','-o',str(build/'simv')]+defs+inputs+[str(SNAP/'tb_eda.sv')]
        call(command,build,'compile.log')
        for trace in trace_entries:
            run=work/(phase+'_'+trace['trace']);run.mkdir()
            vectors=SNAP/'vectors'/top/trace['trace']/'vectors.txt'
            golden=SNAP/'vectors'/top/trace['trace']/'golden.log'
            assert digest(vectors)==trace['vectors_sha256'] and digest(golden)==trace['golden_sha256']
            command=[str(build/'simv'),'+VECTORS='+str(vectors)]
            if phase=='gate':command+=['+VCD='+str(run/'activity.vcd')]
            call(command,run,'simulation.log')
            expected,actual=rows(golden),rows(run/'simulation.log')
            if expected!=actual:
                write(run/'MISMATCH.json',dict(expected_rows=len(expected),actual_rows=len(actual),
                    differences=[dict(i=i,expected=a,actual=b) for i,(a,b) in enumerate(zip(expected,actual)) if a!=b][:10]))
                raise RuntimeError('oracle mismatch '+phase+' '+trace['trace'])
            check=dict(phase=phase,trace=trace['trace'],cycles=trace['cycles'],status='pass',
                compared_edges=len(actual),log_sha256=digest(run/'simulation.log'),vectors_sha256=digest(vectors))
            checks.append(check);write(run/'VALIDATION.json',check)
            if phase=='gate':
                for window in trace['windows']:
                    pt=run/('pt_'+window['name']);pt.mkdir()
                    os.environ.update(AC_VCD=str(run/'activity.vcd'),AC_START_NS=str(window['start_ns']),AC_END_NS=str(window['end_ns']))
                    call(['pt_shell','-f',str(SNAP/'pt.tcl')],pt,'pt.log')
                    assert (pt/'POWER_COMPLETE.txt').exists()
                    power.append(dict(trace=trace['trace'],window=window,
                        slack=json.loads((pt/'SLACK.json').read_text()),directory=str(pt.relative_to(work))))
                    write(work/'PROGRESS.json',dict(functional_checks=len(checks),power_windows=len(power),last_trace=trace['trace']))
    write(work/'VALIDATION.json',dict(status='pass',checks=checks,power_windows=power,
        dc_netlist_sha256=digest(dc/'mapped.v'),dc_sdc_sha256=digest(dc/'mapped.sdc'),
        models_sha256=digest(Path(os.environ['AC_MODELS'])),sdf=False,spef=False,cts=False))

def main():
    manifest=json.loads((SNAP/'SOURCE.json').read_text())
    for name,meta in manifest['files'].items():
        assert digest(SNAP/name)==meta['sha256'],name
    stage,index=sys.argv[1],int(sys.argv[2])
    case=json.loads((SNAP/'CASES.json').read_text())['tops'][index]
    job=os.environ['SLURM_JOB_ID'];tag=os.environ.get('SLURM_ARRAY_TASK_ID','single')
    work=ROOT/'results'/(job+'_'+tag+'_'+stage+'_'+case['top']);work.mkdir(parents=True,exist_ok=False)
    os.environ.update(AC_TOP=case['top'],AC_RTL_DIR=str(SNAP/'rtl'),AC_FREQ_MHZ='100')
    write(work/'EXECUTION.json',dict(stage=stage,case=case,source_sha256=digest(SNAP/'SOURCE.json'),
        job=job,array_task=tag,frequency_MHz=100,input_transition_ns=.1,output_load_pF=.02,
        setup_uncertainty_ns=2,hold_uncertainty_ns=.1,clock_tree='ideal, no CTS',
        library_sha256=digest(Path(os.environ['AC_TARGET_DB'])),start_unix=time.time()))
    try:
        if stage=='dc':
            call(['dc_shell','-f',str(SNAP/'dc.tcl')],work,'dc.log')
            assert (work/'SYNTHESIS_COMPLETE.txt').exists()
        elif stage=='replay':replay(case,work)
        else:raise ValueError('stage not implemented '+stage)
        write(work/'STATUS.json',dict(status='completed',stage=stage,case=case,end_unix=time.time(),
              files={p.name:dict(bytes=p.stat().st_size,sha256=digest(p)) for p in work.iterdir() if p.is_file()}))
    except Exception as e:
        write(work/'FAILURE.json',dict(status='failed',error=str(e),stage=stage,case=case));raise
    print(json.dumps(dict(status='completed',case=case['top'],directory=str(work))))

if __name__=='__main__':main()
