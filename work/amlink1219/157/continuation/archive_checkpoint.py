"""Immutable Issue157 checkpoints. Importing is inert; only main() archives files."""
from pathlib import Path, PurePosixPath
import datetime, hashlib, json, re, subprocess, sys, tempfile, uuid

ROOT = Path(__file__).resolve().parent
TREE = ROOT.parents[1] / 'workspace_projects/sq157'
REPO = 'rayggxia-workspace/pbit-llm-qwen-baselines'
TERMINAL = {'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8')


def valid_label(label):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_]*', label):
        raise ValueError('label must contain only ASCII letters, digits and underscores')
    return label


def child(root, name):
    rel = PurePosixPath(name)
    root = Path(root).resolve()
    if rel.is_absolute() or '..' in rel.parts or '\\' in name:
        raise ValueError('unsafe relative path: '+name)
    path = root.joinpath(*rel.parts)
    if not path.resolve().is_relative_to(root):
        raise ValueError('path escapes root: '+name)
    return path


def freeze(path, payload):
    """Create exclusively, or require identical existing bytes. Never overwrite."""
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream: stream.write(payload)
    except FileExistsError:
        if path.read_bytes() != payload:
            raise ValueError('immutable artifact differs; use a new label: '+str(path))


def current(path, payload):
    """Atomic update for mutable pointers, handoff, STATUS and manifest only."""
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name+'.pending_'+uuid.uuid4().hex)
    with pending.open('xb') as stream: stream.write(payload)
    pending.replace(path)


def scheduler_state(root, job):
    rows = []
    for name in ('gpu_FULL_V2_latest_state.txt','gpu_FULL_V2_terminal_state.txt'):
        path = Path(root)/name
        if not path.is_file(): continue
        fields = dict(re.findall(r'\b(JobId|JobState|ExitCode|RunTime|NodeList)=([^\s]+)',path.read_text(encoding='utf-8')))
        if fields.get('JobId') != str(job) or not fields.get('JobState'): continue
        state = fields['JobState'].split('+')[0]
        rows.append(dict(job=str(job),state=state,terminal=state in TERMINAL,exit_code=fields.get('ExitCode'),
            runtime=fields.get('RunTime'),allocation=fields.get('NodeList'),source=name,sha256=digest(path),
            observed_local_file_mtime=datetime.datetime.fromtimestamp(path.stat().st_mtime,datetime.timezone.utc).isoformat(timespec='seconds'),
            _mtime=path.stat().st_mtime))
    if not rows:
        return dict(job=str(job),state='UNKNOWN',terminal=False,exit_code=None,source=None,observed_local_file_mtime=None)
    # Preserve the terminal response even after Slurm ages out or a stale RUNNING file is copied.
    result = max([r for r in rows if r['terminal']] or rows,key=lambda r:r['_mtime'])
    result.pop('_mtime')
    return result


def scheduler_text(state):
    return (f"GPU {state['job']} 最近保存的 Slurm 状态 **{state['state']}**，ExitCode={state.get('exit_code') or '未知'}，"
            f"观测文件时间 {state.get('observed_local_file_mtime') or '未知'}。"
            '这是保存的调度证据；监控断连或文件缺失不证明作业结束。')


