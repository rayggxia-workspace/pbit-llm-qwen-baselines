"""One separate GPU power/latency supplement, only after quality job terminates."""
from prepare_cpu_gate import ROOT,TREE,project,guard,m
from pathlib import Path
import hashlib,json,re,subprocess,sys,time,shutil,datetime,traceback,os
from watch_quality import readonly_retry,stamp,save,git,command,TERMINAL

def exclusive_receipt(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n')
        stream.flush();os.fsync(stream.fileno())

def main():
    exclusive_receipt(ROOT/'MEASUREMENT_CONTROLLER_LOCK.json',dict(pid=os.getpid(),started=stamp()))
    plan=json.loads((ROOT/'MEASUREMENT_PLAN.json').read_text(encoding='utf-8'))
    assert plan['project']==project
    old=(ROOT/'gpu_FULL_V2_terminal_state.txt').read_text(encoding='utf-8')
    assert re.search(r'\bJobId=2878\b',old) and 'JobState=COMPLETED' in old
    parent_watch=json.loads((ROOT/'WATCH_QUALITY_STATE.json').read_text(encoding='utf-8'))
    assert parent_watch['status']=='quality_complete_verified' and parent_watch['job']=='2878'
    assert not (ROOT/'MEASUREMENT_SUBMIT_INTENT.json').exists(),'inspect prior submission identity; never automatically replay'
    assert not git('status','--porcelain')
    expected_head=git('rev-parse','HEAD')
    save(ROOT/'MEASUREMENT_CONTROLLER_STATE.json',dict(status='waiting_for_idle_personal_gpu_queue',started=stamp(),head=expected_head))
    deadline=time.monotonic()+3600
    while True:
        queues=readonly_retry(m.queues)
        busy=any('gpu:' in line for row in queues for line in row['stdout'].splitlines()[2:])
        if not busy:break
        if time.monotonic()>=deadline:raise TimeoutError('personal GPU jobs still in flight; supplement not submitted')
        time.sleep(45)
    source=plan['source']
    checked=readonly_retry(lambda:m.ssh(guard+f'test "$(realpath -e {source})" = {source}\ntest "$(stat -c %U {source})" = Weican_Chen\nsha256sum {plan["script"]}'))
    assert checked.split()[0]==plan['script_sha256']
    # Persist intent before the only state-changing remote submission. Ambiguous
    # timeout stops here for queue inspection; it never resubmits automatically.
    exclusive_receipt(ROOT/'MEASUREMENT_SUBMIT_INTENT.json',dict(plan=plan,when=stamp()))
    reply=m.ssh(guard+f'/opt/slurm/21.08.8/bin/sbatch --parsable --output={project}/logs/measurement-%j.out --error={project}/logs/measurement-%j.err {plan["script"]}')
    job=reply.strip().split(';')[0];assert re.fullmatch(r'\d+',job)
    save(ROOT/'MEASUREMENT_JOB.json',dict(job=job,commit=plan['commit'],source=source,parent_job='2878',gpu=True))
    remote=project+'/benchmark_supplements/'+plan['commit'][:12]+'_'+plan['parent_fingerprint'][:12]+'/'+job
    local=ROOT/'measurement_results'/job;local.mkdir(parents=True,exist_ok=True)
    deadline=time.monotonic()+3600
    while True:
        text=readonly_retry(lambda:m.ssh(guard+'/opt/slurm/21.08.8/bin/scontrol show job '+job))
        assert re.search(r'\bJobId='+job+r'\b',text)
        status=re.search(r'\bJobState=(\S+)',text).group(1).split('+')[0]
        (ROOT/'measurement_latest_state.txt').write_text(text,encoding='utf-8')
        save(ROOT/'MEASUREMENT_CONTROLLER_STATE.json',dict(status='submitted',job=job,scheduler_state=status,updated=stamp(),remote=remote))
        if status in TERMINAL:
            (ROOT/'measurement_terminal_state.txt').write_text(text,encoding='utf-8')
            break
        if time.monotonic()>=deadline:raise TimeoutError('supplement still queued/running; retain job identity, do not replay')
        time.sleep(30)
    for suffix in ('out','err'):
        readonly_retry(lambda:m.transfer(ROOT/('measurement-'+job+'.'+suffix),project+'/logs/measurement-'+job+'.'+suffix,download=True))
    listing=readonly_retry(lambda:m.ssh(guard+f'if test -d {remote}; then find {remote} -maxdepth 1 -type f \\( -name "*.json" -o -name "progress.jsonl" \\) -printf "%f\\n"; fi'))
    names=listing.splitlines();assert all(re.fullmatch('[A-Za-z0-9_.-]+',n) for n in names)
    hashes={}
    if names:
        lines=readonly_retry(lambda:m.ssh(guard+'sha256sum '+' '.join(remote+'/'+n for n in names)))
        hashes={line.split(None,1)[1].strip()[len(remote)+1:]:line.split()[0] for line in lines.splitlines()}
        for name,digest in hashes.items():
            target=local/name;temporary=target.with_suffix('.json.part')
            readonly_retry(lambda:m.transfer(temporary,remote+'/'+name,download=True))
            assert hashlib.sha256(temporary.read_bytes()).hexdigest()==digest
            temporary.replace(target)
    save(local/'TRANSFER.json',dict(job=job,remote=remote,files={n:dict(sha256=d,remote=remote+'/'+n) for n,d in hashes.items()}))
    review=ROOT/('measurement_review_'+job)
    verified=False
    if status=='COMPLETED' and 'report.json' in hashes:
        subprocess.run([sys.executable,'-X','utf8','-B','-m','qwen3.sparq.report',str(local),'--supplement',
            '--parent-results',str(ROOT/'formal_results/8d60abe4e7c5'),'--source-root',plan['bundle'],'--output',str(review)],cwd=TREE,check=True)
        reviewed=json.loads((review/'REVIEW.json').read_text(encoding='utf-8'))
        verified=reviewed['measurement_complete'] is True
        assert reviewed['quality_evaluation_complete'] is False
    assert git('rev-parse','HEAD')==expected_head and not git('status','--porcelain'),'checkout changed externally during supplement'
    dest=TREE/'qwen3/sparq/results/benchmark_supplements'/job
    assert not dest.exists();dest.mkdir(parents=True)
    shutil.copytree(local,dest/'raw')
    if review.exists():shutil.copytree(review,dest/'review')
    (dest/'.gitattributes').write_text('* -text -whitespace\n** -text -whitespace\n',encoding='utf-8',newline='\n')
    note=f'''# GPU 测量补充（Slurm {job}）

调度状态 `{status}`；独立离线复核 `{verified}`。质量源仍为8d60abe4e7c5，测量源 `{plan['commit']}`。此目录不新增PPL或准确率，不继承完整质量结论；GPU板级遥测不是ASIC PPA。原质量结果与此前未采到功率的54次计时保留。

完整原件及SHA见raw/；成功完成并核验时见review/REVIEW_ZH.md。若作业失败、缺少报告或验证不通过，功率/能量不得作为成功结果引用。
'''
    (dest/'README_ZH.md').write_text(note,encoding='utf-8',newline='\n')
    work=TREE/'work/amlink1219/157';receipts=work/('measurement_'+job);receipts.mkdir()
    for name in ('MEASUREMENT_PLAN.json','MEASUREMENT_JOB.json','MEASUREMENT_CONTROLLER_STATE.json','measurement_terminal_state.txt','measurement-'+job+'.out','measurement-'+job+'.err'):
        shutil.copyfile(ROOT/name,receipts/name)
    attr=work/'.gitattributes';attr.write_text(attr.read_text(encoding='utf-8')+f'measurement_{job}/** -text -whitespace\n',encoding='utf-8',newline='\n')
    handoff=work/'HANDOFF.md';handoff.write_text(handoff.read_text(encoding='utf-8')+f'\n\nGPU补测最新：作业{job}，{status}；离线校验{verified}；测量源{plan["commit"]}。结果qwen3/sparq/results/benchmark_supplements/{job}/，不改变原质量源。物理ASIC PPA仍null。\n',encoding='utf-8',newline='\n')
    personal_status=TREE/'progress/amlink1219/STATUS.md'
    personal_status.write_text(f'GPU补测更新（{stamp()}）：作业{job}，调度{status}，离线校验{verified}；见[SparQ补测](../../qwen3/sparq/results/benchmark_supplements/{job}/README_ZH.md)。板级功率可用性以该独立报告为准，ASIC PPA仍null。\n\n'+personal_status.read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
    manifest={p.relative_to(work).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in work.rglob('*') if p.is_file() and p.name!='ARTIFACTS.json'}
    save(work/'ARTIFACTS.json',manifest)
    subprocess.run(['git','-C',str(TREE),'add','qwen3/sparq/results/benchmark_supplements', 'work/amlink1219/157','progress/amlink1219/STATUS.md'],check=True)
    subprocess.run(['git','-C',str(TREE),'diff','--cached','--check'],check=True)
    subprocess.run(['git','-C',str(TREE),'commit','-m',f'results(sparq): archive separate GPU measurement job {job}'],check=True)
    command('publish.py',timeout=600)
    import control
    session=control.client();base='https://api.github.com/repos/'+control.REPO+'/'
    url='https://github.com/'+control.REPO+'/blob/task/157-sparq-qwen3/qwen3/sparq/results/benchmark_supplements/'+job+'/README_ZH.md'
    marker='<!-- sparq-157-gpu-measurement-supplement -->'
    for endpoint in ('issues/157','pulls/163'):
        response=session.get(base+endpoint,timeout=45);response.raise_for_status();old=response.json()['body']
        if marker in old:old=old.split(marker)[0].rstrip()
        body=old+'\n\n'+marker+f'\nGPU补测已归档：[Slurm {job}]({url})；调度{status}，离线校验{verified}。原8d60质量快照保持，ASIC PPA仍null。\n'
        save(ROOT/('MEASUREMENT_'+endpoint.replace('/','_')+'_INTENT.json'),dict(body=body))
        response=session.patch(base+endpoint,json=dict(body=body),timeout=45);response.raise_for_status()
        response=session.get(base+endpoint,timeout=45);response.raise_for_status();assert response.json()['body']==body
    save(ROOT/'MEASUREMENT_CONTROLLER_STATE.json',dict(status='archived_uploaded',job=job,scheduler_state=status,verified=verified,url=url,finished=stamp()))
    print(json.dumps(dict(job=job,scheduler_state=status,verified=verified,url=url)),flush=True)

if __name__=='__main__':
    try:main()
    except FileExistsError:
        raise
    except BaseException as e:
        save(ROOT/'MEASUREMENT_CONTROLLER_ERROR.json',dict(error=repr(e),traceback=traceback.format_exc(),time=stamp()))
        raise
