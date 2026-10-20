"""Standard-library-only reporting of actual E1 journals; never runs a model.

Usage: summarize.py --run-root PATH_CONTAINING_PILOT_AND_FULL --output NEW_DIR
Raw phase directories are read-only. A declared passing summary cannot replace
checking expected case identities, distinct seeds, failed records and outputs.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics


SCHEMA = "attention_e01_microbench_v1"
NUMERICAL = ("stable_fp32", "bf16_probability_cast_fp32_sum", "exp2_pwl_fp32", "online_tiled_fp32_pv")
SAMPLERS = ("digital_iid_inverse_cdf", "digital_systematic_single_phase", "serial_random_scan_ising")
DEFAULT_CONFIG = {"candidate_counts": [64, 512, 2048], "sample_counts": [32, 128, 512],
                  "seeds": [0, 1, 2], "real_row_indices": [0, 2, 4]}
METRICS = {
    "tv_half_l1": ("contracts", "full_probability", "tv"),
    "probability_max_abs_error": ("contracts", "full_probability", "max_abs_error"),
    "abs_row_sum_minus_one": ("contracts", "full_probability", "abs_row_sum_minus_one"),
    "nmse": ("contracts", "final_v", "nmse"),
    "relative_l2_error": ("contracts", "final_v", "relative_l2_error"),
    "unique_V_rows": ("contracts", "category_indices", "unique_V_rows"),
    "attempted_updates": ("sampler", "attempted_updates"),
    "state_flips": ("sampler", "state_flips"),
    "backend_CPU_software_seconds": ("backend_cpu_software_seconds",),
    "sampling_CPU_software_seconds": ("sampling_cpu_software_seconds",),
}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def metric_value(record, path):
    value = record
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value if type(value) in (int, float) and math.isfinite(value) else None


def sample_statistics(values):
    values = list(values)
    return {"n": len(values), "mean": statistics.mean(values) if values else None,
            "std_ddof1": statistics.stdev(values) if len(values) >= 2 else None,
            "minimum": min(values) if values else None, "maximum": max(values) if values else None}


def case_identity(record):
    return record.get("profile"), record.get("M"), record.get("S"), record.get("backend"), record.get("seed")


def group_identity(record):
    return case_identity(record)[:4]


def expected_cases(config, phase):
    config = {**DEFAULT_CONFIG, **config}
    profiles = ["uniform", "peaked"] + [f"real:{i}" for i in config["real_row_indices"]]
    if phase == "full":
        rows = [{"profile": p, "M": m, "backend": b}
                for p, m, b in itertools.product(profiles, config["candidate_counts"], NUMERICAL)]
        rows += [{"profile": p, "M": m, "S": s, "seed": seed, "backend": b}
                 for p, m, s, seed, b in itertools.product(profiles, config["candidate_counts"],
                     config["sample_counts"], config["seeds"], SAMPLERS)]
    elif phase == "pilot":
        counts = config["candidate_counts"]
        low, middle, high = min(counts), counts[len(counts) // 2], max(counts)
        seed, small_s, large_s = config["seeds"][0], min(config["sample_counts"]), max(config["sample_counts"])
        rows = [{"profile": "uniform", "M": low, "backend": b} for b in NUMERICAL]
        rows += [{"profile": "peaked", "M": middle, "S": small_s, "seed": seed, "backend": b} for b in SAMPLERS]
        rows += [{"profile": profiles[2], "M": high, "backend": b}
                 for b in ("stable_fp32", "exp2_pwl_fp32", "online_tiled_fp32_pv")]
        rows += [{"profile": profiles[2], "M": high, "S": large_s, "seed": seed, "backend": b}
                 for b in ("serial_random_scan_ising", "digital_systematic_single_phase")]
    else:
        raise ValueError("unknown phase")
    return {f"{phase}_{index:05d}": row for index, row in enumerate(rows)}


def _required_metrics(backend):
    names = ["nmse", "relative_l2_error"]
    if backend != "online_tiled_fp32_pv":
        names.append("tv_half_l1")
    if backend in SAMPLERS:
        names.append("unique_V_rows")
    if backend == "serial_random_scan_ising":
        names.extend(("attempted_updates", "state_flips"))
    return names


def aggregate_records(records, expected):
    """Exclude failed/duplicate/unexpected records; preserve every failure."""
    identity_counts = Counter(case_identity(record) for record in records)
    id_counts = Counter(record.get("case_id") for record in records)
    expected_groups = defaultdict(list)
    for wanted in expected.values():
        expected_groups[group_identity(wanted)].append(wanted)
    valid_by_group = defaultdict(list)
    failures = []
    seen_expected = set()
    for record in records:
        case_id = record.get("case_id")
        wanted = expected.get(case_id)
        reason = None
        if wanted is None or case_identity(record) != case_identity(wanted):
            reason = "unexpected_case_id_or_case_identity"
        else:
            seen_expected.add(case_id)
        if reason is None and (id_counts[case_id] != 1 or identity_counts[case_identity(record)] != 1):
            reason = "duplicate_case_or_seed_identity_all_duplicates_excluded"
        if reason is None and (record.get("status") != "ok" or record.get("correctness_invariants_passed") is not True):
            reason = "failed_status_or_correctness_invariant"
        if reason is None:
            absent = [name for name in _required_metrics(record["backend"]) if metric_value(record, METRICS[name]) is None]
            if absent:
                reason = "missing_or_nonfinite_required_metrics:" + ",".join(absent)
        if reason:
            failures.append({"case_id": case_id, "profile": record.get("profile"), "M": record.get("M"),
                             "S": record.get("S"), "backend": record.get("backend"), "seed": record.get("seed"),
                             "status": record.get("status"), "reason": reason, "error": record.get("error")})
        else:
            valid_by_group[group_identity(record)].append(record)
    groups = []
    for key, wanted in expected_groups.items():
        profile, m, s, backend = key
        valid = valid_by_group[key]
        expected_seeds = sorted(row["seed"] for row in wanted if "seed" in row)
        actual_seeds = sorted(row["seed"] for row in valid if "seed" in row)
        # A failed case still occupies an expected seed; it is not a valid
        # repetition. Repeated observations are never called distinct seeds.
        failed_count = sum(group_identity(row) == key for row in failures)
        groups.append({"profile": profile, "M": m, "S": s, "backend": backend,
                       "contract_kind": "category_indices_counts_and_sampled_V" if backend in SAMPLERS else "deterministic_numerical_operator",
                       "expected_records": len(wanted), "valid_records": len(valid), "failed_records": failed_count,
                       "expected_seeds": expected_seeds, "valid_seeds": actual_seeds,
                       "missing_valid_seeds": sorted(set(expected_seeds) - set(actual_seeds)),
                       "status": "complete" if len(valid) == len(wanted) else "failed" if failed_count else "partial",
                       "statistics": {name: sample_statistics(value for row in valid if (value := metric_value(row, path)) is not None)
                                      for name, path in METRICS.items()},
                       "valid_seed_nmse": {str(row["seed"]): metric_value(row, METRICS["nmse"]) for row in valid if "seed" in row}})
    valid_count = sum(group["valid_records"] for group in groups)
    return {"expected_cases": len(expected), "observed_records": len(records), "valid_records": valid_count,
            "failed_records": len(failures), "missing_case_ids": sorted(set(expected) - seen_expected),
            "failures": failures, "groups": groups,
            "status": "complete" if valid_count == len(expected) and not failures else "failed" if failures else "partial"}


def read_phase(run_root, phase):
    directory = Path(run_root) / phase
    if not directory.is_dir():
        return {"phase": phase, "status": "missing", "groups": [], "input_files": {}}
    paths = {name: directory / name for name in ("run_context.json", "cases.jsonl", "summary.json")}
    inputs = {name: {"path": str(path.resolve()), "sha256": digest(path), "bytes": path.stat().st_size}
              for name, path in paths.items() if path.is_file()}
    issues = []
    if not paths["run_context.json"].is_file():
        return {"phase": phase, "status": "partial", "groups": [], "input_files": inputs,
                "integrity_issues": ["missing_run_context_cannot_determine_expected_matrix"]}
    context = json.loads(paths["run_context.json"].read_text(encoding="utf-8"))
    if context.get("schema") != SCHEMA or context.get("phase") != phase:
        raise ValueError(f"unexpected schema/phase in {paths['run_context.json']}")
    records = []
    malformed = []
    if paths["cases.jsonl"].is_file():
        for line_number, line in enumerate(paths["cases.jsonl"].read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("record is not a JSON object")
                records.append(record)
            except (ValueError, TypeError) as error:
                malformed.append({"line": line_number, "error": str(error)})
    else:
        issues.append("missing_cases_jsonl")
    result = aggregate_records(records, expected_cases(context.get("config", {}), phase))
    raw_summary = None
    if paths["summary.json"].is_file():
        raw_summary = json.loads(paths["summary.json"].read_text(encoding="utf-8"))
        if raw_summary.get("context_sha256") != context.get("context_sha256"):
            issues.append("summary_context_fingerprint_mismatch")
        if raw_summary.get("journal_sha256") != inputs.get("cases.jsonl", {}).get("sha256"):
            issues.append("summary_journal_sha256_mismatch")
        for field, expected_value in (("planned_cases", result["expected_cases"]), ("recorded_cases", len(records)),
                                       ("completed_cases", sum(row.get("status") == "ok" for row in records))):
            if raw_summary.get(field) != expected_value:
                issues.append("summary_" + field + "_does_not_match_actual_journal_or_matrix")
        if raw_summary.get("gate_passed") and result["status"] != "complete":
            issues.append("declared_passing_summary_does_not_establish_actual_complete_matrix")
        if result["status"] == "complete" and raw_summary.get("gate_passed") is not True:
            issues.append("terminal_summary_did_not_pass_execution_gate")
    else:
        issues.append("missing_terminal_summary")
    if malformed:
        issues.append("malformed_jsonl_records_excluded_and_reported")
    if issues:
        result["status"] = "failed" if any(issue not in ("missing_cases_jsonl", "missing_terminal_summary") for issue in issues) else "partial" if result["status"] == "complete" else result["status"]
    sources = {}
    for row in records:
        metadata = row.get("input", {})
        if "source_row" in metadata:
            sources[str(metadata["source_row"])] = metadata.get("source_row_metadata")
    result.update({"phase": phase, "context": context, "raw_summary": raw_summary, "input_files": inputs,
                   "integrity_issues": issues, "malformed_lines": malformed, "source_rows_in_actual_records": sources})
    return result


def same_s_comparisons(groups):
    indexed = defaultdict(dict)
    for group in groups:
        if group["backend"] in SAMPLERS:
            indexed[(group["profile"], group["M"], group["S"])][group["backend"]] = group
    comparisons = []
    for (profile, m, s), backends in indexed.items():
        result = {"profile": profile, "M": m, "S": s, "complete_three_backend_seed_sets": False, "backends": {}}
        for name, group in backends.items():
            result["backends"][name] = {"status": group["status"], "valid_seeds": group["valid_seeds"],
                                        "nmse": group["statistics"]["nmse"], "relative_l2_error": group["statistics"]["relative_l2_error"]}
        complete = all(name in backends and backends[name]["status"] == "complete" for name in SAMPLERS)
        complete &= len({tuple(backends[name]["valid_seeds"]) for name in SAMPLERS if name in backends}) == 1
        complete &= all(len(backends[name]["valid_seeds"]) >= 3 for name in SAMPLERS if name in backends)
        result["complete_three_backend_seed_sets"] = complete
        result["paired_nmse_ising_minus_iid"] = None
        result["paired_nmse_ising_minus_systematic"] = None
        if complete:
            serial = backends["serial_random_scan_ising"]["valid_seed_nmse"]
            for digital, label in (("digital_iid_inverse_cdf", "iid"), ("digital_systematic_single_phase", "systematic")):
                target = backends[digital]["valid_seed_nmse"]
                result["paired_nmse_ising_minus_" + label] = sample_statistics(serial[seed] - target[seed] for seed in serial)
        comparisons.append(result)
    return comparisons


def collect_report(run_root):
    phases = {phase: read_phase(run_root, phase) for phase in ("pilot", "full")}
    full = phases["full"]
    pilot = phases["pilot"]
    if full["status"] == "complete" and pilot["status"] == "complete":
        overall = "complete"
    elif any(phase["status"] == "failed" for phase in phases.values()):
        overall = "failed"
    else:
        overall = "partial"
    issues = []
    if "context" in full and "context" in pilot and full["context"].get("context_sha256") != pilot["context"].get("context_sha256"):
        overall = "failed"
        issues.append("pilot_and_full_context_fingerprints_differ")
    return {"report_schema": "attention_e01_summary_v1", "run_root": str(Path(run_root).resolve()), "status": overall,
            "default_plan_full_cases": 465, "default_plan_pilot_cases": 12,
            "phases": phases, "integrity_issues": issues, "same_S_comparisons": same_s_comparisons(full.get("groups", [])),
            "statistics_scope": "valid_distinct_seed_records_only_sample_std_ddof1_no_confidence_interval_claim",
            "timing_scope": "CPU_software_elapsed_time_NOT_hardware_latency_or_energy",
            "limitations": ["renormalized_first_M_subcandidate_distributions_only",
                            "synthetic_uniform_and_peaked_logits_are_not_real_Qwen_distributions",
                            "selected_real_rows_are_not_representative_of_the_whole_model",
                            "serial_Ising_finite_samples_do_not_prove_stationarity_or_physical_device_performance",
                            "sample_histogram_TV_is_not_exact_probability_output_accuracy",
                            "no_sparse_QK_screen_quality_or_hardware_PPA_or_full_sampled_PPL_evaluated",
                            "raw_NPZ_artifact_hashes_are_recorded_by_execution_not_reverified_by_this_summary"]}


def write_csv(path, groups):
    fixed = ["profile", "M", "S", "backend", "status", "expected_records", "valid_records", "failed_records", "expected_seeds", "valid_seeds", "missing_valid_seeds"]
    fields = fixed + [name + "_" + statistic for name in METRICS for statistic in ("n", "mean", "std_ddof1")]
    with Path(path).open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for group in groups:
            row = {name: group[name] for name in fixed}
            for name in ("expected_seeds", "valid_seeds", "missing_valid_seeds"):
                row[name] = json.dumps(row[name], separators=(",", ":"))
            for name in METRICS:
                row.update({name + "_" + stat: group["statistics"][name][stat] for stat in ("n", "mean", "std_ddof1")})
            writer.writerow(row)


def number(value):
    return "—" if value is None else f"{value:.5g}"


def _mean_std(stats):
    if not stats or stats["mean"] is None:
        return "—"
    return number(stats["mean"]) + (" ± " + number(stats["std_ddof1"]) if stats["std_ddof1"] is not None else "（仅 1 条有效记录）")


def render_chinese(report):
    phases = report["phases"]
    full = phases["full"]
    status_zh = {"complete": "完整", "partial": "部分完成", "failed": "含失败或一致性错误", "missing": "尚无产物"}
    lines = ["# Attention E1 实际数值微基准汇总", "", f"状态：**{status_zh[report['status']]}**。本报告只汇总实际 JSONL 记录，不补写缺失实验。", "",
             "| 阶段 | 状态 | 计划数 | 观察行数 | 有效行数 | 失败行数 | 缺少 case |", "|---|---|---:|---:|---:|---:|---:|"]
    for name in ("pilot", "full"):
        phase = phases[name]
        lines.append(f"| {name} | {status_zh[phase['status']]} | {phase.get('expected_cases', '—')} | {phase.get('observed_records', 0)} | {phase.get('valid_records', 0)} | {phase.get('failed_records', 0)} | {len(phase.get('missing_case_ids', [])) if 'expected_cases' in phase else '—'} |")
    lines += ["", "默认执行矩阵为 12 条 pilot、465 条 full；实际验收按本次配置逐条核对身份和种子，不沿用此前 623 条规划表。",
              "pilot 仅作有限执行与数值正确性门槛；full 缺失、缺种子、超时和失败均不能称为完整实验。失败行与重复种子不进入均值。", "",
              "## 同 M、同 S 的最终 V 误差", "",
              "以下 NMSE 为三个独立种子有效记录的均值 ± 样本标准差（ddof=1），不是置信区间。只有三个后端均完整且种子一致时，才给出配对差值。Ising−数字的差值为正表示本轮 Ising 的 V 误差更大；这不是硬件能效结论。", "",
              "| 分布 | M | S | 数字 IID NMSE | 数字 systematic NMSE | 串行 Ising NMSE | 三后端种子完整 | Ising−IID 配对差值 |", "|---|---:|---:|---|---|---|---|---|"]
    for comparison in report["same_S_comparisons"]:
        values = [_mean_std(comparison["backends"].get(name, {}).get("nmse")) for name in SAMPLERS]
        lines.append(f"| {comparison['profile']} | {comparison['M']} | {comparison['S']} | {' | '.join(values)} | {'是' if comparison['complete_three_backend_seed_sets'] else '否'} | {_mean_std(comparison['paired_nmse_ising_minus_iid'])} |")
    if not report["same_S_comparisons"]:
        lines.append("| 尚无 full 采样记录 | — | — | — | — | — | 否 | — |")
    lines += ["", "## 数字数值路径", "",
              "| 数值方法 | 完整组 / 计划组 | 最大 half-L1 概率误差 | 最大最终 V 相对 L2 误差 |", "|---|---:|---:|---:|"]
    for backend in NUMERICAL:
        groups = [group for group in full.get("groups", []) if group["backend"] == backend]
        tv = [group["statistics"]["tv_half_l1"]["maximum"] for group in groups if group["statistics"]["tv_half_l1"]["n"]]
        error = [group["statistics"]["relative_l2_error"]["maximum"] for group in groups if group["statistics"]["relative_l2_error"]["n"]]
        lines.append(f"| {backend} | {sum(group['status'] == 'complete' for group in groups)} / {len(groups)} | {number(max(tv)) if tv else '—'} | {number(max(error)) if error else '—'} |")
    context = full.get("context", phases["pilot"].get("context", {}))
    lines += ["", "完整统计见 aggregate.csv 与 REPORT.json，包含 TV/half-L1、概率行和、NMSE、相对 L2、unique V、attempted updates、flips 和 CPU 软件耗时。确定性数值路径没有 S 和种子重复，CSV 的 S 留空，单条记录的标准差留空。", "",
              "## 边界与未验证项", "",
              f"- 执行代码提交：`{context.get('git_commit', '未记录')}`；上下文指纹：`{context.get('context_sha256', '未记录')}`。",
              f"- 实际记录中的源行索引：`{', '.join(full.get('source_rows_in_actual_records', {})) or '尚无记录'}`。固定选取的少数层/头不代表全模型。",
              "- 每个 M 都对前 M 个 logits 与相同顺序的 V 前缀重新归一化；uniform/peaked logits 是合成对照，V 可来自实测捕获。",
              "- 完整概率向量、类别索引/计数、最终 V 是不同契约。采样直方图 TV 衡量有限样本误差；均匀分布的 M>S 情况存在至少 1−S/M 的支撑集误差下界。",
              "- BF16 概率输出不重新归一化；其 TV 字段按 half-L1 计算并单列行和。exp2 PWL 是带 log2(e) 转换的 FP32 软件数值模型，未综合成定点数字硬件。",
              "- 串行 Ising 使用离散 random-scan heat-bath；事件压缩仅省软件空更新，硬件仍需全部 attempted updates。短采样不证明稳态、ESS 或物理 p-bit 独立性。",
              "- 所有时间均为 CPU 软件数值仿真耗时，不能作为数字 ASIC 或 p-bit 的延迟、吞吐、功率、能量、面积对比。",
              "- 本报告未验证稀疏 QK 筛选、物理随机源、硬件 PPA 或随机 Attention 的完整 PPL；原 BF16 重跑由上级实验报告单独记录。",
              "- 本汇总不加载原始 NPZ，也不重新验证执行时记录的 NPZ 散列；输入 JSON 的实际 SHA-256 已写入 REPORT.json。", ""]
    issues = list(report["integrity_issues"])
    for name, phase in phases.items():
        issues.extend(name + ": " + issue for issue in phase.get("integrity_issues", []))
    failures = sum(phase.get("failed_records", 0) for phase in phases.values())
    if issues or failures:
        lines += ["## 失败与待核对", "", f"实际失败/无效行共 {failures} 条，具体 case、种子、状态与原因保留在 REPORT.json。"]
        lines += ["- " + issue for issue in issues]
        lines.append("")
    return "\n".join(lines)


def write_report(run_root, output):
    root = Path(run_root).resolve()
    destination = Path(output).resolve()
    for phase in ("pilot", "full"):
        raw_phase = root / phase
        if destination == raw_phase or raw_phase in destination.parents:
            raise ValueError("report output must be outside raw phase directories")
    if destination.exists():
        raise ValueError("report output must be a new directory; refusing overwrite")
    report = collect_report(root)
    destination.mkdir(parents=True)
    csv_path = destination / "aggregate.csv"
    write_csv(csv_path, report["phases"]["full"].get("groups", []))
    markdown_path = destination / "RESULTS_ZH.md"
    markdown_path.write_text(render_chinese(report), encoding="utf-8", newline="\n")
    report["report_artifacts"] = {path.name: {"sha256": digest(path), "bytes": path.stat().st_size} for path in (csv_path, markdown_path)}
    (destination / "REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = write_report(args.run_root, args.output)
    print(json.dumps({"status": report["status"], "output": str(Path(args.output).resolve())}, ensure_ascii=False))
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