def progress_text(report):
    lines, missing = [], []
    def number(value): return '待定' if value is None else format(value,'.9g')
    for mode in ('dense','sparq'):
        row = report['ppl']['modes'][mode]; done = row['verified_complete']
        scope = '完整 PPL' if done else '子集 PPL（不是全 WT2）'
        lines.append(f"- cached {mode}：{row['verified_windows']}/{row.get('expected_windows') or '未知'} 窗，"
                     f"{row['scored_tokens']} 个目标；{scope}={number(row.get('perplexity'))}；完整核验={done}。")
        if not done: missing.append('cached '+mode+' 全 WT2')
    row = report['vectorized_anchor']
    lines.append(f"- 向量化 BF16 anchor：{row['verified_windows']}/{row.get('expected_windows') or '未知'} 窗，"
                 f"PPL={number(row.get('perplexity'))}，完整核验={row['verified_complete']}；执行形状与 cached 不同。")
    if not row['verified_complete']: missing.append('向量化 anchor')
    for task, data in report['tasks'].items():
        for mode in ('dense','sparq'):
            row = data['modes'][mode]; done = row['verified_complete']
            values = ', '.join(k+'='+number(v) for k,v in row['metrics_from_official_rows'].items())
            lines.append(f"- {task}/{mode}：{row['verified_documents']}/{row['expected_documents']} 题，"
                         f"{'全任务' if done else '已验子集'} {values}；完整核验={done}。")
            if not done: missing.append(task+'/'+mode)
    if not report['benchmark']['verified_complete']: missing.append('GPU benchmark')
    if not report.get('final_SUMMARY_present'): missing.append('最终 SUMMARY')
    if not report['gates']['preflight']['passed']: missing.append('正式 preflight 门禁')
    if report.get('formal_task_document_batch') != 1 and not report['gates']['document_batch_gate']['passed']:
        missing.append('所选跨题批处理门禁')
    conclusion = ('全部请求的质量部件和正式门禁已核验；PR 仍待审，物理 PPA 未完成。' if report['complete']
                  else '尚未完整核验：'+'、'.join(missing or ['总报告完整性判定'])+'。')
    return '\n'.join(lines), conclusion


def benchmark_text(report):
    bench = report['benchmark']
    if not bench['present']: return 'GPU benchmark 原件尚未归档；不推算速度或功率。'
    rows = [r for r in bench['summaries'] if r['context_tokens']==2048 and r['decode_steps']==128]
    speeds = '，'.join(f"{r['mode']} {r['decode']['tokens_per_wall_second']:.6g} token/s" for r in rows)
    power = bench.get('power_unavailable_interpretation') or '仅使用采样覆盖检查通过的板级估计；不可用阶段保持 null'
    return (f"GPU benchmark 完整核验={bench['verified_complete']}；{bench.get('gpu_name','未知GPU')}，"
            f"context2048/decode128：{speeds or '未验得该测量'}。功率：{power}。"
            '这是原 FFN 的 Python 全模型参考计时，不是优化稀疏 kernel 或 ASIC 速度/能耗。'
            '后续计量修复须另冻结、另存补充，不能替换原质量快照。')


def gate_text(report):
    gate = report['gates']['document_batch_gate']
    return (f"正式 document_batch={report.get('formal_task_document_batch')}；preflight passed={report['gates']['preflight']['passed']}。"
            f"跨题候选 present={gate['present']}、passed={gate['passed']}；失败项={json.dumps(gate.get('reported_failures',[]),ensure_ascii=False)}。"
            '候选失败完整保留；正式逐题/choice_batch4 不采用该优化，不放宽门限。')


def evidence_files(root, job):
    names = ['FULL_V2_EXECUTION.json','CPU_FULL_V2_JOB.json','GPU_FULL_V2_JOB.json','CPU_FINAL_V2.json',
             'cpu_final_V2_terminal_state.txt','cpu-final-2877.out','cpu-final-2877.err',
             'gpu_FULL_V2_latest_state.txt','gpu_FULL_V2_terminal_state.txt','gpu_full.sbatch','cpu_final.sbatch',
             'JIERUIZ_COMMENT_RECEIPT.json','PROJECTS_READ_CHECK.json','ZOTERO_READING_PENDING_RECEIPT.json',
             'WATCH_QUALITY_STATE.json','MEASUREMENT_PLAN.json','MEASUREMENT_CONTINUATION_READY.json']
    files = {n:Path(root)/n for n in names if (Path(root)/n).is_file()}
    for directory in (Path(root),Path(root)/'logs'):
        if directory.is_dir():
            for suffix in ('out','err'):
                for path in directory.glob('*'+str(job)+'*.'+suffix): files[path.relative_to(root).as_posix()] = path
    return dict(sorted(files.items()))


