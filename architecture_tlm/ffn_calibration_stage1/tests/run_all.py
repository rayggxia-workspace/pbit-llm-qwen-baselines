#!/usr/bin/env python3
# Unified functional gate: no technology or power claims.
import argparse, hashlib, importlib.util, json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
    paths=[ROOT/'cases.json']
    for d in ('rtl','tests','flow'):
        paths += [p for p in (ROOT/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(paths)}
def dump(p,obj): p.write_bytes((json.dumps(obj,indent=2)+'\n').encode('utf-8'))
def run(command,cwd,phase):
    dump(cwd/(phase+'_command.json'),command)
    r=subprocess.run(command,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=900)
    (cwd/(phase+'.log')).write_bytes(r.stdout.encode('utf-8'))
    if r.returncode: raise RuntimeError(f'{phase} exited {r.returncode}: {r.stdout[-2000:]}')
    return r.stdout

def compile_and_run(args,folder,tb,plus=(),top='tb'):
    rtl=[str(p) for p in sorted((ROOT/'rtl').glob('*.sv'))]
    if args.simulator=='iverilog':
        exe=folder/'sim.vvp'; cmd=[args.iverilog]
        if args.ivl: cmd+=['-B',args.ivl]
        cmd+=['-g2012','-Wall','-s',top,'-o',str(exe),*rtl,str(tb)]
        sim=[args.vvp]+(['-M',args.ivl] if args.ivl else [])+[str(exe),*plus]
    else:
        exe=folder/'simv';cmd=[args.vcs,'-full64','-sverilog','-top',top,*rtl,str(tb),'-o',str(exe)]
        sim=[str(exe),*plus]
    run(cmd,folder,'compile');return run(sim,folder,'simulation')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--suite',choices=['smoke','all'],default='smoke')
    ap.add_argument('--case-id')
    ap.add_argument('--simulator',choices=['iverilog','vcs'],default='iverilog')
    ap.add_argument('--iverilog',default='iverilog');ap.add_argument('--vvp',default='vvp')
    ap.add_argument('--ivl');ap.add_argument('--vcs',default='vcs')
    args=ap.parse_args(); out=args.output.resolve()
    if out.exists(): raise SystemExit('Output already exists; use a new immutable output directory.')
    out.mkdir(parents=True);before=sources();started=time.monotonic()
    config=json.loads((ROOT/'cases.json').read_text(encoding='utf-8'))
    cases=[c for c in config['cases'] if c['id']==args.case_id] if args.case_id else [c for c in config['cases'] if args.suite=='all' or c['smoke']]
    summary=dict(status='running',case_id=args.case_id,suite=args.suite,source_sha256=before,cases=[],simulator=args.simulator,scope='RTL integer and handshake only; no STA/PPA/model-quality claim')
    try:
        if not cases: raise ValueError('unknown case ID or empty suite')
        import counter_verify, chain_verify, test_restore_accumulator as restore_verify
        for c in cases:
            print('RUN '+c['id'],flush=True);folder=out/c['id'];folder.mkdir();p=c['parameters'];kind=c['verification_kind']
            if kind=='counter':
                seed_results=[]
                for seed in ((17,) if p["M"]==8 else (17,31,193)):
                    d=folder/f'seed_{seed}';d.mkdir()
                    g=counter_verify.generate_case(d,n=p['N'],m=p['M'],bins=p['BINS'],t=p['T'],seed=seed)
                    bench=(ROOT/'tests/tb_ffn_counter.sv').read_text(encoding='utf-8')
                    # Instantiate the unchanged testbench with explicit parameters, for both simulators.
                    wrapper='\nmodule tb; tb_ffn_counter #('+','.join(f'.{k}({v})' for k,v in p.items())+') test(); endmodule\n'
                    tb=d/'tb.sv';tb.write_bytes((bench+wrapper).encode('utf-8'))
                    stdout=compile_and_run(args,d,tb,['+VECTORS='+g['stimulus']])
                    receipt=counter_verify.parse_run(stdout,g['expected_receipt'])
                    seed_results.append(dict(seed=seed,receipt=receipt,oracle_sha256=g['oracle_sha256'],stimulus_sha256=g['stimulus_sha256']))
                result=dict(status='passed',seeds=seed_results)
            elif kind in ('restore','accumulator'):
                result=restore_verify.run_tests(folder,simulator=args.simulator,iverilog=args.iverilog,vvp=args.vvp,ivl=args.ivl,vcs=args.vcs,case_id=c['id'])
                if result['status']!='passed': raise AssertionError(result)
            else:
                tb,frames=chain_verify.generate(folder,bins=p['BINS'],t=p['T'])
                result=chain_verify.check(compile_and_run(args,folder,tb),frames)
            dump(folder/'result.json',result);summary['cases'].append(dict(case_id=c['id'],**result))
            print('PASS '+c['id'],flush=True)
        if sources()!=before: raise RuntimeError('Source changed while functional validation was running')
        summary['status']='passed'
    except Exception as exc:
        summary['status']='failed';summary['error']=repr(exc)
    summary['elapsed_seconds']=time.monotonic()-started;dump(out/'summary.json',summary)
    print(json.dumps(dict(status=summary['status'],cases=len(summary['cases']),elapsed_seconds=summary['elapsed_seconds'])),flush=True)
    if summary['status']!='passed': raise SystemExit(summary.get('error','failed'))
if __name__=='__main__': main()
