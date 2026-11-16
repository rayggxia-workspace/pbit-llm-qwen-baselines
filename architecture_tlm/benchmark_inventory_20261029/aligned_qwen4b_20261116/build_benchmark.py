"""Build the project-aligned Qwen3-4B table from sealed evidence and optional full runs."""

import argparse
from contextlib import redirect_stdout
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
SUMMARY = Path("architecture_tlm/process_28nm/results_20261111/SUMMARY.json")
NAMES = (
    ("SC_ising", "本项目 P-bit"),
    ("W8_screen", "本项目 W8 + Key Selection"),
    ("W8_dense", "本项目 W8 Dense"),
    ("BF16_dense", "本项目 BF16 Dense"),
)
CANDIDATES = {
    "BitMoD": "作者矩阵阵列模型已跑；整机接合待做",
    "EdgeCIM": "已核对原文 Qwen3-4B，待取得模拟器及 28 nm CIM 计价",
    "Harmonia": "待取得实现、可校验排程及 28 nm 资源证据",
    "Zhou et al. (BMQ)": "待取得实现或分模块计价、可执行排程",
    "NVLLM": "需保留 NAND 内计算及其接口；外存等价边界待确认",
    "Sirius": "待取得双芯粒实现、互连和调度配置",
    "RS-LPU": "需保留 draft/target 和 ReRAM；共同外存边界待确认",
}


def read_json(path, expected_sha=None):
    data = path.read_bytes()
    if expected_sha and hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError(f"Evidence checksum mismatch: {path}")
    return json.loads(data)


def complete_external(path, target):
    """Read a full-run record. Compare execution extent and PPA / DRAM evidence."""
    record = read_json(path)
    name = record.get("candidate")
    if name not in CANDIDATES:
        raise ValueError(f"Unknown candidate: {name}")
    if record.get("scope") != "complete_decode" or record.get("run_status") != "completed":
        raise ValueError(f"{name}: completed full-decode evidence required")
    fields = ("model_id", "model_revision", "model_config_sha256", "batch",
              "cache_tokens", "output_tokens", "decoder_layers", "head_vocabulary",
              "technology", "frequency_MHz", "dram_backend", "dram_profile_sha256",
              "dram_bridge_sha256", "dram_transfer_energy_pJ_per_bit")
    for key in fields:
        if record["conditions"].get(key) != target[key]:
            raise ValueError(f"{name}: comparison condition differs: {key}")
    if not set(target["required_stages"]).issubset(record["executed_stages"]):
        raise ValueError(f"{name}: full-decode stage evidence incomplete")
    if record.get("clock_validated") is not True:
        raise ValueError(f"{name}: 250 MHz mapping not validated")
    for label in ("runtime", "dram", "ppa"):
        evidence = record["evidence"][label]
        file = path.parent / evidence["path"]
        if hashlib.sha256(file.read_bytes()).hexdigest() != evidence["sha256"]:
            raise ValueError(f"{name}: {label} evidence checksum mismatch")
    v = record["metrics"]
    for key in ("time_ms", "core_mJ", "area_mm2"):
        if not math.isfinite(v[key]) or v[key] <= 0:
            raise ValueError(f"{name}: bad measured/estimated metric {key}")
    for key in ("dram_read_bytes", "dram_write_bytes"):
        if type(v[key]) is not int or v[key] < 0:
            raise ValueError(f"{name}: invalid byte count {key}")
    if not v["dram_read_bytes"]:
        raise ValueError(f"{name}: no external reads for a streamed Qwen3-4B run")
    off_chip = (v["dram_read_bytes"] + v["dram_write_bytes"]) * 8 * target["dram_transfer_energy_pJ_per_bit"] * 1e-9
    return name, [v["time_ms"], v["core_mJ"], v["core_mJ"] + off_chip, v["area_mm2"]]


def print_table(workspace, files):
    target = read_json(HERE / "TARGET.json")
    project = read_json(workspace / SUMMARY, target["project_summary_sha256"])
    if project["status"] != "FULL_BATCH15_OF15_SEAL_AND_SLURM_VERIFIED":
        raise ValueError("Unexpected project evidence status")
    rows = {r["scheme"]: r for r in project["rows"] if r["model"] == "qwen3_4b"}
    confirmed = {}
    for path in files:
        name, metrics = complete_external(path, target)
        if name in confirmed:
            raise ValueError(f"Provide one aligned configuration per candidate: {name}")
        confirmed[name] = metrics

    def line(name, metrics, status):
        values = " | ".join(f"{x:.2f}" if isinstance(x, (int, float)) else x for x in metrics)
        print(f"| {name} | {status} | {values} |")

    print("# Qwen3-4B 对齐 benchmark")
    print()
    print("B1，2K 已缓存，单步完整 decode，含全词表 head，28 nm／250 MHz／共同 LPDDR。"
          "项目数据来自封存 TLM。")
    print()
    print("| 方案 | 证据状态 | ms/token | 片上 mJ/token | 含外存 mJ/token | 片上 mm² |")
    print("|---|---|---:|---:|---:|---:|")
    for key, name in NAMES:
        r = rows[key]
        line(name, [r[m] for m in ("time_ms", "core_mJ", "total_4pJ_mJ", "area_mm2")], "项目 LPDDR TLM")
    for name, status in CANDIDATES.items():
        line(name, confirmed.get(name, ["—"] * 4), "同条件整机" if name in confirmed else status)
    print()
    print("外部工作按原生数制入场。质量需在同一真实模型与评测条件下另验，"
          "形状级事务或矩阵点均不表示数值质量。")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--workspace", default=Path.cwd(), type=Path)
    cli.add_argument("--external-result", type=Path, action="append", default=[])
    cli.add_argument("--out", type=Path)
    opts = cli.parse_args()
    if opts.out:
        with opts.out.open("w", encoding="utf-8", newline="\n") as stream, redirect_stdout(stream):
            print_table(opts.workspace, opts.external_result)
    else:
        print_table(opts.workspace, opts.external_result)