def input_snapshot(raw, source, execution, reporter, evidence):
    files = {}
    for name, checksum in execution['files'].items():
        actual = digest(child(source,name))
        if actual != checksum: raise ValueError('frozen source hash differs: '+name)
        files[name] = actual
    originals = {p.relative_to(raw).as_posix():digest(p) for p in sorted(Path(raw).rglob('*.json'))}
    if not {'IDENTITY.json','TRANSFER.json'} <= set(originals): raise ValueError('IDENTITY and TRANSFER required')
    for name in originals: child(raw,name)
    return dict(schema=1,execution_commit=execution['commit'],source_files_sha256=files,raw_files_sha256=originals,
                reporter_sha256=digest(reporter),evidence_files_sha256={n:digest(p) for n,p in evidence.items()})


def reusable_review(review, inputs):
    review = Path(review)
    if not review.exists(): return False
    binding, reports = review/'CHECKPOINT_INPUTS.json', review/'CHECKPOINT_REPORTS.json'
    if not binding.is_file() or load(binding)!=inputs or not reports.is_file():
        raise ValueError('existing review lacks identical input/source binding; use a new label')
    expected = load(reports)
    if set(expected)!={'REVIEW.json','REVIEW_ZH.md'}: raise ValueError('invalid checkpoint report manifest')
    for name, checksum in expected.items():
        if digest(review/name)!=checksum: raise ValueError('immutable review changed: '+name)
    return True


