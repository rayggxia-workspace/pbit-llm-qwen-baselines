import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];W=ROOT.parent.parent
url='https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/134'
note='\n2026-10-23 Issue95发布回执：网络已恢复，分层质量实现/结果已上传PR134（'+url+'），开放待审未合并；科学交付1f8e1d468792b5af17d337db885b482c189c00f9。完整远端tree与本地c8162a04b3c32bd0d5615108d8dc7b93bdf0b1ee相同，报告读回逐字符一致。旧网络阻塞文字仅为先前时点，无需重复实验。\n'
for path in ('PROJECT_MEMORY_ZH.md','progress/rayggxia/STATUS.md','work/rayggxia/95/quality/HANDOFF.md'):
    p=ROOT/path;raw=p.read_bytes()
    if note.encode('utf-8') not in raw:p.write_bytes(raw+note.encode('utf-8'))
canonical=W/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';mirror=W/'PROJECT_MEMORY_ZH.md'
old=canonical.read_bytes()
if mirror.read_bytes()!=old:raise ValueError('memory changed independently')
if note.encode('utf-8') not in old:
    if canonical.read_bytes()!=old or mirror.read_bytes()!=old:raise ValueError('memory race')
    canonical.write_bytes(old+note.encode('utf-8'));mirror.write_bytes(old+note.encode('utf-8'))
p=ROOT/'work/rayggxia/95/quality/PUBLICATION.json';data=json.loads(p.read_text(encoding='utf-8'))
data.update(pushed=True,pr=url,merged=False,blocker=None,scientific_remote_commit='1f8e1d468792b5af17d337db885b482c189c00f9',
            remote_tree_equal_local=True,remote_report_readback_equal=True,projects_sync='unavailable tool; pending')
p.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8',newline='\n')
registry_note='\nIssue95分层随机质量189案例已通过PR134发布（'+url+'，待审未合并），run `rng-quality-95-20261023` 为DESIGN_PROOF，不能当作新RTL/PPA或熵认证；其他并行记录保持。\n'
for base in (ROOT,W):
    p=base/'digital_circuit_simulation_registry/README_ZH.md';raw=p.read_bytes()
    if registry_note.encode('utf-8') not in raw:p.write_bytes(raw+registry_note.encode('utf-8'))
print('publication receipt, memory and registry reference appended')
