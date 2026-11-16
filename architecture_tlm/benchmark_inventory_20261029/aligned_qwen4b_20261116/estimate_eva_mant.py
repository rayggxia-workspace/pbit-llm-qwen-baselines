"""Shape-level EVA and M-ANT decode estimates on the frozen Qwen workload."""

import argparse
import json
import math
from pathlib import Path
from time import perf_counter

from quick_benchmark import (
    BANDWIDTH_EFFICIENCY,
    MODEL_INDEX,
    packed_tensor_bytes,
    qwen_workload,
    read_json,
    vector_support,
)


EVA_CODEBOOK_BYTES = 8 * 256 * 2
EVA_K_TILE = 1024
MANT_EFFECTIVE_BITS = 4 + (16 + 8) / 64


def eva_linear(outputs, reduction, codebooks):
    # B1 specialization of the public VqArrayMethod's AQLM decode path.
    # One group of codebooks is active at a time. A tile uses 128 indices.
    tiles = [min(EVA_K_TILE, reduction - start)
             for start in range(0, reduction, EVA_K_TILE) for _ in range(codebooks)]
    first = 296 * math.ceil(tiles[0] / 256)
    overlap = sum(max(outputs, 296 * math.ceil(tile / 256)) for tile in tiles[:-1])
    cycles = first + overlap + outputs + 6
    # Qwen's FC dimensions fit one author DRAM buffer tile on each axis except
    # N/K=9728, which can use two. K=9728 occurs on down_proj only.
    # Account for the author's intermediate output reread and writeback.
    k_buffer_tiles = math.ceil(reduction / 8192)
    traffic = codebooks * (outputs * math.ceil(reduction / 8) + EVA_CODEBOOK_BYTES)
    traffic += 2 * reduction + 4 * outputs * k_buffer_tiles
    startup = EVA_CODEBOOK_BYTES + 2 * tiles[0]
    return cycles, traffic, startup


def mant_operation(groups, query_rows, outputs, reduction, tile_ii):
    # 64 reduction rows and 32 output columns per W4A8 logical tile.
    tiles = groups * math.ceil(outputs / 32) * math.ceil(reduction / 64)
    # One query is issued per cycle when reusing a resident GQA tile.
    cycles = tiles * max(query_rows, tile_ii) + 94
    return cycles, packed_tensor_bytes(groups, outputs, reduction, MANT_EFFECTIVE_BITS), 0