def archive(label, root=ROOT, tree=TREE):
    valid_label(label); root,tree=Path(root).resolve(),Path(tree).resolve()
    execution,job_info=load(root/'FULL_V2_EXECUTION.json'),load(root/'GPU_FULL_V2_JOB.json')
    commit,job=execution['commit'],str(job_info['job']); key=commit[:12]
    if job_info['commit']!=commit: raise ValueError('job/execution commit mismatch')
    raw,source=root/'formal_results'/key,root/('source_'+key)
    for name,checksum in execution['files'].items():
        payload=subprocess.check_output(['git','-C',str(tree),'show',commit+':'+name])
        if hashlib.sha256(payload).hexdigest()!=checksum: raise ValueError('Git source hash differs: '+name)
        freeze(child(source,name),payload)
    freeze(source/'EXECUTION.json',encoded(execution))
    evidence=evidence_files(root,job); state=scheduler_state(root,job); reporter=tree/'qwen3/sparq/report.py'
    inputs=input_snapshot(raw,source,execution,reporter,evidence); review=root/('review_'+label)
    if not reusable_review(review,inputs):
        pending=review.with_name(review.name+'.pending_'+uuid.uuid4().hex)
        subprocess.run([sys.executable,'-X','utf8','-B','-m','qwen3.sparq.report',str(raw),'--output',str(pending),
                        '--source-root',str(source)],cwd=tree,check=True)
        if input_snapshot(raw,source,execution,reporter,evidence)!=inputs:
            raise ValueError('inputs changed during review; pending output preserved; retry new label')
        freeze(pending/'CHECKPOINT_INPUTS.json',encoded(inputs))
        freeze(pending/'CHECKPOINT_REPORTS.json',encoded({n:digest(pending/n) for n in ('REVIEW.json','REVIEW_ZH.md')}))
        pending.rename(review)
    report=load(review/'REVIEW.json')
    if report['identity']['source_commit']!=commit or not report['identity']['local_source_bytes_verified']:
        raise ValueError('review did not verify the frozen execution sources')
    out=tree/'qwen3/sparq/results'/key
    for name,checksum in inputs['raw_files_sha256'].items():
        path=child(raw,name)
        if digest(path)!=checksum: raise ValueError('download changed before archive: '+name)
        dest=out/'raw'/name
        if name=='TRANSFER.json':
            freeze(out/'reviews'/label/name,path.read_bytes())
            current(dest,path.read_bytes())
        else: freeze(dest,path.read_bytes())
    for path in sorted(review.iterdir()):
        if path.is_file(): freeze(out/'reviews'/label/path.name,path.read_bytes())
    freeze(out/'reviews'/label/'SCHEDULER.json',encoded(state))
    freeze(out/'.gitattributes',b'raw/** -text\nreviews/** -text\n')
    current(out/'LATEST_REVIEW.json',encoded(dict(review='reviews/'+label+'/REVIEW.json',markdown='reviews/'+label+'/REVIEW_ZH.md',
        transfer='reviews/'+label+'/TRANSFER.json',status=report['status'],scheduler=state)))
    work=tree/'work/amlink1219/157'; receipts=work/('formal_'+job)/'checkpoints'/label
    for name,path in evidence.items():
        if digest(path)!=inputs['evidence_files_sha256'][name]: raise ValueError('receipt changed during archive: '+name)
        freeze(receipts/name,path.read_bytes())
    freeze(receipts/'CHECKPOINT_INPUTS.json',encoded(inputs)); freeze(receipts/'SCHEDULER.json',encoded(state))
    attr=work/'.gitattributes'; content=attr.read_text(encoding='utf-8') if attr.exists() else ''
    line='formal_'+job+'/** -text\n'
    if line not in content: current(attr,(content+('' if not content or content.endswith('\n') else '\n')+line).encode('utf-8'))
    now=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
    progress,conclusion=progress_text(report); state_line=scheduler_text(state)
    action=('全部质量结果已核验，准备复核交付；调度终态仍按保存证据单独判断。' if report['complete'] else
            '作业已到终态；先核日志和未完成部件，保留完成分片，不自动重放作业。' if state['terminal'] else
            '继续只读核调度状态并归档新完成分片；没有新观测时不推断作业终态。')
    handoff=f'''# Issue157 当前执行与交接

更新时间：{now}。唯一目标 `{REPO}`；认证 `amlink1219`；分支 `task/157-sparq-qwen3`；[PR163](https://github.com/{REPO}/pull/163) 待审、未自动合并，依赖 PR147@357db588。

## 已核验结果

最新独立复核：[REVIEW_ZH.md](../../../../qwen3/sparq/results/{key}/reviews/{label}/REVIEW_ZH.md)，结论 `{report['status']}`。

{progress}

{conclusion}

{benchmark_text(report)}

## 调度证据和恢复入口

{state_line}

固定执行提交 `{commit}`；后训练 `Qwen/Qwen3-4B@1cfa9a7208912126459214e8b04321603b3df60c`，原 FFN。CPU 依赖 {job_info.get('dependency','见回执')} 历史终态见回执，不能代替当前 GPU 状态。

- 个人远端根 `{job_info['project']}`；不变源 `{job_info['source']}`；结果 `results/{key}`；日志 `logs/full-{job}.out`、`.err`。
- 环境 `env-v2/bin/python`，Torch2.7.1+cu128、TF4.51.3、lm_eval0.4.8；模型10文件及语料已登记 SHA。本次只重建并核固定源码，不重新下载权重。
- 命令 `python -B -m qwen3.sparq.run --root {job_info['project']} --phase full --batch 32 --ppl-chunk 32 --task-chunk 256 --diagnose-document-batching`，只能在原 Slurm 分配中运行，不能在登录节点直接执行。
- WT2 2048/1024；正式 MC 逐题/choice_batch4，每256题分片落盘；分片大小不是跨题 batch。
- 本检查点下载清单为 `reviews/{label}/TRANSFER.json`；raw/TRANSFER 是可更新的最新下载索引，每版原件按检查点保存。报告、输入哈希、调度终态和日志均按检查点冻结。

## 验证和负结果

{gate_text(report)}

历史 CPU/原生 logits 门禁、环境失败与候选失败回执保留，不把历史调度记录当作当前执行状态。

## 下一步及边界

1. {action} 只有完整 SUMMARY、全部目标/题目和正式门禁通过才标 complete。
2. 当前本人 GPU 作业结束并核本人队列后，才可另冻计量源补板级功率。补测关联原质量 identity 和新测量 SHA，不能混写原 `{key}` 结果。
3. [EDA_HANDOFF_ZH.md](../../../../architecture_tlm/sparq_baseline/EDA_HANDOFF_ZH.md)已交接并通知 jieruiz；完整 SparQ RTL/STA 尚缺，物理 ASIC 面积、功率、真实延迟为 null。
4. Projects 与 Zotero 的限制、待办保留在回执，不声称待同步/待入库已完成。Issue116/123 继续暂停，不访问他人 home/工艺库，不上传权重/凭据，不自动合并或重复提交作业。
'''
    current(work/'HANDOFF.md',handoff.encode('utf-8'))
    status=tree/'progress/amlink1219/STATUS.md'; old=status.read_text(encoding='utf-8')
    marker='# Issue116 已暂停（用户明确要求，2026-10-23）'
    if marker not in old: raise ValueError('STATUS preservation marker missing')
    header=f'''# Issue157：后训练 Qwen3-4B SparQ（{now}）

[PR163](https://github.com/{REPO}/pull/163) 待审、未自动合并；固定执行源 `{commit}`。{state_line}

独立复核 `{report['status']}`；{conclusion}

{progress}

{benchmark_text(report)}

见[完整报告](../../qwen3/sparq/results/{key}/reviews/{label}/REVIEW_ZH.md)及[交接](../../work/amlink1219/157/HANDOFF.md)。正式 MC 逐题，跨题候选失败保留；完整 RTL/STA/PPA 尚缺，116/123 仍暂停。

---

'''
    current(status,(header+old[old.index(marker):]).encode('utf-8'))
    manifest={p.relative_to(work).as_posix():digest(p) for p in sorted(work.rglob('*')) if p.is_file() and p.name!='ARTIFACTS.json'}
    current(work/'ARTIFACTS.json',encoded(manifest))
    result=dict(archived=str(out),review=label,files=len(manifest),status=report['status'],scheduler=state)
    print(json.dumps(result,ensure_ascii=False)); return result


