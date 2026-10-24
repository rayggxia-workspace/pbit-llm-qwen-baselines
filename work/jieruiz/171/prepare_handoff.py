from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[3]
D=ROOT/'work/jieruiz/171'
s=(ROOT.parent/'qwen3-qat-plan-issue159-20261023/work/jieruiz/159/publish.py').read_text(encoding='utf-8').split("if __name__=='__main__':")[0]
s=s.replace('task/159-qwen3-sc-qat-plan','task/171-nonlinear-width').replace('2f23344948cfd43e9ab7061f77ea6d3f4a2c2527','1d16d8ccddd17e2b94c705b7871d7708e36577f2')
s=s.replace("'qwen3/training/sc_qat_20261023/', 'work/jieruiz/159/'", "'qwen3/nonlinear_width/', 'qwen3/results/nonlinear_width_20261024/', 'work/jieruiz/171/'")
(D/'github.py').write_bytes(s.encode())
v=dict(job_id=2880,execution_commit='71cb58d0b4cfbf42004c34e28d5b5250f6a000c8',
       root='/home/Hongjie_Zeng/projects/pbit-qwen3-nonlinear-width-20261024-issue171',snapshot='snapshot-71cb58d0',
       package_sha256='4facab9b04e04da257d931ea9ddb08dce3a617f79ff5270f191957f39287c307',
       server_preflight_tests_passed=6,status_at_receipt='RUNNING',planned_cases=28)
(D/'SUBMISSION.json').write_bytes((json.dumps(v,indent=2)+'\n').encode())
note='''## Issue171 Qwen3非线性位宽初筛（2026-10-24）

负责人jieruiz；task/171-nonlinear-width；目录tmp/qwen3-nonlinear-width-issue171-20261024；base PR169@1d16d8cc，拟PR base task/168-qwen3-fixed-scale，依赖其推理源码。Slurm2880已运行，执行71cb58d0冻结；服务器6项预检通过，28项后缀PPL（16×128目标），36层全部替换。非线性使用有限码/LUT的条件均值，不是有限三流AND采样；矩阵恢复仍为FP32参考。W8单因素扫描及固定四档T64三seed组合；无训练/RTL/PPA。模型/数据复用已验证manifest。成果root与包SHA见SUBMISSION.json。完成后核验complete.json的documents SHA、28唯一配置和层覆盖，勿重复提交。Projects未同步；发布回执待补。

'''
(D/'HANDOFF.md').write_bytes(note.encode())
for path in (ROOT/'progress/jieruiz/STATUS.md',ROOT/'PROJECT_MEMORY_ZH.md'):
    path.write_bytes(note.encode()+path.read_bytes())
c=ROOT.parents[1]/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md'
m=ROOT.parents[1]/'PROJECT_MEMORY_ZH.md'
assert c.read_bytes()==m.read_bytes()
c.write_bytes(note.encode()+c.read_bytes());m.write_bytes(c.read_bytes())
(D/'PR_BODY.md').write_bytes('''关联Issue #171；依赖PR #169。对后训练Qwen3-4B全部36层FFN，分离g/u幅度、sigmoid驱动和输出概率位宽的小型后缀PPL。28配置，TRAIN冻结PoT范围，单因素+固定四档T64三seed组合。

本地4项格式/模块测试、服务器6项预检通过；Slurm2880运行，执行71cb58d0冻结。非线性为条件均值，不含有限AND采样；FP32矩阵恢复参考不冒称bittrue。没有训练、完整WT2或PPA。完成数据核验后更新本PR。
'''.encode())
