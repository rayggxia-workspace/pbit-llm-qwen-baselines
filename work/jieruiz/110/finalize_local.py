"""Maintain same-byte reading mirrors and append project workflow, preserving history."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

REPO=Path(__file__).resolve().parents[3]
LOCAL=Path('C:/Users/86134/Documents/a_P_BIT')
OUT=Path(__file__).resolve().parent
reg=REPO/'digital_circuit_simulation_registry'
spec=importlib.util.spec_from_file_location('registry',reg/'registry.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
result=m.check(True,True)
assert result['status']=='PASS'
(OUT/'VALIDATION.json').write_text(json.dumps(dict(**result,unit_guard_tests=8,
    commands=['python -m unittest discover -s digital_circuit_simulation_registry -p test_registry.py -v',
              'python digital_circuit_simulation_registry/registry.py check --local --members'],
    no_new_eda=True),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
rule='''
## 数字电路仿真统一台账（用户2026-10-22要求，Issue110）

- 所有LLM相关数字模块及共用随机源新增仿真，必须在同一任务PR内新增或补全 `digital_circuit_simulation_registry/records/` 的run记录，并运行registry.py的check/render，更新总览。维护入口是该目录README_ZH.md；本机固定阅读副本为 `C:/Users/86134/Documents/a_P_BIT/digital_circuit_simulation_registry/`。不再另建互不相通的功耗台账。
- 登记准确执行源码/manifest与配置SHA、原始结果路径或归档成员、原字节SHA-256、工艺/PVT/频率/位宽/激励/seed/窗口、模块边界和未计成本；功能、综合、STA、PT、后布局分别写实际状态。待跑、失败、仅功能、库提取、TLM估计不能写成已测PPA；功耗算出但时序违例/告警须保留。
- 台账只存小型索引/必要数值，不复制大波形/网表/工艺库；同一实验多副本或重汇总不算新实验。新run保留旧失败/负结果。清理结果所在临时目录前，先把台账补为可恢复归档路径/成员和SHA。没有本机或共享存储权限时明确待补，不宣称远端可访问。
- 工作区正式版本为仓库同名目录；本机根目录仅同字节阅读镜像。更改后同步镜像、本人STATUS/HANDOFF与长期备忘录；未合并维护分支先引用最新PR，避免并发覆盖。
'''
for p in [REPO/'AGENTS.md',LOCAL/'AGENTS.md']:
    b=p.read_bytes();s=b.decode('utf-8-sig')
    if '## 数字电路仿真统一台账（' not in s:
        p.write_bytes(b+rule.encode('utf-8'))
canonical=LOCAL/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md'
root=LOCAL/'PROJECT_MEMORY_ZH.md'
old=canonical.read_bytes();assert old==root.read_bytes(),'canonical/read mirror changed; reconcile before edit'
title='## 2026-10-22 数字电路仿真统一台账（Issue110）'
if title not in old.decode('utf-8'):
    appendix='''

## 2026-10-22 数字电路仿真统一台账（Issue110）

用户要求集中记录已有数字电路PPA并每次新增登记。正式入口digital_circuit_simulation_registry/README_ZH.md，本机同名固定目录为同字节阅读副本；任务task/110-circuit-simulation-registry，独立稀疏tmp/circuit-registry-issue110-20261022。35条批次/模块记录、516行配置/seed/窗口；117个数字原始归档逐SHA发现索引，不把发现未审等同成功。精确结果地址见01_结果地址索引.md及artifact_locations.csv；records保留源绑定/PVT/频率/边界/限制和各阶段状态。

已纳入37962470/37981139/38015538随机矩阵、SS SRAM/DFF主模块与S0–S5、14组SS/TT宏库提取、CACTI估计单列、38100634 TT/SS Q10 SwiGLU、38322118四随机服务核心×三频率252窗口，以及转换/短流/Issue107功能证据与失败历史。共享p-bit后端独立交叉索引，较新38165794/38215256/38263376归档待完整审核，不能用旧报告断言其未完成。120.8uW旧预算缺直接绑定原件，未冒列为本次确认PPA。

157个可访问独立文件原字节SHA与26个tar成员SHA核对通过，8项登记守卫测试通过，无原件缺失；未重新运行RTL/DC/PT/STA/GPU/PPL，不重放全部VCD。所有已算PPA仍保留前/后布局、时序/X/库表告警等限制；新数字v1没有PPA。未搬移/删除/复制大原始结果。AGENTS新增每次仿真登记规则；新结果同任务PR更新台账/总览，清理目录前更新归档恢复地址。当前本地完成，推送/PR状态以work/jieruiz/110/PUBLICATION.json实际回执为准；不自动合并。Projects缺read:project待同步。
'''
    s=old.decode('utf-8');s=s.replace('## 0 恢复工作先读这里','## 0 恢复工作先读这里\n\n> 数字电路仿真统一台账：digital_circuit_simulation_registry/README_ZH.md。新增仿真必须登记原件路径/SHA和实际阶段；35记录/117归档初版见文末Issue110。',1)
    data=(s+appendix).encode('utf-8')
    assert canonical.read_bytes()==old and root.read_bytes()==old
    canonical.write_bytes(data);root.write_bytes(data)
(REPO/'PROJECT_MEMORY_ZH.md').write_bytes(root.read_bytes())
readme=REPO/'README.md';s=readme.read_text(encoding='utf-8')
if 'digital_circuit_simulation_registry/README_ZH.md' not in s:
    s=s.replace('# p-bit LLM：Qwen / LLaMA-1 / Llama 2','# p-bit LLM：Qwen / LLaMA-1 / Llama 2\n\n数字电路功耗/面积证据统一从 [仿真台账](digital_circuit_simulation_registry/README_ZH.md) 查找；逐项记录原件地址、SHA和功能/综合/STA/PT状态。',1)
    readme.write_text(s,encoding='utf-8',newline='\n')
# Small metadata mirror only. No copytree, waves, libraries, binaries or stale helper files.
mirror=LOCAL/'digital_circuit_simulation_registry'
for p in reg.rglob('*'):
    if p.is_file() and '__pycache__' not in p.parts:
        dest=mirror/p.relative_to(reg);dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and dest.read_bytes()!=p.read_bytes():
            raise RuntimeError('Existing reading mirror differs; inspect before replacing '+str(dest))
        dest.write_bytes(p.read_bytes())
assert all((mirror/p.relative_to(reg)).read_bytes()==p.read_bytes() for p in reg.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
print(json.dumps(result,ensure_ascii=False))