def self_test():
    import unittest
    class Tests(unittest.TestCase):
        def test_freeze_never_overwrites(self):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
                path=Path(tmp)/'x'; freeze(path,b'old'); freeze(path,b'old')
                with self.assertRaises(ValueError): freeze(path,b'new')
                self.assertEqual(path.read_bytes(),b'old')
        def test_reuse_requires_binding_and_untampered_reports(self):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
                path=Path(tmp)/'review'; path.mkdir(); inputs={'source':'a','transfer':'b'}
                with self.assertRaises(ValueError): reusable_review(path,inputs)
                for name in ('REVIEW.json','REVIEW_ZH.md'): freeze(path/name,b'test')
                freeze(path/'CHECKPOINT_INPUTS.json',encoded(inputs))
                freeze(path/'CHECKPOINT_REPORTS.json',encoded({n:digest(path/n) for n in ('REVIEW.json','REVIEW_ZH.md')}))
                self.assertTrue(reusable_review(path,inputs))
                with self.assertRaises(ValueError): reusable_review(path,dict(inputs,transfer='changed'))
                (path/'REVIEW.json').write_bytes(b'tampered')
                with self.assertRaises(ValueError): reusable_review(path,inputs)
        def test_scheduler_terminal_and_wrong_job(self):
            with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
                root=Path(tmp); self.assertEqual(scheduler_state(root,2878)['state'],'UNKNOWN')
                (root/'gpu_FULL_V2_latest_state.txt').write_text('JobId=999 JobState=RUNNING')
                self.assertEqual(scheduler_state(root,2878)['state'],'UNKNOWN')
                (root/'gpu_FULL_V2_terminal_state.txt').write_text('JobId=2878 JobState=TIMEOUT ExitCode=0:0')
                (root/'gpu_FULL_V2_latest_state.txt').write_text('JobId=2878 JobState=RUNNING ExitCode=0:0')
                self.assertEqual(scheduler_state(root,2878)['state'],'TIMEOUT')
        def test_labels_and_paths(self):
            for bad in ('../x','a/b','a-b','','中文'):
                with self.assertRaises(ValueError): valid_label(bad)
            self.assertEqual(valid_label('ppl_complete_01'),'ppl_complete_01')
            with self.assertRaises(ValueError): child(ROOT,'../bad')
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    if not result.wasSuccessful(): raise SystemExit(1)


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if argv==['--self-test']: return self_test()
    if len(argv)!=1: raise SystemExit('usage: archive_checkpoint.py LABEL | --self-test')
    archive(argv[0])


if __name__=='__main__': main()
