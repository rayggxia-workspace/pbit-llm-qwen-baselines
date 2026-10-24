"""DC -> independent-oracle gate simulation -> windowed PT. New directory only."""
import argparse,gzip,hashlib,json,os,re,subprocess,sys,tarfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sim'))
from generate import make
from wave import clip
from scalar_vcd import scalarize,verify_pt
from summarize import window_summary,write_csv
from xz_audit import prepare_activity
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def archive_wave(p,out):
    # Only this new run's VCDs; verify a lossless gzip before removing plaintext.
    p=p.resolve();assert out in p.parents and p.suffix=='.vcd'
    before=sha(p);gz=p.with_suffix('.vcd.gz')
    with p.open('rb') as src,gzip.open(str(gz),'wb') as dst:
        for b in iter(lambda:src.read(1048576),b''):dst.write(b)
    h=hashlib.sha256()
    with gzip.open(str(gz),'rb') as src:
        for b in iter(lambda:src.read(1048576),b''):h.update(b)
    assert h.hexdigest()==before
    rec=dict(original=str(p),original_sha256=before,gzip_sha256=sha(gz),original_bytes=p.stat().st_size,gzip_bytes=gz.stat().st_size)
    p.unlink();return rec
def main():
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,required=True);x=a.parse_args()
    out=x.out.resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();arch=int(env['SC_ARCH']);m=int(env['SC_M']);t=int(env['SC_T']);pipe=int(env['SC_PIPE'])
    assert arch in (0,1) and m in (1,8,64) and t in (16,32,64) and pipe in (0,1)
    period=float(env['SC_PERIOD_NS']);assert period>0
    sw=(64*t*128).bit_length()+1
    profiles=env.get('SC_PROFILES','mixed,sparse,dense,zero').split(',')
    seeds=[int(s) for s in env.get('SC_SEEDS','17,43,101').split(',')]
    power_frames=int(env.get('SC_POWER_FRAMES','8'));assert 4<=power_frames<=160
    assert profiles and len(set(profiles))==len(profiles) and set(profiles)<=set(('mixed','sparse','dense','zero'))
    assert seeds and len(set(seeds))==len(seeds)
    manifest=dict(arch=arch,m=m,t=t,pipe=pipe,period_ns=period,corner=env['PPA_CORNER'],
      release='counter_ppa_v3',profiles=profiles,seeds=seeds,power_frames=power_frames,
      package_manifest_sha256=sha(ROOT/'package_manifest.json'),
      sources={str(p.relative_to(ROOT)):sha(p) for p in sorted(ROOT.rglob('*')) if p.is_file() and p.suffix in ('.sv','.py','.tcl','.sh')},
      library=dict(path=env['STD_DB'],sha256=sha(Path(env['STD_DB']))),
      model=dict(path=env['STD_MODEL'],sha256=sha(Path(env['STD_MODEL']))),
      boundary='Parallel weight input pins; excludes SRAM, weight retention, RNG/comparators and floating recovery',
      physical='prelayout; no CTS/SPEF/SDF; zero-delay gate VCD is not a glitch-power measurement')
    (out/'EXECUTION.json').write_text(json.dumps(manifest,indent=2)+'\n')
    commands=[];results=[];wave_archives=[]
    def call(cmd,cwd,extra=None):
        cwd.mkdir(parents=True,exist_ok=True);e=env.copy();e.update(extra or {})
        log=cwd/('command%d.log'%len(commands));start=time.time()
        with log.open('w') as f:p=subprocess.run([str(z) for z in cmd],cwd=str(cwd),env=e,stdout=f,stderr=subprocess.STDOUT)
        commands.append(dict(command=[str(z) for z in cmd],cwd=str(cwd),rc=p.returncode,seconds=time.time()-start,log=str(log)))
        (out/'COMMANDS.json').write_text(json.dumps(commands,indent=2)+'\n')
        if p.returncode:raise RuntimeError('failed '+str(log))
        return log.read_text(errors='replace')
    try:
        dc=out/'dc';call(['dc_shell','-f',ROOT/'flow/dc.tcl'],dc)
        assert (dc/'SYNTH_COMPLETE').exists() and (dc/'mapped.v').exists()
        build=out/'build';exe=build/'simv'
        call(['vcs','-full64','-sverilog','-timescale=1ns/1ps','-debug_access+all','+define+GATE',
          '+define+ARCH=%d'%arch,'+define+N=64','+define+M=%d'%m,'+define+T=%d'%t,'+define+PIPE=%d'%pipe,
          '-top','tb_counter',dc/'mapped.v',env['STD_MODEL'],ROOT/'sim/tb.sv','-o',exe],build)
        functional=out/'gate/functional';v=make(functional/'vectors',64,m,t,17,8)
        log=call([exe,'+DIR='+str(functional/'vectors'),'+FRAMES='+str(v['frames']),'+MODE=1','+RESET_TEST=1','+PERIOD='+str(period)],functional)
        if 'COUNTER_PASS' not in log:raise RuntimeError('gate oracle did not pass')
        (functional/'FUNCTION_PASS').write_text('Independent signed integer oracle passed\n')
        for profile in profiles:
            for seed in seeds:
                case=out/('gate/%s_s%d'%(profile,seed));v=make(case/'vectors',64,m,t,seed,power_frames,profile)
                log=call([exe,'+DIR='+str(case/'vectors'),'+FRAMES='+str(v['frames']),'+MODE=0','+PERIOD='+str(period),'+VCD='+str(case/'raw.vcd')],case)
                if 'COUNTER_PASS' not in log:raise RuntimeError('power activity gate oracle failed')
                begin=float(re.search(r'WINDOW_BEGIN time_ns=([\d.]+)',log).group(1))
                end=float(re.search(r'WINDOW_END time_ns=([\d.]+)',log).group(1))
                cycle_count=int(re.search(r'active_cycles=(\d+)',log).group(1))
                if cycle_count!=v['frames']*(t+pipe+3):
                    raise RuntimeError('Unexpected full-frame cycle count')
                if abs((end-begin)-cycle_count*period)>.002:
                    raise RuntimeError('Wave window duration/cycle mismatch')
                (case/'FUNCTION_PASS').write_text('All frame outputs match independent oracle\n')
                for label,start,stop in [('active',begin,end),('idle',end,end+64*period)]:
                    pw=out/('power/%s_s%d_%s'%(profile,seed,label));pw.mkdir(parents=True)
                    stats=prepare_activity(case/'raw.vcd',pw,start,stop,m*4*sw,dc,call)
                    (pw/'ACTIVITY_EXPECTED.json').write_text(json.dumps(stats,indent=2)+'\n')
                    call(['pt_shell','-f',ROOT/'flow/pt.tcl'],pw,dict(NET_DIR=str(dc),ACTIVITY_VCD=str(pw/'activity.vcd')))
                    assert (pw/'POWER_CALCULATED').exists()
                    check=verify_pt(stats,pw/'output_activity.tsv')
                    (pw/'ACTIVITY_VERIFIED.json').write_text(json.dumps(check,indent=2)+'\n')
                    row=dict(profile=profile,seed=seed,window=label,duration_ns=stop-start,
                         frames=v['frames'] if label=='active' else 0,bin_outputs=v['bin_outputs'] if label=='active' else 0,
                         frame_cycles=cycle_count/v['frames'] if label=='active' else None,
                         setup_slack_ns=float((pw/'setup_slack_ns.txt').read_text()),hold_slack_ns=float((pw/'hold_slack_ns.txt').read_text()),
                         reports=str(pw),energy_instruction='E_frame_pJ = total_power_uW * duration_ns / (1000 * completed_frames)')
                    (pw/'WINDOW.json').write_text(json.dumps(row,indent=2)+'\n')
                    row.update(window_summary(pw,row));results.append(row)
                    (out/'PARTIAL_SUMMARY.json').write_text(json.dumps(results,indent=2)+'\n')
                    write_csv(out,results)
                    if env.get('KEEP_PLAIN_VCD','0')!='1':
                        for f in [pw/'window.vcd',pw/'activity.vcd']:wave_archives.append(archive_wave(f,out))
                if env.get('KEEP_PLAIN_VCD','0')!='1':wave_archives.append(archive_wave(case/'raw.vcd',out))
                (out/'WAVE_ARCHIVES.json').write_text(json.dumps(wave_archives,indent=2)+'\n')
        (out/'SUMMARY.json').write_text(json.dumps(dict(status='POWER_CALCULATED_REVIEW_WARNINGS_AND_STA',config=manifest,windows=results),indent=2)+'\n')
        (out/'FLOW_COMPLETE').write_text('Completed tools; inspect timing, coverage and range warnings before accepting PPA.\n')
    except Exception as error:
        import traceback
        (out/'failure.txt').write_text(str(error)+'\n'+traceback.format_exc())
        raise
    finally:
        # Return small reports and immutable provenance; keep large VCD/netlist at result location.
        files=[p for p in out.rglob('*') if p.is_file() and (p.suffix in ('.json','.log','.rpt','.txt','.tsv','.sdc','.csv') or p.name in ('FLOW_COMPLETE','FUNCTION_PASS','POWER_CALCULATED','SYNTH_COMPLETE'))]
        index={str(p.relative_to(out)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in files}
        (out/'RESULT_INDEX.json').write_text(json.dumps(index,indent=2)+'\n')
        with tarfile.open(str(out)+'_reports.tar.gz','w:gz') as tar:
            for p in files+[out/'RESULT_INDEX.json']:tar.add(str(p),arcname=out.name+'/'+str(p.relative_to(out)))
if __name__=='__main__':main()
