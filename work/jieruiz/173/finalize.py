import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HOME=ROOT.parents[1]
OUT=ROOT/'work/jieruiz/173'
archive=HOME/'project_archives/qwen3_and_direct_20261024'
def save(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
package=json.loads((OUT/'PACKAGE.json').read_bytes())
src=Path(package['path']);dst=archive/src.name
if src.exists():
    assert hashlib.sha256(src.read_bytes()).hexdigest()==package['sha256']
    if dst.exists():assert dst.read_bytes()==src.read_bytes()
    else:shutil.copyfile(src,dst)
    src.unlink()
save(archive/'RECOVERY.json',dict(source_archive=str(dst),source_sha256=package['sha256'],
    results_archive=str(archive/'sealed-2881.tar.gz'),results_sha256='1f87f6f00a9ffda47ca03b0bca0d55d2236e6fe99cacd5c6bf88f9eed4d54309',
    execution=package['commit'],issue=173,pr=174,branch='task/173-and-direct-wd'))
save(OUT/'SUBMISSION.json',dict(job_array=2881,shards=list(range(5)),execution_commit=package['commit'],
    root='/home/Hongjie_Zeng/projects/pbit-qwen3-and-direct-20261024-issue173',snapshot='snapshot-098c7a00',
    package_sha256=package['sha256'],server_preflight_tests_per_shard=12,
    status='all five completed JSON verified',physical_scored_results=27,unique_scored_configs=23,
    local_test_status='9 passed; CUDA skipped; runner unavailable locally (transformers absent); all12 passed remotely'))
entry='''## Issue173有限AND直连Wd完成（2026-10-24）

Slurm2881五片完成，执行098c7a00db27dded1b7047dc5828871e4b057f70。每片12项检查通过，包括GPU有界整数GEMM与逐拍事件累加参考。27份封存计分/23唯一配置、documents与sidecar SHA、36层全前缀覆盖通过。后训练Qwen3-4B，8×128=1024目标后缀，非完整WT2；准确Attention。BF16五次完全一致13.566049，W8 13.414964；旧8位均值z再编码三seed13.428421，直连均值原尺度13.517797、有限系数13.498204。有限三流直连T64/256/1024/4096三seed分别8949057.252807/7735.004324/30.692997/14.937278。首层平均AND概率0.000910389，T64零事件95.02%；不能用旧均值PPL支持短流直连，也不能认为8位门限只需256次就充分。

新路径：幅度8+符号/驱动signed8/概率8+true-one，独立三流AND事件跨Wd输出共享；Wd固定W8，有限恢复系数16位、signed52输出累加、整数RNE BF16。无z重新统计/定标/采样。gate/up恢复仍FP32参考，无训练、RTL或PPA。建议先解决SgSu和稀少事件问题，再冻结训练硬件前向；勿把当前T64直连直接当可用训练配置。

负责人jieruiz/task/173-and-direct-wd，目录tmp/qwen3-and-direct-issue173-20261024，PR174依赖PR172，待审未合并。报告qwen3/results/and_direct_20261024/REPORT_ZH.md；归档project_archives/qwen3_and_direct_20261024/sealed-2881.tar.gz，SHA1f87f6f00a9ffda47ca03b0bca0d55d2236e6fe99cacd5c6bf88f9eed4d54309，RECOVERY.json包含源包恢复。无运行任务或新增定时；Projects未同步。结果远端发布以FINAL_PUBLICATION.json为准，勿重交。

'''
for p in (ROOT/'progress/jieruiz/STATUS.md',ROOT/'PROJECT_MEMORY_ZH.md'):
    text=p.read_text(encoding='utf-8')
    if not text.startswith(entry):p.write_bytes((entry+text).encode())
canonical=HOME/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';mirror=HOME/'PROJECT_MEMORY_ZH.md'
assert canonical.read_bytes()==mirror.read_bytes()
text=canonical.read_text(encoding='utf-8')
if not text.startswith(entry):
    b=(entry+text).encode();canonical.write_bytes(b);mirror.write_bytes(b)
(OUT/'HANDOFF.md').write_bytes((entry+'''恢复：先读Issue173/PR174。实验已完成，不重交2881。正式结果SUMMARY.json/RAW_INDEX.json含配置、模型、数据、校准及执行源码SHA，原始结果压缩包不必解压复制。重核验运行python work/jieruiz/173/summarize.py。发布阶段用同PR174，不合并。后续训练契约Issue159/PR170尚未自动采用本新路径；原57参数扫描不能直接沿用z重编码参数。当前输出恢复系数/宽累加为功能候选，没有硬件面积优越性证明。
''').encode())
print('Results archived, handoff and same-byte persistent memory updated')
