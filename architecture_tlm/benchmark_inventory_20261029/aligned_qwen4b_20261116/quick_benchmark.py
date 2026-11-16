"""Estimate matched Qwen decode scenarios without a native DRAM simulation."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from time import perf_counter

from run_bitmod_pilot import COMMIT, MODEL_INDEX, qwen_workload, verify_author_files


SRAM_READ_PJ_PER_16B = 10.360592
SRAM_WRITE_PJ_PER_16B = 10.732592
BITMOD_TILE_AREA_MM2 = 0.099509
SRAM_MM2_PER_4KIB = 0.01188012105
SRAM_MM2_PER_8KIB = 0.01735667145
BANDWIDTH_EFFICIENCY = (0.65, 0.80, 0.90)
SCENARIOS = (
    ("BitMoD W6", (64, 16), 6.0625, 8),
    ("BitMoD W3", (64, 16), 3.0625, 8),
    ("BitMoD W6, B1-shaped array sensitivity", (256, 4), 6.0625, 8),
    ("BitMoD W3, B1-shaped array sensitivity", (256, 4), 3.0625, 8),
    ("Tender W4, paper-style output-stationary mapping", None, 4.125, 16),
)


def read_json(path):
    data = path.read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def source_bitmod_cycles(artifact, tasks, target, dimensions, weight_bits):
    sys.path.insert(0, str((artifact / "bitmod_sim").resolve()))
    from accelerator import Accelerator

    class BitMoDQwen(Accelerator):
        def _init_model_profiler(self, model_name, cxt_len, is_generation):
            self.layer_name_list = [name for name, _, _, _, _, _ in tasks]
            self.weight_dim = {n: [g, o, k] for n, _, g, _, o, k in tasks}
            self.input_dim = {n: [g, m, k] for n, _, g, m, _, k in tasks}
            self.output_dim = {n: [g, m, o] for n, _, g, m, o, _ in tasks}

    model = BitMoDQwen(
        model_name=target["model_id"], i_prec=16, kv_prec=8, w_prec=weight_bits,
        batch_size=1, is_bit_serial=True, pe_dp_size=4, pe_energy=0.56,
        pe_area=1507.7, pe_array_dim=list(dimensions), init_mem=False,
        cxt_len=target["cache_tokens"], is_generation=True,
    )
    model._calc_compute_cycle()
    if set(model._layer_cycle_compute) != set(model.layer_name_list):
        raise ValueError("BitMoD cycle coverage differs from the Qwen matrix workload")
    return model._layer_cycle_compute, model.pe_energy


def packed_tensor_bytes(groups, output, reduction, precision):
    bytes_per_row = math.ceil(reduction * precision / 8)
    return math.ceil(groups * output * bytes_per_row / 64) * 64


def vector_support(shape, context):
    # A shared 64-element/cycle proxy for RMSNorm, residual, RoPE, softmax
    # and SwiGLU plus activation conversion. Output selection is in the head.
    hidden, ffn = shape["hidden"], shape["ffn"]
    q_width = shape["q_heads"] * shape["head_dim"]
    kv_width = shape["kv_heads"] * shape["head_dim"]
    passes = ((8, hidden), (4, q_width + kv_width),
              (6, shape["q_heads"] * context), (4, ffn))
    cycles = shape["layers"] * sum(n * math.ceil(size / 64) for n, size in passes)
    return cycles + 3 * math.ceil(hidden / 64)


def estimate(name, dimensions, weight_bits, kv_bits, shape, target, head, tasks, artifact, pilot):
    frequency = target["frequency_MHz"]
    peak_bw = target["dram_nominal_bandwidth_GBs"]
    dram_price = target["dram_transfer_energy_pJ_per_bit"]
    vector_cycles = vector_support(shape, target["cache_tokens"])
    kv_width = shape["kv_heads"] * shape["head_dim"]
    # Assumed streamed embedding row and BF16 norm vectors, plus one KV write.
    misc_bytes = 4 * shape["hidden"] + 2 * shape["layers"] * (
        2 * shape["hidden"] + 2 * shape["head_dim"]
    )
    kv_write = shape["layers"] * 2 * kv_width * kv_bits // 8
    area = None
    if dimensions:
        source_cycles, pe_pj = source_bitmod_cycles(artifact, tasks, target, dimensions, weight_bits)
        if dimensions == (64, 16):
            mode = "author_generation_6bit" if weight_bits > 6 else "author_generation_3bit"
            if sum(source_cycles.values()) != pilot["runs"][mode]["total_matrix_array_cycles"]:
                raise ValueError("BitMoD cycles did not reproduce the frozen author pilot")
            # 16 published tiles and the two original 512 KiB SRAM capacities.
            compute_area = 16 * BITMOD_TILE_AREA_MM2
            area = [
                compute_area + 128 * SRAM_MM2_PER_8KIB,
                compute_area + 256 * SRAM_MM2_PER_4KIB,
            ]

    stages = []
    sram_reads = 0
    sram_writes = misc_bytes + kv_write
    for op, stage, groups, tokens, output, reduction in tasks:
        if stage == "head":
            continue
        attention = stage in ("qk", "pv")
        bit_width = kv_bits if attention else weight_bits
        traffic = packed_tensor_bytes(groups, output, reduction, bit_width)
        if dimensions:
            cycles = int(source_cycles[op])
            columns = dimensions[1]
            rows = dimensions[0]
            digit_cycles = math.ceil(math.floor(bit_width) / 2)
            tiles = cycles // digit_cycles
            weight_read_bits_per_tile = 4 * math.ceil(bit_width / 4) * 4 * rows // 2
            activation_read_bits_per_tile = 4 * 16 * columns // 2
            sram_reads += tiles * (weight_read_bits_per_tile + activation_read_bits_per_tile) // 8
            sram_writes += traffic + 2 * groups * tokens * (output + reduction)
        elif attention:
            # Shared dense BF16 256-lane path, modeling one MAC/lane/cycle.
            cycles = math.ceil(groups * tokens * output * reduction / 256)
        else:
            # B1 occupies one M row of Tender's 64x64 OS grid. Each tile
            # services 64 outputs and K reduction steps plus skew fill/drain.
            cycles = math.ceil(output / 64) * (reduction + 63)
        stages.append((stage, cycles, traffic))

    matrix_cycles = sum(cycles for _, cycles, _ in stages)
    matrix_ms = matrix_cycles / (1000 * frequency)
    support_ms = vector_cycles / (1000 * frequency)
    dram_bytes = sum(b for _, _, b in stages) + kv_write + misc_bytes + head["external_bytes"]
    latency = {}
    for efficiency in BANDWIDTH_EFFICIENCY:
        bandwidth = peak_bw * efficiency
        transfers = [b / (1e6 * bandwidth) for _, _, b in stages]
        auxiliary_ms = support_ms + (kv_write + misc_bytes) / (1e6 * bandwidth) + head["time_ms"]
        overlapped_ms = auxiliary_ms + sum(
            max(cycles / (1000 * frequency), transfer)
            for (_, cycles, _), transfer in zip(stages, transfers)
        )
        latency[f"{efficiency:.2f}"] = {
            "overlapped_ms": overlapped_ms,
            "serial_ms": auxiliary_ms + matrix_ms + sum(transfers),
        }
    dram_mj = dram_bytes * 8 * dram_price / 1e9
    bitmod_accounted = None
    if dimensions:
        pe_mj = matrix_cycles * (dimensions[0] * dimensions[1]) * pe_pj / 1e9
        sram_mj = (sram_reads * SRAM_READ_PJ_PER_16B + sram_writes * SRAM_WRITE_PJ_PER_16B) / 16e9
        bitmod_accounted = {
            "pe_dynamic_mJ": pe_mj,
            "sram_proxy_dynamic_mJ": sram_mj,
            "shared_head_core_mJ": head["core_energy_mJ"],
            "priced_onchip_subtotal_mJ": pe_mj + sram_mj + head["core_energy_mJ"],
            "priced_onchip_plus_dram_subtotal_mJ": pe_mj + sram_mj + head["core_energy_mJ"] + dram_mj,
        }
    return {
        "candidate": name, "pe_grid": list(dimensions) if dimensions else [64, 64],
        "packed_linear_weight_bits": weight_bits, "kv_bits": kv_bits,
        "decoder_matrix_ops": len(stages), "decoder_matrix_cycles": matrix_cycles,
        "decoder_matrix_ms": matrix_ms, "shared_nonmatrix_proxy_ms": support_ms,
        "shared_head_ms": head["time_ms"], "external_bytes": dram_bytes,
        "dram_weight_bytes_ex_head": sum(b for stage, _, b in stages if stage not in ("qk", "pv")),
        "kv_read_write_bytes": sum(b for stage, _, b in stages if stage in ("qk", "pv")) + kv_write,
        "dram_transfer_mJ": dram_mj, "latency_scenarios": latency,
        "bitmod_priced_components": bitmod_accounted,
        "bitmod_array_sram_area_proxy_mm2": area,
        "aligned_full_die_area_mm2": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    started = perf_counter()
    directory = Path(__file__).parent
    target, target_sha = read_json(directory / "TARGET.json")
    pilot, pilot_sha = read_json(directory / "BITMOD_MATRIX_PILOT.json")
    summary, summary_sha = read_json(args.summary)
    model_index, model_index_sha = read_json(args.workspace / MODEL_INDEX)
    source = model_index["models"]["qwen3_4b"]
    if summary_sha != target["project_summary_sha256"] or (
        source["model_id"], source["revision"], source["config_sha256"]
    ) != (target["model_id"], target["model_revision"], target["model_config_sha256"]):
        raise ValueError("The reference or model revision differs from the frozen benchmark")
    verify_author_files(args.artifact)
    results = [row for row in summary["rows"] if row["model"] == "qwen3_4b"]
    reference_dense = next(row for row in summary["completed_cases"]
                           if row["model"] == "qwen3_4b" and row["name"] == "full_W8_dense")
    head = reference_dense["head_split"]["lm_head_stage"]
    tasks = list(qwen_workload(source["shape"], target["cache_tokens"]))
    output = {
        "scope": "shape_level_single_decode_step_estimate",
        "inputs": {"target_sha256": target_sha, "pilot_sha256": pilot_sha,
                   "project_summary_sha256": summary_sha, "model_index_sha256": model_index_sha,
                   "author_code_commit": COMMIT},
        "platform": {key: target[key] for key in (
            "model_id", "model_revision", "technology", "batch", "cache_tokens",
            "frequency_MHz", "dram_nominal_bandwidth_GBs", "dram_transfer_energy_pJ_per_bit",
        )},
        "matrix_ops_including_shared_head": len(tasks),
        "shared_bf16_head": head,
        "project_reference": results,
        "external_estimates": [estimate(*scenario, source["shape"], target, head, tasks,
                                        args.artifact, pilot) for scenario in SCENARIOS],
    }
    args.out.write_bytes((json.dumps(output, indent=2) + "\n").encode("utf-8"))
    print(f"{len(SCENARIOS)} scenarios in {perf_counter() - started:.2f} s (inside Python)")


if __name__ == "__main__":
    main()
