"""Bind literature recheck, preserve shared-note history and record the decision."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
WS = ROOT.parents[1]
PKG = ROOT / "architecture_tlm/bf16_baseline_20261028"
ARCH = WS / "project_archives/matrix204_bf16_literature_20261028"
note = """## 2026-10-28 Issue204：已找到完整28nm BF16数字阵列功耗证据

rayggxia，task/204-bf16-baseline / PR209接续，源起点d6aa128997072acd837508c7703844bf950603ec。用户要求确认是否没有28/55nm BF16数字矩阵依据、缺乏时再自建仿真。二轮已找到MFSA完整正文和FlexBlock作者PDF，纠正首轮检索不足；两原PDF及表II/V原图已下载、SHA绑定、渲染核对。当前入口architecture_tlm/bf16_baseline_20261028/README_ZH.md、LITERATURE_RECHECK_ZH.md及literature_recheck.py。

MFSA2026-10-14预印本：28nm SS0.72V/125℃/1GHz，16×16全格式数字阵列，BF16输入/FP32累加；后布线RC+LLM门级轨迹稳态估算1.85W/1.024TOPS，排除reset/预装/排空。两op/MAC由256PE×两项×1GHz核验，得3.61328pJ/MAC、231.25pJ/64MAC；对SC54核69.4633pJ为3.329倍，仅异工艺/异精度/异边界归一，非N64冷启动延迟或整片节能。原73pJ摘要换算保留低完整度版本，不作为唯一参考。

FlexBlock作者文件头为2203.06673v1：65nm BF16 SA128×128、333MHz、9.84W、1.77TFLOPS；P/T约711.59pJ/64MAC，但吞吐只占乘法器理论峰值16.22%，属含利用率/周期模型的负载归一，不能据此宣布10倍优势；SRAM另CACTI。外部65nm面积不套本项目0.81。55nm严格同PVT/数据/接口仍未找到已核验匹配项，不断言不存在。

有了可用28nm参考，用户“确认没有才自建”的条件未成立，本轮未启动新RTL/EDA/Slurm/GPU/PPL，中央台账84条不变。后续本工艺表征仍是独立工作，不冒称已测。实际追加提交/回读见work/rayggxia/204/bf16_baseline/LITERATURE_PUBLICATION.json；PR209待审不合并，Projects沿既有限制。

"""
preimages = []
for p in (ROOT / "PROJECT_MEMORY_ZH.md", WS / "PROJECT_MEMORY_ZH.md",
          WS / "tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md",
          ROOT / "progress/rayggxia/STATUS.md", HERE / "HANDOFF.md", ROOT / "work/rayggxia/204/HANDOFF.md"):
    raw = p.read_bytes()
    if note.splitlines()[0].encode() in raw:
        continue
    h = hashlib.sha256(raw).hexdigest()
    target = ARCH / ("preimage_" + h + ".bin")
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    p.write_bytes(note.encode() + raw)
    preimages.append({"path": str(p), "previous_sha256": h, "archive": str(target)})
log = ROOT / "architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md"
addition = """

## 2026-10-28 BF16二轮补充 已找到28nm阵列完整证据

Issue204/PR209；[文献复核](bf16_baseline_20261028/LITERATURE_RECHECK_ZH.md)纠正首轮检索不足，MFSA28nm BF16/FP32后布线稳态功耗可作外部参考；65nm FlexBlock的BF16 SA含利用率影响，不能当纯MAC动作能量。原摘要条件值保留版本边界，不再作为唯一依据。两PDF/表格原图SHA核对、数值归一与吞吐计数通过；无新EDA/模型或台账run，55nm同条件PPA仍待独立表征。
"""
if addition.splitlines()[2].encode() not in log.read_bytes():
    log.write_bytes(log.read_bytes() + addition.encode())
files = [PKG / x for x in ("README_ZH.md", "LITERATURE_RECHECK_ZH.md", "LITERATURE_RECHECK.json", "literature_recheck.py")]
files += [HERE / "cache_primary_papers.py", Path(__file__).resolve()]
data = {"date": "2026-10-28", "owner": "rayggxia", "issue": 204, "pr": 209,
        "starting_commit": "d6aa128997072acd837508c7703844bf950603ec", "new_simulations": 0,
        "primary_PDFs_SHA_verified": 2, "table_pages_visually_reviewed": ["MFSA PDF6/TableII", "FlexBlock PDF10/TableV"],
        "command": "python architecture_tlm/bf16_baseline_20261028/literature_recheck.py --workspace C:/Users/86134/Documents/a_P_BIT",
        "files": [{"path": str(p.relative_to(ROOT)).replace("\\", "/"), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size} for p in files],
        "memory_preimages": preimages, "model_corpus_fields": "N/A: literature reanalysis only; no model inference or new coding evaluation"}
(HERE / "LITERATURE_VALIDATION.json").write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode())
print(json.dumps({"files_bound": len(files), "shared_note_preimages": len(preimages), "new_simulations": 0}))
