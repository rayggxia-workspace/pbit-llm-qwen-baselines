"""Record the verified remote science tree without overwriting other task memories."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[4]
ws=Path('C:/Users/86134/Documents/a_P_BIT')
here=Path(__file__).parent
record=dict(repository='rayggxia-workspace/pbit-llm-qwen-baselines',issue=95,pr=188,
    branch='task/95-ideal-quality-20261025',base='pbit-tlm-attention-details-20261016',
    previous_remote_head='057629881fcbf0704c87b70393bce1437edacae2',
    science_remote_commit='2fa6e67a216b9e59e96918f66f3dcc852a12a2c8',
    science_local_commit='317b1fe7f284bbf40d139c82908034051ad7b175',
    equal_tree='2649f52c96b7a6048d466437fa4c67ca462c21bd',
    publication='GitHub API; exact committed UTF-8 blobs; leased fast-forward',
    state='PR open, not merged; Issue95 remains open',
    projects='not verified or synchronized; pending authorized maintainer',
    raw_archive='C:/Users/86134/Documents/a_P_BIT/project_archives/rng_correlation_20261025',
    note='A subsequent receipt-only commit does not change the frozen execution or result bytes.')
(here/'PUBLICATION.json').write_bytes((json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
entry='''## 2026-10-25 Issue95 / PR188 全路相关性增量已发布

新增18物理播种长流＋18同形状IID对照已上传PR188，远端科学提交2fa6e67a216b9e59e96918f66f3dcc852a12a2c8；tree2649f52c96b7a6048d466437fa4c67ca462c21bd与本地317b1fe7逐文件相同。此前225例保留。报告与CSV已在远端上传/目录交付；中央run rng-correlation-95-20261025，分支58/root66记录check通过，180份CSV矩阵对源NPZ一致。PR开放待审，未合并，不关闭Issue95；Projects待有权限维护者同步。准确发布/恢复入口work/rayggxia/95/correlation_20261025/PUBLICATION.json及RECOVERY_INDEX.json。三个物理noise seed非空间通道，1s周期换种未触发，GF64联合结构问题仍保留。

'''
def prepend(p):
    old=p.read_bytes()
    if entry.encode('utf8') not in old:p.write_bytes(entry.encode('utf8')+old)
for p in [root/'PROJECT_MEMORY_ZH.md',root/'progress/rayggxia/STATUS.md',here/'HANDOFF.md']:prepend(p)
canonical=ws/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md'
mirror=ws/'PROJECT_MEMORY_ZH.md'
assert canonical.read_bytes()==mirror.read_bytes()
prepend(canonical);mirror.write_bytes(canonical.read_bytes())
print('publication receipt saved; canonical memory mirrored')
