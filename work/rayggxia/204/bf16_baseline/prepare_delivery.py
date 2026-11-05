"""Bind the read-only BF16 study and preserve prior shared-note bytes."""
from pathlib import Path
import hashlib
import json
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
WS = ROOT.parents[1]
PKG = ROOT / "architecture_tlm/bf16_baseline_20261028"
ARCH = WS / "project_archives/matrix204_bf16_research_20261028"
ARCH.mkdir(parents=True, exist_ok=True)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


sources = [
    {"id": "hpc28", "url": "https://hub.hku.hk/handle/10722/339469", "doi": "10.1109/TCSII.2023.3322259",
     "type": "author_institution_primary_abstract", "verified": "28nm; slow corner 1.471GHz; BF16 1761.41GFLOPS/W and 9-way",
     "not_verified": "full text; voltage; area; precise FLOP count; accumulator/rounding contract; N64 latency and memory boundary"},
    {"id": "tpu", "url": "https://docs.cloud.google.com/tpu/docs/bfloat16", "type": "official_documentation",
     "verified": "BF16 matrix multiplication with FP32 accumulation; conversion behavior"},
    {"id": "arm", "url": "https://developer.arm.com/community/arm-community-blogs/b/ai-blog/posts/bfloat16-processing-for-neural-networks-on-armv8_2d00_a",
     "type": "official_architecture_article", "verified": "BF16 product/dot accumulating into FP32; instruction contracts differ"},
    {"id": "normalization", "url": "https://arxiv.org/html/2408.11997v1", "type": "author_paper",
     "verified": "28nm BF16 PE architecture; 16-bit partial-sum significand; normalization sharing/approximation; not FP32 accumulate PPA"},
    {"id": "fpnew", "url": "https://arxiv.org/html/2007.01530v1", "type": "author_paper",
     "verified": "FP16alt is BF16; 22FDX Ariane silicon does not include expanding FMA, so its BF16 same-format energy is not the requested BF16/FP32 baseline"},
    {"id": "cvfpu", "url": "https://github.com/openhwfoundation/cvfpu", "type": "official_source_repository",
     "verified": "parametric SystemVerilog FPU source candidate only; no vendoring/version freezing or local PPA performed"},
    {"id": "vortex", "url": "https://arxiv.org/html/2512.00053v1", "type": "author_paper",
     "verified": "fused low-precision dot with FP32 sum; shared alignment and normalization; FPGA evaluation is not ASIC energy"},
]
save(PKG / "SOURCES.json", {"checked_at_UTC": "2026-10-28T10:58:59Z", "sources": sources})
note = """## 2026-10-28 Issue204：BF16数字基线调研与可复算预算

rayggxia，同task/204-matrix-t32 / PR205，复用tmp/matrix-t32-issue204-20261028；本轮读取既有证据及一手论文，无新RTL/EDA/Slurm/GPU/PPL，中央台账84条不变。结果architecture_tlm/bf16_baseline_20261028/REPORT_ZH.md及ESTIMATE.json；estimate.py核验旧SS/TT两份summary SHA、三seed单位和负时序，绑定旧RTL，重算预算。

主比较合同BF16×BF16、FP32累加。28nm Li等TCAS-II论文作者机构摘要可核实1761.41GFLOPS/W；条件按2 FLOPs/MAC为1.13545pJ/MAC、64项72.6691pJ，非55nm已测事务，全文累加/舍入/FLOP计数/面积/N64延迟未核验，不按工艺或0.81换能量。与本SC54计算核69.4633pJ接近，不能据此宣称巨大节能。SC需数字>1.08536/5.42682/10.85365pJ/MAC才分别持平/5倍/10倍，均未计两侧缺失前后端成本。

旧本工艺BF16标量KIND2在SS100MHz setup−26.219376ns、TT−10.537953ns；原731输入/5变长帧不是N64。其通用转换和26次依赖规格化循环值得优化，但未做新网表关键路径归因，不能用旧失败实现代表成熟基线。建议补专用乘法、树LZC FP32加法、融合MAC、共享处理DOT2/4/8与真实N64反馈/归约封装，验证35拍/350ns附近预算；两个算术lane不自动保证32拍。旧原件保留，不接管Issue107；BF16与SC W8/T32/OR4精度不同，匹配量化数字控制仍需保留。

研究稿/脚本本地完成；实际推送状态查work/rayggxia/204/bf16_baseline/PUBLICATION.json和PR205，不宣称新BF16 PPA已完成。Projects沿既有限制待有权限维护者同步。

"""
paths = [ROOT / "progress/rayggxia/STATUS.md", ROOT / "work/rayggxia/204/HANDOFF.md",
         ROOT / "PROJECT_MEMORY_ZH.md", WS / "PROJECT_MEMORY_ZH.md",
         WS / "tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md"]
