import ast, hashlib, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
DOC=ROOT/'qwen3/training/sc_qat_20261023'
PY='C:/Users/86134/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
def dump(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
result=subprocess.run([PY,str(DOC/'scan.py')],capture_output=True,text=True,check=True)
report=json.loads(result.stdout)
guard=subprocess.run([PY,str(DOC/'scan.py'),'--require-launch-ready'],capture_output=True,text=True)
assert guard.returncode!=0
for p in DOC.glob('*.json'):json.loads(p.read_bytes())
ast.parse((DOC/'scan.py').read_text(encoding='utf-8'))
env=json.loads((DOC/'REMOTE_ENV.example.json').read_bytes())
res=json.loads((DOC/'RUN_RESULT.example.json').read_bytes())
assert env['weight_bits_sweep']==[4,6,8]
assert res['ffn']['weight_bits'] is None and res['status']=='not_run'
assert 'per_seed_results' in res['evaluation']['full_wt2']
assert res['all_results_above_are_placeholders'] and not env['data']['license_and_access_confirmed']
report.update(launch_guard_rejected=True,all_json_parse_pass=True,python_ast_pass=True,
              result_template_control_and_per_seed_fields_pass=True,
              independent_review='remote_handoff_audit: G2/seed/bitwidth clarifications incorporated',
              revision_reference='PR160@989546376f2295990b7712ea553615f0b8d88cb4',
              server_queue_queried=False,slurm_jobs_submitted=0)
dump(OUT/'VALIDATION.json',report)
index={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
       for p in sorted(DOC.iterdir()) if p.is_file()}
dump(OUT/'ARTIFACT_INDEX.json',index)
dump(ROOT/'work/jieruiz/159/ARTIFACT_INDEX.json',index)
entry='''## Issue159远程执行交接v2：INT4/INT6/INT8（2026-10-23）

用户要求面向远程Agent，并增加INT4/INT6，其他设置不变、工作3倍。正式入口qwen3/training/sc_qat_20261023/REMOTE_AGENT_START_HERE_ZH.md，附环境/逐seed结果JSON模板。每项实验36层gate/up/down统一Wb，三套各19项=57计划（48随机+9控制，A总114亿有效token）；BF16三个是配对重复，不是三位宽结构或三训练seed。输入仍A8、共享64、原尺度/采样/优化器设置保持，跨位宽清单一致性通过。

补明确源码/依赖、待实现模块、独立120步G2课程、checkpoint随机重放、位宽/容器区别、Slurm及回传门槛。PR160已有非Base准备，revision1cfa9a7208912126459214e8b04321603b3df60c；依赖读取head98954637，22:45交接的2869/2870状态不当实时队列，恢复先查避免重复。本任务无新训练器/GPU/Slurm/PPL；v2清单/模板/启动拒绝与独立审阅通过。继续同PR161，实际发布见work/jieruiz/159/remote_agent_v2/PUBLICATION.json；不合并不关闭，Projects待权限。

'''
for p in [ROOT/'PROJECT_MEMORY_ZH.md',ROOT/'progress/jieruiz/STATUS.md',ROOT/'work/jieruiz/159/HANDOFF.md']:
    old=p.read_bytes()
    if 'Issue159远程执行交接v2'.encode() not in old:p.write_bytes(entry.encode()+old)
workspace=ROOT.parents[1]
canonical=workspace/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md'
mirror=workspace/'PROJECT_MEMORY_ZH.md'
old=canonical.read_bytes();assert old==mirror.read_bytes()
if 'Issue159远程执行交接v2'.encode() not in old:
    canonical.write_bytes(entry.encode()+old);mirror.write_bytes(canonical.read_bytes())
(OUT/'REVIEW_ZH.md').write_bytes('''# 远程Agent交接审阅

独立只读审阅确认可取得源码并区分现成命令和待实现模块。已补PR160依赖与锁定revision，旧队列状态明确为交接时点。

修复：G2不能机械沿用200M课程，改独立120步并覆盖目标T32及L冻结；结果模板增加实际命令/源码manifest/逐seed NLL与原件SHA，BF16控制字段不假写8位；INT4/6/8明确为每项实验所有FFN矩阵统一位宽，A8保持，容器与逻辑位宽分开。

最终scan.py通过57配置=48随机+9控制、114亿计划有效token、三位宽非权重设置完全一致。未实现或运行训练，无新PPL/硬件测试。
'''.encode())
(ROOT/'work/jieruiz/159/PR_BODY.md').write_bytes('''面向远程Agent提供可执行的Qwen/Qwen3-4B非Base训练交接：固定源码与模型revision、依赖PR160复用、待实现模块、先导验证、Slurm组织及结果回传模板。新增INT4/INT6，与INT8各执行原完整一套，其余设置保持。

主扫描为48随机配置+9控制=57项（每位宽19项，A计划114亿有效训练token）。每项实验36层gate/up/down统一Wb，输入仍A8/共享64；三份BF16为配对重复，不作三种量化结构或三seed。B阶段每位宽最多18、合计54；C/D同样按各位宽原预算。

入口：qwen3/training/sc_qat_20261023/REMOTE_AGENT_START_HERE_ZH.md，附REMOTE_ENV/RUN_RESULT模板、SCAN_MANIFEST与原设计依据。PR147/153只读oracle；PR160已有非Base准备，恢复先检查现有任务。

验证：57项唯一任务ID/码界/跨位宽非权重设置一致、JSON与Python语法、未就绪启动拒绝、独立审阅通过。G2独立120步短课程覆盖目标采样及尺度冻结。无本任务训练器、H200/Slurm作业、新PPL/PPA。关联Issue159；通过本PR交付设计，不自动合并。
'''.encode())
print(json.dumps(report))
