"""Append current task evidence without replacing concurrent task records."""
import hashlib,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
WORKSPACE=ROOT.parent.parent
stamp='2026-10-23 Issue95 分层随机质量首轮'
addition='''
## 2026-10-23 Issue95 分层随机质量首轮

负责人rayggxia；task/95-rng-quality，tmp/rng-quality-issue95-20261023，基线6966739a。复用38237164已有Spectre原始9条轨迹，189案例（两端点各4096帧）与30调理/36抽样诊断完成，9机制测试及1269原件/算术/结构核对通过。质量不是自动逐层改善：旧比较器VN后P1近50%仍有负时间相关；GF64在q128前4路严格xor=0；重复种子使三后端两端点同流。无新Spectre/RTL/PT/LLM/PPL，不认证熵率或最佳换种周期；两个独立电路记录不是同一物理噪声因果链，缺同时多路阵列记录。

入口architecture_tlm/random_service/quality/README_ZH.md及results/20261023/REPORT.html；用户副本远端上传/rng_quality_20261023.html。稳定原件project_archives/rng_quality_20261023，SOURCE_MANIFEST绑定8文件，执行本地8a862a38cf6e4e46f50e719f8b2b3877db745c75。中央run rng-quality-95-20261023为DESIGN_PROOF，PPA未运行；新增record单独同步固定入口，保留其他并行记录，不用旧catalog覆盖。当前本地完成；发布前GitHub连接器出现HTTP传输错误，远端发布状态以work/rayggxia/95/quality/PUBLICATION.json为准。恢复见同目录HANDOFF，不重复实验。
'''
for p in (ROOT/'PROJECT_MEMORY_ZH.md',):
    text=p.read_text(encoding='utf-8')
    if stamp not in text:p.write_text(text+addition,encoding='utf-8',newline='\n')
canonical=WORKSPACE/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md'
mirror=WORKSPACE/'PROJECT_MEMORY_ZH.md'
old=canonical.read_bytes()
if mirror.read_bytes()!=old:raise ValueError('memory mirror differs; refuse overwrite')
if stamp not in old.decode('utf-8'):
    new=old+addition.encode('utf-8')
    # Preserve all existing bytes, including concurrently maintained history.
    if canonical.read_bytes()!=old or mirror.read_bytes()!=old:raise ValueError('memory changed during update')
    canonical.write_bytes(new);mirror.write_bytes(new)
record=ROOT/'digital_circuit_simulation_registry/records/rng-quality-95-20261023.json'
fixed=WORKSPACE/'digital_circuit_simulation_registry'
spec=importlib.util.spec_from_file_location('fixed_registry',fixed/'registry.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
target=fixed/'records'/record.name
if target.exists():
    if target.read_bytes()!=record.read_bytes():raise ValueError('existing fixed record differs')
else:module.add(record)
print(json.dumps(module.check(),ensure_ascii=False))
status=ROOT/'progress/rayggxia/STATUS.md';text=status.read_text(encoding='utf-8')
if stamp not in text:
    status.write_text('# '+stamp+'\n\n负责人rayggxia；本地已完成，待上传。分支task/95-rng-quality，base pbit-tlm-attention-details-20261016@6966739a；目录tmp/rng-quality-issue95-20261023。189案例/9测试/1269核对及浏览器通过；无新EDA/PPL。正式入口architecture_tlm/random_service/quality/README_ZH.md；交接work/rayggxia/95/quality/HANDOFF.md，发布回执同目录PUBLICATION.json。GitHub发布前HTTP传输异常，Projects无可用操作；不写远端已交付。根记忆canonical/mirror已保留原增量同步，中央台账仅添加新run并重建总览。下一步恢复网络后刷新远端，保留其他record合并catalog，再上传PR。\n\n'+text,encoding='utf-8',newline='\n')
receipt=dict(date='2026-10-23',issue=95,branch='task/95-rng-quality',base='6966739a5223680888bf0315f7bb4f73423a1ae6',
 local_complete=True,pushed=False,pr=None,blocker='GitHub connector HTTP transport failure during pre-publication refresh',
 execution_commit='8a862a38cf6e4e46f50e719f8b2b3877db745c75',
 source_manifest_sha256=hashlib.sha256((ROOT/'architecture_tlm/random_service/quality/results/20261023/SOURCE_MANIFEST.json').read_bytes()).hexdigest())
(ROOT/'work/rayggxia/95/quality/PUBLICATION.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
