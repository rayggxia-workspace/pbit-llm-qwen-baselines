"""One finite Issue157 continuation: read-only monitoring and verified milestone publication.

Never resubmits quality jobs or modifies the frozen execution snapshot. A failed
query is not a terminal job state. Publication errors stop for explicit recovery.
"""
from pathlib import Path
import datetime,hashlib,importlib.util,json,os,re,subprocess,sys,time,traceback
from prepare_cpu_gate import ROOT,TREE,project,guard,m

KEY='8d60abe4e7c5'
JOB='2878'
TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'}
STATE=ROOT/'WATCH_QUALITY_STATE.json'
LOCK=ROOT/'WATCH_QUALITY_LOCK.json'

def stamp():return datetime.datetime.now().astimezone().isoformat(timespec='seconds')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    temp.replace(path)
def git(*args):
    return subprocess.check_output(['git','-C',str(TREE),*args],text=True,encoding='utf-8').strip()
def command(script,*args,timeout=600):
    r=subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/script),*args],capture_output=True,text=True,encoding='utf-8',timeout=timeout)
    with (ROOT/'watch_quality_commands.log').open('a',encoding='utf-8') as log:
        log.write(stamp()+' '+script+' '+repr(args)+'\n'+r.stdout+r.stderr+'\n')
    if r.returncode:raise RuntimeError(f'{script} exit={r.returncode}; inspect watch_quality_commands.log')
    return r.stdout
def state_from(text):
    if not re.search(r'\bJobId='+JOB+r'\b',text):raise ValueError('unexpected scheduler job identity')
    match=re.search(r'\bJobState=(\S+)',text)
    if not match:raise ValueError('missing job state')
    return match.group(1).split('+')[0]
def readonly_retry(function):
    for attempt in range(3):
        try:return function()
        except (OSError,RuntimeError,subprocess.SubprocessError):
            if attempt==2:raise
            time.sleep(5*(attempt+1))
def milestone_keys(r):
    keys=[]
    if all(r['ppl']['modes'][mode]['verified_complete'] for mode in ('dense','sparq')):keys.append('ppl')
    for name,task in r['tasks'].items():
        if all(task['modes'][mode]['verified_complete'] for mode in ('dense','sparq')):keys.append(name)
    if r['complete']:keys.append('quality_complete')
    return keys

def main():
    # The lock is never silently cleared: an interrupted process requires its
    # recorded PID/publication/submission receipts to be inspected before resume.
    with LOCK.open('x',encoding='utf-8') as f:json.dump(dict(pid=os.getpid(),started=stamp(),job=JOB),f)
    helpers=['watch_quality.py','collect_live.py','archive_checkpoint.py','publish.py','publish_checkpoint_stage.py','control.py','prepare_cpu_gate.py']
    hashes={str(ROOT/p):sha(ROOT/p) for p in helpers}
    for dependency in (ROOT.parent/'pdnn_accuracy_20261023/remote_control.py',
                       ROOT.parent/'pbit_attention_e01_20261019/control.py'):
        hashes[str(dependency)]=sha(dependency)
    reporter=TREE/'qwen3/sparq/report.py';hashes[str(reporter)]=sha(reporter)
    spec=importlib.util.spec_from_file_location('issue157_verified_report',reporter)
    report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report)
    expected_head=git('rev-parse','HEAD')
    assert not git('status','--porcelain'),'checkout must be clean before background continuation'
    assert git('branch','--show-current')=='task/157-sparq-qwen3'
    published=[];iteration=0;next_collection=0;deadline=time.monotonic()+13*3600
    state=dict(pid=os.getpid(),started=stamp(),job=JOB,execution=KEY,expected_head=expected_head,
               status='monitoring',published=published,helper_sha256=hashes)
    save(STATE,state)
    while time.monotonic()<deadline:
        assert all(sha(p)==digest for p,digest in hashes.items()),'continuation helper changed; stop before action'
        text=readonly_retry(lambda:m.ssh(guard+'/opt/slurm/21.08.8/bin/scontrol show job '+JOB))
        current=state_from(text)
        (ROOT/'gpu_FULL_V2_latest_state.txt').write_text(text,encoding='utf-8')
        terminal=current in TERMINAL
        if terminal:
            target=ROOT/'gpu_FULL_V2_terminal_state.txt'
            if not target.exists():target.write_text(text,encoding='utf-8')
            for suffix in ('out','err'):
                dest=ROOT/('full-'+JOB+'.'+suffix)
                readonly_retry(lambda:m.transfer(dest,project+'/logs/full-'+JOB+'.'+suffix,download=True))
        state.update(updated=stamp(),job_state=current)
        save(STATE,state)
        if time.monotonic()>=next_collection or terminal:
            readonly_retry(lambda:command('collect_live.py',timeout=600))
            r=report.review(ROOT/'formal_results'/KEY,source_root=ROOT/('source_'+KEY))
            keys=milestone_keys(r)
            if terminal:keys.append('terminal_'+current.lower())
            fresh=[k for k in keys if k not in published]
            state.update(quality_status=r['status'],ppl_windows={k:v['verified_windows'] for k,v in r['ppl']['modes'].items()},
                         task_documents={k:{m:v['verified_documents'] for m,v in t['modes'].items()} for k,t in r['tasks'].items()})
            if fresh:
                assert git('rev-parse','HEAD')==expected_head and not git('status','--porcelain'),'checkout changed externally'
                label='auto_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+'_'.join(fresh)
                intent=dict(label=label,head=expected_head,milestones=fresh,when=stamp())
                save(ROOT/('WATCH_'+label+'_INTENT.json'),intent)
                command('archive_checkpoint.py',label)
                subprocess.run(['git','-C',str(TREE),'add','qwen3/sparq/results','work/amlink1219/157','progress/amlink1219/STATUS.md'],check=True)
                subprocess.run(['git','-C',str(TREE),'diff','--cached','--check'],check=True)
                subprocess.run(['git','-C',str(TREE),'commit','-m','results(sparq): verify '+', '.join(fresh)],check=True)
                expected_head=git('rev-parse','HEAD')
                state['expected_head']=expected_head;save(STATE,state)
                # Do not retry state-changing calls after ambiguous errors.
                command('publish.py',timeout=600)
                command('publish_checkpoint_stage.py',label,timeout=240)
                published.extend(fresh)
                state.update(last_publication=label,published=published)
                print(json.dumps(dict(time=stamp(),job_state=current,published=fresh,quality_status=r['status'])),flush=True)
            save(STATE,state)
            next_collection=time.monotonic()+180
        if terminal:
            state.update(status='quality_complete_verified' if r['complete'] else 'terminal_quality_incomplete',finished=stamp())
            save(STATE,state)
            # Measurement continuation is enabled only after its separate
            # reviewed immutable plan is present, never by guessing commands.
            supplement=ROOT/'MEASUREMENT_CONTINUATION_READY.json'
            if supplement.exists() and current=='COMPLETED' and r['complete']:
                plan=json.loads(supplement.read_text(encoding='utf-8'))
                script=ROOT/plan['script']
                assert script.parent==ROOT and sha(script)==plan['sha256']
                command(plan['script'],timeout=7200)
            return
        time.sleep(45)
    raise TimeoutError('finite 13-hour watch limit reached; job state not inferred')

if __name__=='__main__':
    try:main()
    except FileExistsError:
        # A second launch must not overwrite the active owner's state receipt.
        raise
    except BaseException as e:
        value=json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else dict(job=JOB,pid=os.getpid())
        value.update(status='needs_recovery',updated=stamp(),error=repr(e),traceback=traceback.format_exc())
        save(STATE,value)
        raise
