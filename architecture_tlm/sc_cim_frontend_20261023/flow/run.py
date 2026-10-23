"""DC -> mapped VCS oracle -> scalar VCD -> PT, with evidence and small archives."""
import argparse
import gzip
import json
import os
import shutil
import subprocess
import sys
import tarfile
import traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sim'))
from vectors import make
from wave import clip
from scalar_vcd import digest,scalarize,verify_pt
from summarize import window_summary,write_csv


def save(path,value):
    path.write_bytes((json.dumps(value,indent=2)+'\n').encode('utf-8'))


def compress(path):
    before=digest(path)
    dest=path.with_suffix(path.suffix+'.gz')
    with path.open('rb') as src,gzip.open(str(dest),'wb') as dst:shutil.copyfileobj(src,dst)
    import hashlib
    h=hashlib.sha256()
    with gzip.open(str(dest),'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    if h.hexdigest()!=before:raise ValueError('Compressed waveform verification failed')
    save(path.with_suffix('.compression.json'),dict(original_sha256=before,gzip_sha256=digest(dest),gzip_file=dest.name))
    path.unlink()


def archive(out):
    files=sorted(p for p in out.rglob('*') if p.is_file() and p.suffix in ['.rpt','.txt','.json','.log','.tsv','.csv']
                 and not set(p.relative_to(out).parts)&{'csrc','simv.daidir','WORK'} and p.name!='RESULT_INDEX.json')
    save(out/'RESULT_INDEX.json',{p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p)) for p in files})
    target=out.parent/(out.name+'_reports.tar.gz')
    with tarfile.open(str(target),'w:gz') as tar:
        for p in files+[out/'RESULT_INDEX.json']:tar.add(str(p),arcname=out.name+'/'+p.relative_to(out).as_posix())
    print('REPORT_ARCHIVE={} SHA256={}'.format(target,digest(target)),flush=True)


