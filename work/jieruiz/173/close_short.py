# -*- coding: utf-8 -*-
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parents[1]
note='''## Issue173短流三路AND结果核验完成（2026-10-24）

Slurm2891三片封存完成，48份/46唯一配置、documents/sidecar原字节SHA、36层全前缀、每片27项预检通过。执行c44c2edc不变；同轮BF16及原尺度mean/IID64三seed与旧结果逐值一致。Qwen3-4B后训练、准确Attention、8×128后缀，非完整WT2。前级W8/x固定四档共享64 T=K64；后级4×2×4联合32区间，各1/2/4次。整体减半固定四档[S/2,S/8,S/32,S/128]的mean/IID64/联合32/64/128 PPL为13.4034/27.4020/103.8940/21.8821/15.3647；BF16=13.5660，最佳128仍高13.26%，不能称无损。gate/up恢复仍FP32参考；无训练/PPA。

报告qwen3/results/and_direct_20261024/short/REPORT_ZH.md及SUMMARY/RAW_INDEX。原件project_archives/qwen3_and_direct_20261024/short-sealed-2891.tar.gz，服务器与本机SHA均e498dc55cfe0dea649f52c3c4635272f32af33d67114b1270328f69ca9587467。不重交、无新增定时。本人jieruiz，task/173-and-direct-wd，沿用Issue173/PR174待审未合并；发布以SHORT_PUBLICATION.json为准，Projects缺read:project待同步。FSM另属Issue175/PR176，不混用结果。

'''
canonical=BASE/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';mirror=BASE/'PROJECT_MEMORY_ZH.md'
assert canonical.read_bytes()==mirror.read_bytes()
data=canonical.read_text(encoding='utf-8')
if not data.startswith(note):data=note+data
for p in (canonical,mirror,ROOT/'PROJECT_MEMORY_ZH.md'):p.write_bytes(data.encode('utf-8'))
for p in (ROOT/'progress/jieruiz/STATUS.md',ROOT/'work/jieruiz/173/HANDOFF.md'):
    old=p.read_text(encoding='utf-8');p.write_bytes((note+old).encode('utf-8'))