def estimate(name, family, setting, shape, target, head):
    context = target["cache_tokens"]
    frequency = target["frequency_MHz"] * 1_000_000
    peak_bps = target["dram_nominal_bandwidth_GBs"] * 1e9
    energy_pjbit = target["dram_transfer_energy_pJ_per_bit"]
    tasks = qwen_workload(shape, context)
    kv_width = shape["kv_heads"] * shape["head_dim"]
    misc_bytes = 4 * shape["hidden"] + 2 * shape["layers"] * (
        2 * shape["hidden"] + 2 * shape["head_dim"]
    )
    kv_bits = 16 if family == "eva" else MANT_EFFECTIVE_BITS
    kv_write = shape["layers"] * math.ceil(2 * kv_width * kv_bits / 8)
    vector_ms = vector_support(shape, context) * 1000 / frequency
    operations = []
    for _, stage, groups, query_rows, outputs, reduction in tasks:
        if stage == "head":
            continue
        if family == "mant":
            row = mant_operation(groups, query_rows, outputs, reduction, setting)
        elif stage in ("qk", "pv"):
            # Common BF16 GQA path used by previous quick benchmarks.
            cycles = math.ceil(groups * query_rows * outputs * reduction / 256)
            row = (cycles, packed_tensor_bytes(groups, outputs, reduction, kv_bits), 0)
        else:
            row = eva_linear(outputs, reduction, setting)
        operations.append((stage, *row))

    latency = {}
    for efficiency in BANDWIDTH_EFFICIENCY:
        cycles_per_byte = frequency / (peak_bps * efficiency)
        common_ms = head["time_ms"] + vector_ms + 1000 * (kv_write + misc_bytes) / (peak_bps * efficiency)
        overlap_cycles = sum(
            math.ceil(startup * cycles_per_byte)
            + max(cycles, math.ceil((traffic - startup) * cycles_per_byte))
            for _, cycles, traffic, startup in operations
        )
        serial_cycles = sum(cycles + traffic * cycles_per_byte
                            for _, cycles, traffic, _ in operations)
        latency[f"{efficiency:.2f}"] = {
            "overlapped_ms": common_ms + 1000 * overlap_cycles / frequency,
            "serial_ms": common_ms + 1000 * serial_cycles / frequency,
        }
    linear = [row for row in operations if row[0] in ("projection", "ffn")]
    attention = [row for row in operations if row[0] in ("qk", "pv")]
    decoder_bytes = sum(row[2] for row in operations) + kv_write + misc_bytes
    total_bytes = decoder_bytes + head["external_bytes"]
    return {
        "candidate": name,
        "family": family,
        "codebooks" if family == "eva" else "assumed_mant_tile_ii_cycles": setting,
        "min_mant_weight_tile_feed_GBs": (
            64 * 32 * MANT_EFFECTIVE_BITS / 8 * frequency / setting / 1e9
            if family == "mant" else None
        ),
        "matrix_operations_ex_head": len(operations),
        "linear_operations_ex_head": len(linear),
        "linear_compute_cycles_ex_head": sum(row[1] for row in linear),
        "attention_compute_cycles": sum(row[1] for row in attention),
        "decoder_linear_traffic_bytes": sum(row[2] for row in linear),
        "kv_read_write_bytes": sum(row[2] for row in attention) + kv_write,
        "external_bytes_including_head": total_bytes,
        "external_mJ": total_bytes * 8 * energy_pjbit / 1e9,
        "shared_head_core_mJ": head["core_energy_mJ"],
        "known_energy_subtotal_mJ": total_bytes * 8 * energy_pjbit / 1e9 + head["core_energy_mJ"],
        "full_onchip_energy_mJ": None,
        "full_energy_mJ": None,
        "original_reported_area_mm2": 1.414 if family == "eva" else 4.587,
        "aligned_full_die_area_mm2": None,
        "latency_scenarios": latency,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    started = perf_counter()
    target, target_sha = read_json(Path(__file__).with_name("TARGET.json"))
    summary, summary_sha = read_json(args.summary)
    index, index_sha = read_json(args.workspace / MODEL_INDEX)
    model = index["models"]["qwen3_4b"]
    if summary_sha != target["project_summary_sha256"] or (
        model["model_id"], model["revision"], model["config_sha256"]
    ) != (target["model_id"], target["model_revision"], target["model_config_sha256"]):
        raise ValueError("The model or shared head differs from the frozen benchmark")
    dense = next(row for row in summary["completed_cases"]
                 if row["model"] == "qwen3_4b" and row["name"] == "full_W8_dense")
    head = dense["head_split"]["lm_head_stage"]
    scenarios = [(f"EVA W{bits}", "eva", bits) for bits in (2, 3, 4)]
    scenarios += [(f"M-ANT W4A8KV4 II={ii}", "mant", ii) for ii in (2, 4, 8, 16)]
    estimates = [estimate(*scenario, model["shape"], target, head) for scenario in scenarios]
    output = {
        "scope": "common_platform_qwen_single_step_analytical_estimate",
        "inputs": {
            "target_sha256": target_sha, "project_summary_sha256": summary_sha,
            "model_index_sha256": index_sha,
            "eva_author_git_blobs": {
                "simulator/methods/vqarray.py": "d58dbcb640388ee731f4992090854d76576c1d03",
                "simulator/methods/base.py": "3655e52a9449c3a4733164db3c80080b892c1694",
                "simulator/configs/methods/eva.yaml": "764e7e4d59401a5288c984c863a9a94baa513367",
            },
        },
        "platform": target,
        "shared_bf16_head": head,
        "external_estimates": estimates,
    }
    args.out.write_bytes((json.dumps(output, indent=2) + "\n").encode("utf-8"))
    print(f"{len(estimates)} analytical scenarios in {perf_counter() - started:.3f} s")
    for row in estimates:
        print(row["candidate"], row["latency_scenarios"]["0.80"], round(row["external_mJ"], 2))


if __name__ == "__main__":
    main()