def execute(out):
    env=os.environ.copy();env['CIM_ROOT']=str(ROOT);env['PPA_SOURCE']=str(ROOT/'flow')
    kind,n,m,t,k,ext=[int(env['CIM_'+s]) for s in ['KIND','N','M','T','K','EXT']]
    seeds=[int(s) for s in env.get('CIM_SEEDS','1,17,74565').split(',')]
    if kind not in range(4) or env['PPA_CORNER'] not in ['ss','tt'] or ext not in [0,1]:raise ValueError('Bad kind/corner/ext')
    if min(n,m,t,k)<=0 or t>256 or k>256 or t%k or 256%k:raise ValueError('Bad geometry/T/K')
    if not seeds or len(seeds)!=len(set(seeds)) or any(not 0<s<2**32 for s in seeds):raise ValueError('Invalid/duplicate seeds')
    config={key:env[key] for key in env if key.startswith(('CIM_','PPA_','SLURM_')) or key in ['STD_DB','STD_MODEL','BUF_REF','LOAD_PF','INPUT_SLEW_NS','EDA_CORES']}
    save(out/'CONFIG.json',config)
    save(out/'SOURCE.json',json.loads((ROOT/'SOURCE_MANIFEST.json').read_text()))
    save(out/'INPUT_BINDING.json',dict(source_manifest_sha256=digest(ROOT/'SOURCE_MANIFEST.json'),
         config_sha256=digest(out/'CONFIG.json'),libraries={key:dict(path=env[key],sha256=digest(Path(env[key]))) for key in ['STD_DB','STD_MODEL']}))
    commands=[]
    def run(cmd,cwd,log):
        print('RUN {} {}'.format(cwd.name,log),flush=True)
        commands.append(dict(command=cmd,cwd=str(cwd),log=log))
        save(out/'COMMANDS.json',commands)
        with (cwd/log).open('w') as f:
            f.write('COMMAND '+repr(cmd)+'\n');f.flush()
            p=subprocess.run(cmd,cwd=str(cwd),env=env,stdout=f,stderr=subprocess.STDOUT)
        commands[-1]['exit_code']=p.returncode;save(out/'COMMANDS.json',commands)
        if p.returncode:raise RuntimeError('Exit {}: {}'.format(p.returncode,cwd/log))
    net=out/'net';net.mkdir();run(['dc_shell','-f',str(ROOT/'flow/dc.tcl')],net,'dc.log')
    if not (net/'SYNTH_COMPLETE').exists():raise RuntimeError('DC did not complete')
    env['NET_DIR']=str(net)
    g=out/'gate';g.mkdir()
    cmd=['vcs','-full64','-sverilog','-top','tb','-o',str(g/'simv'),'+define+MAPPED']
    cmd+=['+define+%s=%d'%p for p in [('KIND',kind),('N',n),('M',m),('T',t),('K',k),('EXT',ext)]]
    run(cmd+[str(net/'mapped.v'),env['STD_MODEL'],str(ROOT/'sim/tb.sv')],g,'compile.log')
    prefix='tb/'+['full','source','gates','qprobe'][kind]+'/dut';env['STRIP_PATH']=prefix
    wanted=[]
    if kind<=1:
        wanted=['clk','seed_ready','seed_error','frame_ready','ext_ready','sample_valid','done']
        wanted+=['sample_bits[%d]'%i for i in range(n)]+['threshold[%d]'%i for i in range(8)]
    if kind in [0,2,3]:wanted+=['%s[%d]'%('local_q' if kind==3 else 'products',i) for i in range(n*m*8)]
    power=out/'power';power.mkdir();windows=[]
    for seed in seeds:
        sg=g/('seed%d'%seed);sg.mkdir();v=make(sg/'vectors',n,m,t,k,ext,kind,seed)
        raw=sg/'raw.vcd'
        run([str(g/'simv'),'+DIR='+str(sg/'vectors'),'+CYCLES='+str(v['cycles']),'+VCD='+str(raw)],sg,'sim.log')
        if 'CIM_PASS' not in (sg/'sim.log').read_text():raise RuntimeError('Gate functional comparison failed')
        save(sg/'FUNCTIONAL_PASS.json',dict(seed=seed,cycles=v['cycles'],vectors_sha256=digest(sg/'vectors/vectors.json')))
        selected=[w for w in v['windows'] if env.get('CIM_SMOKE')!='1' or w['name'] in ['active_2','idle_2']]
        for w in selected:
            d=power/('seed%d_%s'%(seed,w['name']));d.mkdir()
            r=clip(raw,d/'clipped.vcd',w['start_ns'],w['end_ns'])
            s=scalarize(d/'clipped.vcd',d/'scalar.vcd',prefix=prefix,wanted=wanted)
            if r['xz_signals'] or s['duration_ns']!=w['end_ns']-w['start_ns']:raise ValueError('Invalid activity window')
            save(d/'ACTIVITY.json',dict(window=w,clip=r,scalar=s));env['ACTIVITY_VCD']=str(d/'scalar.vcd')
            run(['pt_shell','-f',str(ROOT/'flow/pt.tcl')],d,'pt.log')
            if not (d/'POWER_CALCULATED').exists():raise RuntimeError('PT did not complete')
            save(d/'ACTIVITY_CHECK.json',verify_pt(s,d/'output_activity.tsv'))
            row=dict(name=d.name,kind=kind,corner=env['PPA_CORNER'],n=n,m=m,t=t,k=k,external_rng=ext,seed=seed,
                     mode=w['mode'],duration_ns=s['duration_ns'],frames=w['completed_frames'],accepted_samples=w['accepted_samples'],
                     setup_slack_ns=float((d/'setup_slack_ns.txt').read_text()),hold_slack_ns=float((d/'hold_slack_ns.txt').read_text()))
            row.update(window_summary(d,row));save(d/'WINDOW.json',row);windows.append(row)
            save(out/'SUMMARY.json',windows);write_csv(out,windows)
            compress(d/'clipped.vcd');compress(d/'scalar.vcd')
        compress(raw)
    save(out/'COMPLETE.json',dict(status='calculated_requires_report_review',window_count=len(windows),
         functional='PASS',boundary='Prelayout standard-cell only; no SRAM storage, upstream storage, counter, CTS/SPEF/SDF or physical RNG.'))


def main():
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,required=True);x=a.parse_args()
    out=x.out.resolve();out.mkdir(parents=True,exist_ok=False)
    try:execute(out)
    except Exception:
        (out/'failure.txt').write_bytes(traceback.format_exc().encode('utf-8'));raise
    finally:archive(out)


if __name__=='__main__':main()
