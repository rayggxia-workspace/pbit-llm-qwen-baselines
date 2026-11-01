"""Refresh Issue225's conditional budget from measured module handoffs.

This is deliberately NOT a whole-chip memory replay. In particular a measured
eight-group Attention batch is a reference envelope, never a constant-latency
DRAM actor. Original Issue225 files and all source modules remain immutable.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math


def read(p):
    return json.loads(Path(p).read_bytes())


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_json(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2,
                                allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def collect(root, out):
    old = root / "tmp/module-estimate-issue225-20261031/architecture_tlm/module_estimate_20261031"
    att = root / "tmp/attention-compare-issue198-20261027/architecture_tlm/attention_compare_20261027"
    hand = root / "architecture_tlm/module_handoff"
    paths = {
        "previous_inputs": old / "INPUTS.json",
        "previous_results": old / "results/RESULTS.json",
        "GU_profile": hand / "ffn_gu_k64_m128_t64_20261101/profile.json",
        "NL_profile": hand / "ffn_nonlinear_wd_t64_20261031/profile.json",
        "Attention_profile": hand / "attention_k128_s64_20261031/profile.json",
        "Attention_memory": hand / "attention_k128_s64_20261031/memory_contract.json",
        "Attention_Vpath": hand / "attention_k128_s64_20261031/VPATH_COST_20261101.json",
        "Attention_comparison": att / "systematic_s64_20261101/COMPARISON.json",
    }
    original = read(paths["previous_inputs"])
    gu = read(paths["GU_profile"])
    nl = read(paths["NL_profile"])
    ap = read(paths["Attention_profile"])
    mem = read(paths["Attention_memory"])
    vp = read(paths["Attention_Vpath"])
    compare = read(paths["Attention_comparison"])
    base_summaries = []
    for case in (1, 2, 3):
        p = root / ("tmp/tlm-breakdown-issue210-20261029/architecture_tlm/"
                    f"scheduling_v2_20261027/results_early_dma/case_{case}/RESULT_SUMMARY.json")
        paths[f"old_execution_case{case}"] = p
        base_summaries.append(read(p))
    original["baseline"]["gu_busy_ns"] = sum(
        b["stage_busy_ns"]["SC_locality_gu"] for b in base_summaries) / 3
    rows = compare["rows"]
    sampler_anchors = compare["sampler_anchors"]
    result = {
        "schema": "issue225-measured-module-budget-20261101-v1",
        "scope": "conditional modular budget refresh; NOT integrated TLM/DRAMSys replay",
        "model": original["model"], "batch": 1, "context": 2048,
        "baseline": original["baseline"],
        "old_NL_source_budget": original["ffn"],
        "old_attention_parameters": original["attention"],
        "GU": {
            "K": 64, "paired_columns": 64, "outputs": 128,
            "T": 64, "clock_hz": gu["timing"]["reference_clock_hz"],
            "service_cycles": gu["timing"]["initiation_interval_cycles"],
            "frame_pJ": gu["cost"]["energy_pJ_per_work_unit"],
            "area55_mm2": gu["cost"]["reported_area55eq_mm2"],
            "idle_W": gu["cost"]["idle_background_power_W_and_charging_policy"]["source_stopped_clock_running_W"],
            "stall_W": gu["cost"]["idle_background_power_W_and_charging_policy"]["nonzero_partial_source_stopped_stall_W"],
            "gated_standby_W": None,
            "resident_weight_bytes": gu["storage_and_random"]["port_accesses_bytes_frequency_stride_reuse"]["logical_W_bytes"],
            "input_rng_unique_words": None,
            "variant": gu["reference_variant"],
            "publication_commit": gu["identity"]["publication_commit"],
        },
        "NL": {
            "K": 64, "columns": 8, "T": 64, "clock_hz": 100000000,
            "service_cycles": 66, "frame_pJ": nl["cost"]["energy_pJ_per_work_unit"],
            "area55_mm2": nl["cost"].get("reported_area55eq_mm2", original["ffn"]["area55_mm2"]),
            "idle_leakage_proxy_W": original["ffn"]["leakage_proxy_W"],
            "idle_toggling_diagnostic_W": original["ffn"]["idle_diagnostic_W"],
            "resident_weight_bytes": 512,
            "variant": "g8_weighted_full",
            "publication_commit": nl["identity"].get("publication_commit"),
        },
        "attention": {
            "profile_version": ap["delivery"]["version"],
            "memory_contract": mem,
            "rows": rows,
            "sampler_anchors": sampler_anchors,
            "Vpath": vp,
            "wholechip_integrated": False,
            "continuous_KV_append_integrated": False,
        },
        "source_identities": [{"id": key, "workspace_relative_path": str(p.relative_to(root)).replace("\\", "/"),
                               "bytes": p.stat().st_size, "sha256": digest(p)}
                              for key, p in paths.items()],
        "validation_receipts": {
            "GU": {"status": "PASS", "source_files": 13, "archive_members": 8},
            "NL": {"status": "PASS", "source_files": 9, "archive_members": 6},
            "Attention": {"status": "PASS", "source_hashes": 36, "heads": 24,
                          "samples": 1536, "negative_cases": 4},
            "first_attempts": [
                "NL mirror lacks CONFIG.json; rerun using original Issue204 checkout PASS",
                "Attention accepts --source-root, not --repo-root; corrected invocation PASS"],
            "new_EDA_or_model_runs": 0,
        },
    }
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "INPUTS.json", result)
    return result


def evaluate(i, gu_instances=16, nl_instances=256, attention_groups=8):
    b, g, n = i["baseline"], i["GU"], i["NL"]
    layers = i["model"]["num_hidden_layers"]
    d, f = i["model"]["hidden_size"], i["model"]["intermediate_size"]
    gu_frames = layers * (d // 64) * (f // 64)
    nl_frames = layers * (f // 64) * (d // 8)
    # Preserve input-group/replay boundaries and account for the last wave.
    gu_waves = layers * (d // 64) * math.ceil((f // 64) / gu_instances)
    nl_waves = layers * (f // 64) * math.ceil((d // 8) / nl_instances)
    gu_ms = gu_waves * g["service_cycles"] / g["clock_hz"] * 1000
    nl_ms = nl_waves * n["service_cycles"] / n["clock_hz"] * 1000
    gu_active = gu_frames * g["frame_pJ"] * 1e-9
    nl_active = nl_frames * n["frame_pJ"] * 1e-9
    phase = b["phase_ns"]
    old_ms = b["fma"]["TPOT_ms"]
    row = next(r for r in i["attention"]["rows"]
               if r["mode"] == "GF64" and r["parallel"] == attention_groups)
    reference_attention_ms = layers * row["time_us"] / 1000
    # These are explicitly an overlap envelope. NOT a new DRAM latency model.
    floor_gu = max(0, gu_ms - phase["FFN_gate_up"] / 1e6)
    floor_nl = max(0, nl_ms - phase["FFN_AND_direct_down"] / 1e6)
    exposed_gu = max(0, gu_ms - b["gu_busy_ns"] / 1e6)
    exposed_nl = max(0, nl_ms - b["down_busy_ns"] / 1e6)
    common = old_ms - phase["attention_core"] / 1e6 + reference_attention_ms
    times = [common + floor_gu + floor_nl, common + exposed_gu + exposed_nl]
    assert times[1] >= times[0] > 0
    oldmods = b["modules"]
    corners = []
    old_area = b["fma"]["covered_area_55eq_mm2"]
    vp = i["attention"]["Vpath"]
    area_removed = {k: oldmods[k]["equivalent_55nm_area_mm2"] for k in
                    ("FFN_counter", "PV_vector_adders", "Attention_existing_PRNG_endpoints", "FFN_and_selector_sigmoid_tables")}
    # QK binds existing ordinary FMA lanes; no duplicated standalone FMA array.
    area_added = {"GU": gu_instances*g["area55_mm2"], "NL_Wd": nl_instances*n["area55_mm2"],
                  "Vpath": attention_groups*vp["group"]["area55_mm2"],
                  "samplers": attention_groups*0.05293444,
                  "SparQ_logic": attention_groups*0.086234868}
    area = old_area - sum(area_removed.values()) + sum(area_added.values())
    for t in times:
        for label, nl_idle in [("NL_leakage_proxy", n["idle_leakage_proxy_W"]),
                               ("NL_external_R_toggling_diagnostic", n["idle_toggling_diagnostic_W"])]:
            costs = {}
            for key, v in oldmods.items():
                bg = ((v.get("leakage_J") or 0) + (v.get("idle_clock_background_J") or 0))*1000
                costs[key] = v["energy_mJ_per_token"] - bg + bg*t/old_ms
            # BOTH original uses of the old shared counter pool have now been
            # replaced. Remove its entire cost including idle/background once.
            costs.pop("FFN_counter")
            costs.pop("PV_vector_adders")
            costs.pop("Attention_existing_PRNG_endpoints")
            costs.pop("FFN_and_selector_sigmoid_tables")
            # Cross-K alignment/quantization/restoration remains a separate
            # reserve. Do not discard it because the local exponent is cheap.
            costs["crossK_quantization_restore_legacy_reserve"] = costs.pop("FFN_postscale_restore_proxy")
            # Preserve source budget, explicitly NOT a measured new GU source.
            costs["input_PRNG_old_combined_budget_reserve"] = costs.pop("FFN_shared64_input_frontend")
            costs["NL_PRNG_old_combined_budget_reserve"] = costs.pop("FFN_nonlinear_10_local_PRNG_endpoints")
            costs["GU_active_measured"] = gu_active
            inactive_gu = max(0, gu_instances*t/1000 - gu_frames*g["service_cycles"]/g["clock_hz"])
            costs["GU_inactive_measured_source_stopped_clock_running"] = inactive_gu*g["idle_W"]*1000
            costs["NL_active_measured"] = nl_active
            inactive_nl = max(0, nl_instances*t/1000 - nl_frames*n["service_cycles"]/n["clock_hz"])
            costs["NL_inactive_proxy_or_diagnostic"] = inactive_nl*nl_idle*1000
            costs["Vpath_dynamic"] = layers*8*vp["group"]["dynamic_nJ"]*1e-6
            costs["Vpath_leakage_proxy"] = attention_groups*t*vp["group"]["held_leakage_uW"]*1e-6
            costs["SparQ_dynamic"] = layers*8*29.603*1e-6
            costs["SparQ_leakage_proxy"] = attention_groups*t*118.52e-6
            costs["GF_sampler_active_proxy"] = layers*row["sampler_active_estimate_nJ"]*1e-6
            # Gross-active S64 proxy is about1460ns/head. Leakage outside only.
            sampler_instance_s = max(0, attention_groups*t/1000 - layers*32*1460e-9)
            costs["GF_sampler_stopped_leakage_proxy"] = sampler_instance_s*69.343333e-6*1000
            total = sum(costs.values())
            att_bytes = layers*row["KV_KiB"]*1024
            ext_bytes = b["dram_bytes"] - b["old_attention_bytes"] + att_bytes
            # Only retain this column for comparison with old HBM proxy. This
            # is NOT the measured DDR4 command/background/PHY energy.
            ext_proxy = ext_bytes*64e-9 + .05*t
            corners.append({"time_ms": t, "NL_idle_scenario": label,
                            "modules_mJ": costs, "covered_onchip_mJ": total,
                            "covered_onchip_average_W": total/t,
                            "external_legacy_proxy_mJ": ext_proxy,
                            "with_legacy_external_proxy_mJ": total+ext_proxy,
                            "external_bytes_reference": ext_bytes,
                            "GU_inactive_instance_s": inactive_gu,
                            "NL_inactive_instance_s": inactive_nl})
    return {
        "GU_instances": gu_instances, "NL_instances": nl_instances,
        "Attention_KV_groups": attention_groups,
        "GU_frames": gu_frames, "GU_waves": gu_waves,
        "NL_frames": nl_frames, "NL_waves": nl_waves,
        "GU_compute_ms": gu_ms, "NL_compute_ms": nl_ms,
        "GU_active_mJ": gu_active, "NL_active_mJ": nl_active,
        "reference_budget_time_ms": times,
        "reference_Attention_ms": reference_attention_ms,
        "reference_Attention_batch8_us": row["time_us"],
        "covered_onchip_mJ": [min(c["covered_onchip_mJ"] for c in corners), max(c["covered_onchip_mJ"] for c in corners)],
        "covered_onchip_average_W": [min(c["covered_onchip_average_W"] for c in corners), max(c["covered_onchip_average_W"] for c in corners)],
        "with_legacy_external_proxy_mJ": [min(c["with_legacy_external_proxy_mJ"] for c in corners), max(c["with_legacy_external_proxy_mJ"] for c in corners)],
        "covered_area55eq_mm2": area,
        "area_removed_mm2": area_removed, "area_added_mm2": area_added,
        "resident_weight_bytes_per_bank": max(gu_instances*g["resident_weight_bytes"], nl_instances*n["resident_weight_bytes"]),
        "reference_local_weight_bank_bytes": b["local_weight_bank_bytes"],
        "same_old_local_weight_capacity": max(gu_instances*g["resident_weight_bytes"], nl_instances*n["resident_weight_bytes"]) <= b["local_weight_bank_bytes"],
        "attention_reserved_SRAM_bytes": attention_groups*131072,
        "attention_independent_SRAM_banks_required": attention_groups*16,
        "actual_integrated_DDR4_TPOT_ms": None,
        "actual_integrated_DDR4_energy_mJ": None,
        "corners": corners,
    }


def run(path, out):
    i = read(path)
    configs = [(16,256,8),(8,256,8),(32,256,8),(64,256,8),(16,128,8),(16,256,4),(16,256,1)]
    cases = [evaluate(i, *c) for c in configs]
    assert cases[0]["GU_frames"] == 218880
    assert cases[0]["NL_frames"] == 1751040
    assert math.isclose(cases[0]["GU_active_mJ"], 1.3043365632)
    assert math.isclose(cases[0]["NL_active_mJ"], 1.4704183296)
    assert cases[0]["same_old_local_weight_capacity"]
    assert not cases[2]["same_old_local_weight_capacity"]
    assert cases[1]["GU_compute_ms"] > cases[0]["GU_compute_ms"] > cases[2]["GU_compute_ms"]
    assert cases[-1]["reference_budget_time_ms"][0] > cases[0]["reference_budget_time_ms"][0]
    for c in cases:
        for corner in c["corners"]:
            assert "FFN_counter" not in corner["modules_mJ"]
            assert "PV_vector_adders" not in corner["modules_mJ"]
            assert math.isclose(sum(corner["modules_mJ"].values()), corner["covered_onchip_mJ"], rel_tol=1e-12)
            assert math.isclose(corner["covered_onchip_mJ"]/corner["time_ms"], corner["covered_onchip_average_W"], rel_tol=1e-12)
            assert all(v >= 0 for v in corner["modules_mJ"].values())
        assert math.isclose(c["covered_area55eq_mm2"], i["baseline"]["fma"]["covered_area_55eq_mm2"]-sum(c["area_removed_mm2"].values())+sum(c["area_added_mm2"].values()))
    result = {
        "date": "2026-11-01", "scope": i["scope"], "inputs_sha256": digest(path),
        "baseline": i["baseline"]["fma"], "cases": cases,
        "full_unified_TLM_or_DRAMSys_rerun": False,
        "constant_Attention_latency_installed_in_TLM": False,
        "full_chip_area_energy_or_power": None,
        "numerical_quality_or_same_PPL_verified": False,
        "new_EDA_or_model_runs": 0,
        "remaining_integration": [
            "Use ONE shared asynchronous memory timeline for FFN/projections/Attention/prefetch; no113us constant actor",
            "Bind128 real SRAM banks/ports for8 Attention groups; capacity slicing does not create ports",
            "Distinguish replay vector reservations from newly characterized Vctrl bank-cycle behavior",
            "Continuous KV append/feature-major transpose/incomplete tail and final output normalization",
            "GU and NL source sharing/replay/state/holding, crossK alignment/quantization, PPA/quality contract alignment",
            "Measured GU stopped-source/open-clock standby retained; no free clock-gated GU standby assumed",
            "Full DDR4 command/background/PHY accounting; old64pJ/B+50mW column is proxy only"],
    }
    out.mkdir(parents=True, exist_ok=True)
    write_json(out/"RESULTS.json", result)
    write_json(out/"VALIDATION.json", {"status":"PASS", "cases":len(cases),
        "checks":["GU/NL exact tile counts and pJ units", "tail-wave/clock timing", "resident-capacity classification",
                  "larger arrays monotonic compute floor", "shared-DDR parallel reference not ideal division",
                  "no legacy counter/PV double charge", "module energy and E/T conservation",
                  "area once0.81/physical replication", "unknown wholechip DDR and quality preserved"],
        "handoff_checks":i["validation_receipts"], "new_DRAMSys_or_RTL_execution":False})
    cols = ["GU_instances","NL_instances","Attention_KV_groups","reference_budget_time_ms","covered_onchip_mJ","covered_area55eq_mm2","GU_compute_ms","same_old_local_weight_capacity"]
    with (out/"COMPARISON.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols,lineterminator="\n");w.writeheader()
        w.writerows({k:c[k] for k in cols} for c in cases)
    render(i,result,out.parent/"REPORT_ZH.md")
    print(json.dumps({"status":"PASS","cases":[{k:c[k] for k in cols} for c in cases],
                      "full_unified_TLM_or_DRAMSys_rerun":False},ensure_ascii=True))


def render(i, r, path):
    c=r["cases"][0];b=r["baseline"]
    def span(v):return f"{v[0]:.2f}–{v[1]:.2f}"
    rows=["# 最新GU、非线性/Wd与Attention交接的预算重算（2026-11-01）", "",
          "Issue225 / PR226，负责人rayggxia。复用原任务，旧INPUTS/RESULTS及原模块不变。", "",
          "**本次完成三个交接的来源校验、工作量/费用替换和七种资源条件重算；没有重新运行完整unified_v6或整机DRAMSys。** 新交接明确要求共享访存事件接入，不能把113µs直接安装成整机Attention固定延迟。本报告的时间仅作旧HBM预算与局部DDR4实跑相结合的参考包络；完整DDR4时间/能量仍为null。", "",
          "## 一眼可读的结果", "",
          "| 版本/资源 | 参考时间 ms/token | 已计价片上能量 mJ/token | 已覆盖面积 mm² |", "|---|---:|---:|---:|",
          f"| 旧冻结整机，500MHz其余资源 | {b['TPOT_ms']:.2f} | {b['covered_onchip_mJ_per_token']:.2f} | {b['covered_area_55eq_mm2']:.2f} |",
          "| 上次新NL/Attention初估，GU仍是旧代理 | 51.67–53.71 | 74.22–77.62 | 未闭合；保留旧GU池另加NL |"]
    for x in r["cases"]:
        rows.append(f"| 新GU{x['GU_instances']}＋NL{x['NL_instances']}＋KV组{x['Attention_KV_groups']} | {span(x['reference_budget_time_ms'])} | {span(x['covered_onchip_mJ'])} | {x['covered_area55eq_mm2']:.2f} |")
    groups = {
        "GU核活动＋实测闲置": ["GU_active_measured", "GU_inactive_measured_source_stopped_clock_running"],
        "非线性/Wd活动＋闲置情景": ["NL_active_measured", "NL_inactive_proxy_or_diagnostic"],
        "普通共享数字MAC": ["ordinary_BF16_MACs"],
        "片上SRAM及DMA缓冲": ["shared_SRAM", "local_CIM_SRAM_base", "digital_local_buffers", "DMA_response_buffers"],
        "Attention采样/筛选/V通路": ["Vpath_dynamic", "Vpath_leakage_proxy", "SparQ_dynamic", "SparQ_leakage_proxy", "GF_sampler_active_proxy", "GF_sampler_stopped_leakage_proxy"],
        "跨K/量化/恢复预留": ["crossK_quantization_restore_legacy_reserve", "wide_partial_activity_proxy"],
        "FFN外部随机源旧预算预留": ["input_PRNG_old_combined_budget_reserve", "NL_PRNG_old_combined_budget_reserve"],
        "其他向量/非线性旧代理": ["other_vector_and_nonlinear_proxy"],
    }
    for corner in c["corners"]:
        assert math.isclose(sum(sum(corner["modules_mJ"][k] for k in ks) for ks in groups.values()), corner["covered_onchip_mJ"],rel_tol=1e-12)
    rows += ["", "面积为已定价模块的替换账目，并非完整芯片/P&R；外部保持/宏外围/互连/PHY等仍未闭合。其余普通算子继续旧500MHz条件值，GU和NL只采用已经标定的100MHz；没有把100MHz核当500MHz运行。", "",
             "默认GU16/NL256/KV8的分项如下。范围的上下端来自不同时序/闲置情景，各分项上限不能直接相加冒充同一个情景；完整逐情景账目在RESULTS。", "",
             "| 分项 | 已计价能量 mJ/token |", "|---|---:|"]
    for name, ks in groups.items():
        values=[sum(x["modules_mJ"][k] for k in ks) for x in c["corners"]]
        rows.append(f"| {name} | {span([min(values),max(values)])} |")
    rows += ["",
             "## 这次真正更新了什么", "",
             f"- GU默认融合核：64输入同时算64g＋64u，5959.14pJ/帧、660ns、1.2097358424mm²/实例。完整token {c['GU_frames']:,}帧，活动能量 **{c['GU_active_mJ']:.6f}mJ**。这是局部核活动，不是整个FFN。",
             f"- 非线性→Wd保留已测精确加权核：64对g/u→8输出，839.74pJ/帧、660ns；{c['NL_frames']:,}帧，活动 **{c['NL_active_mJ']:.6f}mJ**。两处均不使用OR近似。",
             "- Attention采用实际S64、8组共享同一DDR回放；三场景三seed参考为113.022µs/层批次，而不是独立单组除8。V控制＋4×16ADD每组0.698074mm²，动态163.199nJ/组；原标量PV动态、闲置和面积不再叠加。",
             "- 原GU/down共用的旧计数池两处均被新核取代，才移除旧FFN_counter整个活动/背景/面积；不再把原约31mJ的GU残留代理继续当实测核价格。跨K/量化/恢复预算仍保留。", "",
             "## 时间为什么没有直接大幅下降", "",
             f"同旧驻留容量的16个GU融合核，纯核服务为{c['GU_compute_ms']:.3f}ms；256个NL核为{c['NL_compute_ms']:.3f}ms。旧GU忙时只有{i['baseline']['gu_busy_ns']/1e6:.3f}ms，但完整GU阶段约{i['baseline']['phase_ns']['FFN_gate_up']/1e6:.3f}ms，包含搬运与恢复。时间下端允许新增核服务被已有等待隐藏；上端暴露新增忙时。它不是统计置信区间，也不是已经调度出来的完成时间。", "",
             "默认GU16和NL256各需128KiB驻留权重，可在阶段不重叠时复用旧权重银行；双缓冲共256KiB。GU32/64分别需要加倍/四倍容量与读出接口，已单列，不能写成同资源加速。Attention8组要求1MiB及128个独立1RW bank；已有总容量足够不等于现有拓扑已经提供这些端口。", "",
             "## 功耗与存储边界", "",
             f"默认已计价片上平均功率为{span(c['covered_onchip_average_W'])}W。GU闲置使用实测停源开主钟3.226mW/核，没有免费假设停钟；NL闲置两端为旧泄漏代理和外部R翻转诊断，真实停源闲置仍未知。实际随机源/权重与输入保持/跨K接口仍留在外部预算，不把它们包含在5.959nJ核价里。", "",
             f"若仅为接续旧表而保留64pJ/B＋50mW外存代理，总计{span(c['with_legacy_external_proxy_mJ'])}mJ/token；**这不是DDR4功耗结果，也不能与新DDR4局部总能量混加。** 局部DDR总能量包含八通道背景；整机必须由唯一全局内存服务计一次。", "",
             "## 下一步真正的接入范围", "",
             "1. 保留DRAMSys控制器，FFN、投影、Attention和预取共享异步请求队列/64在途/8KiB返回缓冲；去掉无依赖的宏DMA全局排空。",
             "2. 根据真实bank分配重放GU/Wd装载、跨K/量化和Attention请求；新Vctrl逐bank仲裁与旧向量预留模型不能视为逐拍相同。",
             "3. 加入KV追加、双K布局维护、尾块和末端归一化，重新跑完整DDR4同资源数字/概率对照。当前固定113µs服务仅用于参考预算，未写入TLM。",
             "4. 同时对齐训练/电路的尺度与随机共享：GU输出不是可直接送非线性的最终g/u；先跨K对齐宽累加，再定点量化。无新PPL，也不继承旧精度。", "",
             "## 验证与复现", "",
             "GU：13源文件＋8归档成员；NL：9源文件＋6成员；Attention：36来源SHA、24头/1536样本、6轨迹配对与4反例守卫均PASS。首次NL阅读镜像缺CONFIG、Attention参数名错误保留在VALIDATION，改用正式源路径/正确参数后通过。", "",
             "`python -B architecture_tlm/module_estimate_20261101/estimate.py --inputs architecture_tlm/module_estimate_20261101/INPUTS.json --out architecture_tlm/module_estimate_20261101/results`", "",
             "INPUTS绑定来源字节SHA；RESULTS、COMPARISON和VALIDATION记录七组配置、逐项费用/面积、容量条件和未知项。无新GPU、训练、EDA或完整DRAMSys执行。"]
    Path(path).write_text("\n".join(rows)+"\n",encoding="utf-8",newline="\n")


if __name__ == "__main__":
    ap=argparse.ArgumentParser(__doc__)
    ap.add_argument("--collect-workspace", type=Path)
    ap.add_argument("--inputs", type=Path, default=Path(__file__).with_name("INPUTS.json"))
    ap.add_argument("--out", type=Path, default=Path(__file__).with_name("results"))
    a=ap.parse_args()
    if a.collect_workspace:
        collect(a.collect_workspace.resolve(), a.inputs.parent)
    run(a.inputs,a.out)
