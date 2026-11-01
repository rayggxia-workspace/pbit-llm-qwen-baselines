"""Continue only timed-out GU power windows; retain original RTL/netlist/activity.

Generic root argument: contains no credentials, process library or fixed server path.
Not used unless an original case really times out. Completed cases exit untouched.
"""
from pathlib import Path
import argparse,hashlib,json,os,shlex,subprocess,sys


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())


def submit(root,parent,binding):
    receipt=root/'RESUME_SUBMISSION.json';assert not receipt.exists()
    cases=json.loads((root/'CASES.json').read_text())
    wanted=[i for i in (2,3) if json.loads((root/('results/ppa_%s_%d'%(parent,i))/'RESULT.json').read_text())['status']!='calculated']
    if not wanted:print(json.dumps(dict(status='all_original_cases_completed',job=None)));return
    binding=binding.resolve();assert binding.is_file()
    script='#!/bin/bash\nsource "$HOME/.bashrc"\nset -eo pipefail\nexport PYTHONDONTWRITEBYTECODE=1\n'+' '.join(shlex.quote(s) for s in [sys.executable,'-B',str(Path(__file__).resolve()),'worker','--root',str(root),'--parent',parent])+'\n'
    args=['sbatch','--parsable','--chdir='+str(root),'--partition=v6_384','--array='+','.join(map(str,wanted))+'%2','--dependency=afterany:'+parent,
          '--cpus-per-task=2','--mem=6G','--time=01:00:00','--job-name=gu204_resume','--export=ALL,MATRIX_PRIVATE_LIBRARY='+str(binding),'--output='+str(root/'logs/%A_%a.out'),'--error='+str(root/'logs/%A_%a.err')]
    z=subprocess.run(args,input=script,universal_newlines=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if z.returncode:raise RuntimeError(z.stderr)
    r=dict(stage='PPA_RESUME',job=z.stdout.strip().split(';')[0],parent_job=parent,cases=wanted,control_sha256=sha(__file__),purpose='Only complete unchanged timed-out GU power windows;no repeated DC or completed windows')
    save(receipt,r);print(json.dumps(r))


def worker(root,parent):
    idx=int(os.environ['SLURM_ARRAY_TASK_ID']);job=os.environ['SLURM_ARRAY_JOB_ID'];assert idx in (2,3)
    c=json.loads((root/'CASES.json').read_text())[idx];assert c['M']==64
    out=(root/('results/ppa_%s_%d'%(parent,idx))).resolve();assert root/'results' in out.parents
    original=json.loads((out/'RESULT.json').read_text())
    if original['status']=='calculated':print('ORIGINAL_ALREADY_CALCULATED');return
    state=subprocess.check_output(['sacct','-X','-n','-j',parent+'_'+str(idx),'--format=State','-P'],universal_newlines=True).strip().split('|')[0]
    assert state=='TIMEOUT',state
    manifest=json.loads((root/'EXECUTION_MANIFEST.json').read_text())
    for n,h in manifest['files'].items():assert sha(root/n)==h,n
    assert sha(out/'synthesis/mapped.v')==original['mapped_sha256']
    sys.path.insert(0,str(root/'flow'))
    source=(root/'flow/run_integrated.py').read_text()
    import upstream as U
    binding_path=json.loads((root/'PPA_SUBMISSION.json').read_text())
    binding_file=Path(os.environ['MATRIX_PRIVATE_LIBRARY'])
    binding=json.loads(binding_file.read_text())
    assert all(sha(binding[k])==binding_path['library_fingerprints'][k] for k in ('db','model'))
    U.archive(out)
    partial=out/('partial_before_resume_'+job+'.tar.gz');assert not partial.exists();(out/'reports.tar.gz').rename(partial)
    meta=dict(job=job,parent_job=parent,parent_state=state,control_sha256=sha(__file__),original_RESULT_sha256=sha(out/'RESULT.json'),
              original_partial_archive=partial.name,original_partial_archive_sha256=sha(partial),mapped_sha256=original['mapped_sha256'],
              source_manifest_sha256=sha(root/'EXECUTION_MANIFEST.json'),completed_window_keys=[[w['seed'],w['mode']] for w in original['windows']],
              library_fingerprints=binding_path['library_fingerprints'])
    def replace_once(text,a,b):
        assert text.count(a)==1,a
        return text.replace(a,b)
    original_init="out.mkdir(parents=True);top=c['top'];r={'status':'running','case':c,'top':top,'windows':[]};save(out/'RESULT.json',r)"
    resumed_init="out.mkdir(parents=True,exist_ok=True);top=c['top'];r=json.loads((out/'RESULT.json').read_text());r['status']='running';r['continuation']=RESUME_META;save(out/'RESULT.json',r)"
    effective=replace_once(source,original_init,resumed_init)
    for name in ('synth','bound','comp'):effective=replace_once(effective,name+'.mkdir();',name+'.mkdir(exist_ok=True);')
    effective=replace_once(effective,"cfg.write_text(U.config(top,binding['db']))","assert cfg.read_text()==U.config(top,binding['db'])")
    old="   for w in rr['windows']:\n    d=out/(w['mode']+'_'+str(seed));d.mkdir();prefix='tb/dut/';"
    new="""   for w in rr['windows']:
    if any(x['seed']==seed and x['mode']==w['mode'] for x in r['windows']):continue
    d=out/(w['mode']+'_'+str(seed))
    if d.exists():d.rename(out/(d.name+'_partial_before_resume_'+RESUME_META['job']))
    d.mkdir();prefix='tb/dut/';"""
    effective=replace_once(effective,old,new)
    meta['effective_flow_sha256']=hashlib.sha256(effective.encode()).hexdigest()
    save(out/('RESUME_'+job+'.json'),meta);(out/('effective_resume_flow_'+job+'.py')).write_bytes(effective.encode())
    ns=dict(__name__='gu_resume_frozen_flow',__file__=str(root/'flow/run_integrated.py'),RESUME_META=meta)
    exec(compile(effective,ns['__file__'],'exec'),ns)
    replay=ns['replay']
    def cached_replay(binary,folder,case,seed,env=None):
        if (folder/'REPLAY.json').exists():
            r=json.loads((folder/'REPLAY.json').read_text());assert r['status']=='pass' and sha(folder/'activity.vcd')==r['VCD_sha256'];return r
        if folder.exists():folder.rename(folder.parent/(folder.name+'_partial_before_resume_'+job))
        return replay(binary,folder,case,seed,env)
    ns['replay']=cached_replay
    run=U.run
    def cached_run(cmd,cwd,log,env=None):
        if str(cmd[0])=='dc_shell':
            assert sha(out/'synthesis/mapped.v')==meta['mapped_sha256'] and (cwd/'STAGE_COMPLETE').exists();return
        if str(cmd[0])=='vcs':assert (cwd/'simv').is_file();return
        if str(cmd[0])=='pt_shell' and env.get('CV2_BOUNDARY_ONLY')=='1':assert (cwd/'activity_boundary.txt').is_file();return
        return run(cmd,cwd,log,env)
    U.run=cached_run
    ns['ppa'](out,c)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['submit','worker']);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--parent',required=True);ap.add_argument('--binding',type=Path);a=ap.parse_args()
    root=a.root.resolve();assert root.name=='gu204_v1_20261101' and (root/'EXECUTION_MANIFEST.json').is_file()
    if a.action=='submit':
        assert a.binding is not None
        submit(root,a.parent,a.binding)
    else:worker(root,a.parent)