preimages = []
for i, path in enumerate(paths):
    raw = path.read_bytes()
    if note.splitlines()[0].encode() in raw:
        continue
    target = ARCH / (sha(raw) + ".bin")
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    preimages.append({"path": str(path), "previous_sha256": sha(raw), "archive": str(target)})
    path.write_bytes(note.encode("utf-8") + raw)
save(HERE / "MEMORY_PREIMAGES.json", {"preimages": preimages,
     "policy": "Identical new note prepended; historical differing bytes preserved independently; no wholesale stale-copy overwrite"})
log = ROOT / "architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md"
addition = """

## 2026-10-28 BF16数字对照的能耗预算（Issue204）

[研究报告](bf16_baseline_20261028/REPORT_ZH.md)与[可复算脚本](bf16_baseline_20261028/estimate.py)：BF16乘法/FP32累加为主合同；28nm成熟PE摘要能效的条件N64换算72.67pJ已接近SC54计算核69.46pJ，不能预设数量级节能。旧本工艺BF16 SS/TT均时序违例，不作为有效100MHz基线。补测候选是专用融合MAC/小型DOT共享处理与真实反馈调度；保留同量化INT8控制。仅研究/预算，无新电路仿真、模型质量或整机结果；面积raw×0.81仅用于本项目已有面积，不缩放外部论文工艺或能量。
"""
raw = log.read_bytes()
if addition.splitlines()[2].encode() not in raw:
    log.write_bytes(raw + addition.encode("utf-8"))
handoff = """# BF16基线研究交接

2026-10-28，rayggxia，Issue204 / PR205；分支task/204-matrix-t32，目标main，起点5bfb221544daca8c345773a4741c30d2712f75ba。工作目录C:/Users/86134/Documents/a_P_BIT/tmp/matrix-t32-issue204-20261028。

用户授权调研BF16或搭模块估计。本轮已核查GitHub身份/最新PR205/Issue204、原负责人Issue107、main README/AGENTS；没有重复旧作业或接管Issue107。完成一手文献、旧BF16 RTL结构/两角summary核验、SC能耗预算与后续模块合同；正式成果architecture_tlm/bf16_baseline_20261028。

实际验证：estimate.py --workspace C:/Users/86134/Documents/a_P_BIT，核验两份原summary SHA，3seed能量/有效输入单位及旧负时序；SC54/50读取旧封存JSON，公式重现。没有新增BF16 RTL、功能/综合/STA/PT或模型推理，因此不新增电路run，不继承质量；原台账84个record保持。SS/TT旧时序失败和论文摘要合同未知均明确保留。

主要结果：主合同BF16×BF16→FP32累加；28nm论文1761.41GFLOPS/W条件2 FLOPs/MAC约72.67pJ/N64，对SC54算术69.46pJ，不能据此宣布巨大能耗优势。全文FLOP/精度/供数/面积/延迟未核验，能量不按节点缩放。5倍能耗比要求数字>5.43pJ/MAC；10倍>10.85；SC前后端还在外。旧BF16 SS setup−26.219ns/TT−10.538ns，不拿其大面积/能量充当成熟数字基线。

本轮无新增服务器作业。后续可在用户授权范围内补专用BF16乘法、FP32树LZC加法、融合MAC、DOT2/4/8及N64帧封装；先冻结源码/浮点合同和oracle，再跑三seed功能、合法STA与PT，加入新run。100MHz反馈流水需真实上下文/多周期协议。模型精度验收与量化数字控制另计。

MEMORY_PREIMAGES.json归档修改前记忆原字节；共享记忆只加同一段，不用旧副本覆盖新历史。PUBLICATION.json为真实上传回执入口；PR待审不合并/关Issue，Projects既有限制。
"""
(HERE / "HANDOFF.md").write_text(handoff, encoding="utf-8", newline="\n")
files = [PKG / n for n in ("REPORT_ZH.md", "estimate.py", "ESTIMATE.json", "SOURCES.json")]
save(HERE / "VALIDATION.json", {"date": "2026-10-28", "new_simulations": 0,
    "registry_records": len(list((WS / "digital_circuit_simulation_registry/records").glob("*.json"))),
    "files": [{"path": str(p.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(p.read_bytes()), "bytes": p.stat().st_size} for p in files],
    "runtime": "bundled Python3.12.14", "command": "python architecture_tlm/bf16_baseline_20261028/estimate.py --workspace C:/Users/86134/Documents/a_P_BIT",
    "source_commit": "5bfb221544daca8c345773a4741c30d2712f75ba", "model_corpus_fields": "N/A: no model inference or new coding evaluation"})
print(json.dumps({"files_bound": len(files), "notes_preserved": len(preimages), "new_simulations": 0}))
