"""Replay the full B1 Qwen3-4B decode workload on a published Harmonia core."""

import argparse
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
from math import ceil, isclose
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def div_up(numerator, denominator):
    return (numerator + denominator - 1) // denominator


def align(value, width):
    return div_up(value, width) * width


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class Tile:
    cycles: int
    macs: int = 0
    read: int = 0
    write: int = 0
    sram_read: int = 0
    sram_write: int = 0


class Replay:
    def __init__(self, model, paper, target, kv_mode):
        self.model = model
        self.paper = paper
        self.target = target
        self.kv_mode = kv_mode
        self.stages = defaultdict(lambda: defaultdict(int))
        self.rows = paper["pe_rows"]
        self.columns = paper["pe_columns"]
        self.group = paper["bfp_group_size"]
        self.head_dim = model["head_dim"]
        self.query_rows = model["query_heads"] // model["kv_heads"]
        self.kv_dim = model["kv_heads"] * self.head_dim
        self.query_dim = model["query_heads"] * self.head_dim
        self.clock = target["frequency_mhz"] * 1e6
        self.bandwidth = target["bandwidth_gbs"] * target["memory_efficiency"] * 1e9
        self.service_cycles_per_byte = self.clock / self.bandwidth
        self.response_latency_cycles = target["request_setup_ns"] * 1e-9 * self.clock
        self.extra = target["array_tile_extra_cycles"]
        self.peak_mac = self.rows * self.columns * self.group
        source_peak = (
            paper["peak_gops_per_w_m8w4"] * paper["total_power_mw"] * 0.5
            / paper["frequency_mhz"]
        )
        assert isclose(self.peak_mac, source_peak, rel_tol=0.001)
        assert paper["peak_gops_per_w_m8m8"] * 2 == paper["peak_gops_per_w_m8w4"]
        assert target["node_nm"] == paper["node_nm"] and target["voltage"] == paper["voltage"]
        assert model["batch"] == 1 and model["outputs"] == 1
        assert self.query_rows <= self.rows

    def packed_bfp(self, groups, mantissa):
        # Sign bits are counted separately. The five-bit exponent is stored in a byte.
        payload = self.group * (mantissa + 1) // 8
        return groups * (payload + self.target["exponent_bytes_per_group"])

    def stage(self, name, tiles, occupied_rows=0):
        """Assign each tile to a reusable buffer slot; one shared external link and PE port."""
        t = self.target
        slot_available = [0] * t["buffer_slots"]
        link_free = memory_end = compute_end = 0
        stats = self.stages[name]
        for index, tile in enumerate(tiles):
            slot = index % len(slot_available)
            read = align(tile.read, t["burst_bytes"])
            write = align(tile.write, t["burst_bytes"])
            ready = 0
            if read:
                link_free = max(link_free, slot_available[slot]) + read * self.service_cycles_per_byte
                memory_end = link_free + self.response_latency_cycles
                ready = ceil(memory_end)
            compute_end = max(compute_end, ready) + tile.cycles
            if write:
                link_free = max(link_free, compute_end) + write * self.service_cycles_per_byte
                memory_end = link_free + self.response_latency_cycles
            slot_available[slot] = max(compute_end, ceil(memory_end) if write else 0)
            stats["macs"] += tile.macs
            stats["dram_read_bytes"] += read
            stats["dram_write_bytes"] += write
            stats["sram_read_words"] += div_up(tile.sram_read + write, t["sram_word_bytes"])
            stats["sram_write_words"] += div_up(tile.sram_write + read, t["sram_word_bytes"])
            stats["dram_link_busy_cycles"] += (read + write) * self.service_cycles_per_byte
            stats["pe_cycles"] += tile.cycles if occupied_rows else 0
            stats["occupied_row_cycles"] += tile.cycles * occupied_rows
            stats["tiles"] += 1
        stats["calls"] += 1
        stats["elapsed_cycles"] += max(ceil(memory_end), compute_end)

    def vector(self, name, elements, passes, read=0, write=0):
        self.stage(name, [Tile(
            cycles=div_up(elements, self.target["vector_elements_per_cycle"]) * passes + 8,
            read=read,
            write=write,
            sram_read=elements * 2 * max(passes - 1, 1),
            sram_write=elements * 2,
        )])

    def linear(self, name, in_dim, out_dim, retain_output=True):
        t = self.target
        weight_group = self.paper["int4_group_size"]
        group_bytes = weight_group // 2 + t["weight_group_metadata_bytes"]
        slot_groups = t["weight_slot_bytes"] // (self.columns * group_bytes)
        assert slot_groups > 0
        input_chunk = slot_groups * weight_group
        assert in_dim % weight_group == 0 and out_dim % self.columns == 0

        def tiles():
            for output in range(0, out_dim, self.columns):
                for start in range(0, in_dim, input_chunk):
                    count = min(input_chunk, in_dim - start)
                    weight_bytes = count // weight_group * self.columns * group_bytes
                    assert weight_bytes <= t["weight_slot_bytes"]
                    last = start + count == in_dim
                    extra = self.extra if start == 0 else 0
                    result_bytes = self.columns * 2 if last else 0
                    # LM head drains directly into a running argmax at one result tile per cycle.
                    reduction = 1 if last and not retain_output else 0
                    activation_bytes = self.packed_bfp(count // self.group, 8)
                    yield Tile(
                        cycles=count // self.group + extra + reduction,
                        macs=count * self.columns,
                        read=weight_bytes,
                        sram_read=weight_bytes + activation_bytes,
                        sram_write=result_bytes if retain_output else 0,
                    )

        self.stage(name, tiles(), occupied_rows=1)
        if retain_output:
            self.intermediate(out_dim)

    def intermediate(self, elements):
        if self.target["spill_intermediates"]:
            size = elements * 2
            self.stage("intermediate_spills", [Tile(cycles=0, write=size)])
            self.stage("intermediate_spills", [Tile(cycles=0, read=size)])

    def cache_append(self):
        m = self.model
        base_group = self.group
        key = self.packed_bfp(self.kv_dim // base_group, 8)
        # The raw V suffix is needed to regroup a partially filled temporal BFP group.
        raw_suffix = (m["cached_tokens"] % base_group) * self.kv_dim * 2
        new_raw_suffix = raw_suffix + self.kv_dim * 2
        packed_v = self.packed_bfp(self.kv_dim, 8) if new_raw_suffix == base_group * self.kv_dim * 2 else 0
        migration_read = migration_write = 0
        if self.kv_mode == "mix":
            # Amortize a V-group migration from the high-precision recent window.
            migration_read = div_up(self.packed_bfp(self.kv_dim, 8), base_group) + key
            migration_write = 2 * div_up(self.packed_bfp(self.kv_dim, 4), base_group)
        self.vector(
            "kv_update",
            (raw_suffix // 2 + 2 * self.kv_dim),
            2,
            read=raw_suffix + migration_read,
            write=key + new_raw_suffix + packed_v + migration_write,
        )

    def kv_segments(self):
        length = self.model["attended_positions"]
        if self.kv_mode == "m8":
            return [(length, 8)]
        initial = min(self.paper["initial_m8_tokens"], length)
        recent = min(self.paper["local_m8_tokens"], length - initial)
        return [(initial, 8), (length - initial - recent, 4), (recent, 8)]

    def attention(self, name):
        is_qk = name == "qk"

        def tiles():
            for segment_length, mantissa in self.kv_segments():
                for start in range(0, segment_length, self.target["kv_chunk_tokens"]):
                    tokens = min(self.target["kv_chunk_tokens"], segment_length - start)
                    repeat = 2 if mantissa == 8 else 1
                    reduction_dim = self.head_dim if is_qk else tokens
                    columns = tokens if is_qk else self.head_dim
                    outputs = div_up(columns, self.columns)
                    cycles = outputs * (div_up(reduction_dim, self.group) * repeat + self.extra)
                    # K is grouped per token, V uses the temporal dimension.
                    groups = (tokens * div_up(self.head_dim, self.group) if is_qk
                              else self.head_dim * div_up(tokens, self.group))
                    kv_bytes = self.packed_bfp(groups, mantissa)
                    query_reads = self.packed_bfp(
                        self.query_rows * div_up(reduction_dim, self.group), 8
                    ) * outputs
                    result_bytes = self.query_rows * columns * (2 if is_qk else 4)
                    partial_reads = 0 if is_qk else result_bytes
                    yield Tile(
                        cycles=cycles,
                        macs=self.query_rows * tokens * self.head_dim,
                        read=kv_bytes,
                        sram_read=kv_bytes + query_reads + partial_reads,
                        sram_write=result_bytes,
                    )

        self.stage(name, tiles(), occupied_rows=self.query_rows)

    def run(self):
        m = self.model
        h = m["hidden"]
        intermediate = m["intermediate"]
        self.vector("embedding", h, 1, read=h * 2)
        for _ in range(m["layers"]):
            self.vector("attn_input_rmsnorm", h, 3, read=h * 2)
            self.linear("q_proj", h, self.query_dim)
            self.linear("k_proj", h, self.kv_dim)
            self.linear("v_proj", h, self.kv_dim)
            if m["qk_norm"]:
                self.vector("qk_norm", self.query_dim + self.kv_dim, 3, read=4 * self.head_dim)
            self.vector("rope", self.query_dim + self.kv_dim, 2)
            self.cache_append()
            for _ in range(m["kv_heads"]):
                self.attention("qk")
                self.intermediate(self.query_rows * m["attended_positions"])
                self.vector("softmax_bfp", self.query_rows * m["attended_positions"], 3)
                self.intermediate(self.query_rows * m["attended_positions"])
                self.attention("pv")
            self.linear("o_proj", self.query_dim, h)
            self.vector("attn_residual", h, 1)
            self.vector("ffn_input_rmsnorm", h, 3, read=h * 2)
            self.linear("gate_proj", h, intermediate)
            self.linear("up_proj", h, intermediate)
            self.vector("swiglu_bfp", intermediate, 2)
            self.linear("down_proj", intermediate, h)
            self.vector("ffn_residual", h, 1)
        self.vector("final_rmsnorm", h, 3, read=h * 2)
        self.linear("lm_head", h, m["vocab"], retain_output=False)
        self.vector("output_select", 1, 1, write=4)
        return self.total()

    def total(self):
        m, p, t = self.model, self.paper, self.target
        rows = dict(self.stages)
        total = {key: sum(s[key] for s in rows.values()) for key in rows["lm_head"]}
        linear_macs = (
            m["layers"] * (
                2 * m["hidden"] * (self.query_dim + self.kv_dim)
                + 3 * m["hidden"] * m["intermediate"]
            ) + m["hidden"] * m["vocab"]
        )
        attention_macs = 2 * m["layers"] * self.query_dim * m["attended_positions"]
        assert total["macs"] == linear_macs + attention_macs
        assert rows["qk"]["calls"] == rows["pv"]["calls"] == m["layers"] * m["kv_heads"]
        assert rows["lm_head"]["macs"] == m["hidden"] * m["vocab"]
        assert rows["lm_head"]["dram_read_bytes"] == packed_head_weight_bytes(m, p, t)
        assert all(s["elapsed_cycles"] + 1e-6 >= s["dram_link_busy_cycles"] for s in rows.values())
        assert all(s["elapsed_cycles"] >= s["pe_cycles"] for s in rows.values())
        assert all(s["macs"] <= s["occupied_row_cycles"] * self.peak_mac / self.rows for s in rows.values())
        assert all(s["dram_read_bytes"] % t["burst_bytes"] == 0 for s in rows.values())
        assert all(s["dram_write_bytes"] % t["burst_bytes"] == 0 for s in rows.values())
        time_ms = total["elapsed_cycles"] / self.clock * 1e3
        total_bytes = total["dram_read_bytes"] + total["dram_write_bytes"]
        power = p["component_area_mm2_and_power_mw"]
        static_fraction = t["native_static_fraction"]
        fixed_activity = t["pe_fixed_activity_fraction"]
        frequency_ratio = t["frequency_mhz"] / p["frequency_mhz"]
        pe_cycles_scaled = (
            fixed_activity * total["pe_cycles"]
            + (1 - fixed_activity) * total["occupied_row_cycles"] / self.rows
        )
        pe_mj = (
            power["pe"][1] * frequency_ratio * (1 - static_fraction)
            * pe_cycles_scaled / self.clock
        )
        sram_mj = 1e-9 * (
            total["sram_read_words"] * t["sram_read_pj_per_word"]
            + total["sram_write_words"] * t["sram_write_pj_per_word"]
        )
        native_misc_mw = p["total_power_mw"] - power["pe"][1] - power["sram"][1]
        misc_mj = native_misc_mw * (1 - static_fraction) * frequency_ratio * time_ms / 1000
        idle_mj = p["total_power_mw"] * static_fraction * time_ms / 1000
        common_mj = t["common_platform_w"] * time_ms
        energy = {
            "pe_dynamic": pe_mj,
            "sram_access": sram_mj,
            "native_misc_dynamic": misc_mj,
            "native_static_assumption": idle_mj,
            "common_platform": common_mj,
            "dram": total_bytes * 8 * t["dram_pj_per_bit"] * 1e-9,
        }
        core_mj = sum(value for name, value in energy.items() if name != "dram")
        total_mj = core_mj + energy["dram"]
        area = p["total_area_mm2"] + t["common_dma_buffers_area_mm2"] + t["common_vector_area_mm2"]
        assert time_ms >= total_bytes * 1e3 / self.bandwidth
        return {
            "kv_mode": self.kv_mode,
            "time_ms": time_ms,
            "area_mm2": area,
            "native_core_area_mm2": p["total_area_mm2"],
            "peak_unpartitioned_core_power_at_target_mw": p["total_power_mw"] * frequency_ratio,
            "core_mJ": core_mj,
            "total_mJ": total_mj,
            "average_core_W": core_mj / time_ms,
            "average_total_W": total_mj / time_ms,
            "dram_minimum_time_at_peak_ms": total_bytes / (t["bandwidth_gbs"] * 1e6),
            "energy_mJ": energy,
            "counts": total,
            "stages": rows,
        }


def packed_head_weight_bytes(model, paper, target):
    weights = model["hidden"] * model["vocab"]
    metadata = weights // paper["int4_group_size"] * target["weight_group_metadata_bytes"]
    return weights // 2 + metadata


def verify_source_files(config, workspace):
    hashes = config["source_files_sha256"]
    for name, expected in hashes.items():
        found = hashlib.sha256((workspace / name).read_bytes()).hexdigest()
        assert found == expected, f"Source digest changed: {name}: {found}"
    index_path = "architecture_tlm/process_28nm/cross_models_20261110/MODELS.json"
    ref = load_json(workspace / index_path)["models"]["qwen3_4b"]
    m = config["workload"]
    assert m["model_id"] == ref["model_id"] and m["revision_in_project_manifest"] == ref["revision"]
    assert m["qk_norm"] == ref["qk_norm"] and m["tie_word_embeddings"] == ref["tie_word_embeddings"]
    fields = {"hidden": "hidden", "intermediate": "ffn", "layers": "layers",
              "query_heads": "q_heads", "kv_heads": "kv_heads", "head_dim": "head_dim", "vocab": "vocab"}
    assert all(m[local] == ref["shape"][source] for local, source in fields.items())
    frozen = load_json(workspace / "architecture_tlm/process_28nm/250MHz/WHOLE_CONFIG.json")
    assert config["target"]["frequency_mhz"] == frozen["clock_MHz"]
    assert isclose(config["target"]["sram_read_pj_per_word"], frozen["SRAM"]["read_pJ_per16B"])
    assert isclose(config["target"]["sram_write_pj_per_word"], frozen["SRAM"]["write_pJ_per16B"])
    assert str(config["target"]["bandwidth_gbs"]) in frozen["external_memory_policy"]
    budget = load_json(workspace / "project_archives/tlm28p250_full225_20261110/seed17/BUDGET.json")
    dma = next(row for row in budget["rows"] if row["component"] == "DMA_FIFO_and_platform_macros")
    assert config["target"]["common_dma_buffers_area_mm2"] == dma["area_detail"]["register_area_mm2"]
    assert config["target"]["common_vector_area_mm2"] == dma["area_detail"]["vector_output_mm2"]


def scenarios(config):
    t = config["target"]
    changes = [
        ("target_m8", "m8", {}),
        ("target_mix", "mix", {}),
        ("at_85_percent_bandwidth", "m8", {"memory_efficiency": 0.85}),
        ("lower_service_overhead", "m8", {"memory_efficiency": 1.0, "array_tile_extra_cycles": 0}),
        ("higher_service_overhead", "m8", {"memory_efficiency": 0.7, "array_tile_extra_cycles": 16}),
        ("without_ping_pong", "m8", {"buffer_slots": 1}),
        ("with_fp16_intermediate_spills", "m8", {"spill_intermediates": True}),
        ("half_target_bandwidth", "m8", {"bandwidth_gbs": t["bandwidth_gbs"] / 2}),
        ("double_target_bandwidth", "m8", {"bandwidth_gbs": 2 * t["bandwidth_gbs"]}),
        ("low_pe_and_static_activity", "m8", {"pe_fixed_activity_fraction": 0.0, "native_static_fraction": 0.02}),
        ("high_pe_and_static_activity", "m8", {"pe_fixed_activity_fraction": 1.0, "native_static_fraction": 0.20}),
        ("paper_frequency_and_memory_on_qwen", "m8", {
            "frequency_mhz": config["paper"]["frequency_mhz"],
            "bandwidth_gbs": config["paper"]["bandwidth_gbs"],
            "dram_pj_per_bit": config["paper"]["dram_pj_per_bit"],
        }),
    ]
    reports = {}
    for name, mode, overrides in changes:
        target = {**t, **overrides}
        result = Replay(config["workload"], config["paper"], target, mode).run()
        result["scenario_changes"] = overrides
        reports[name] = result
    a, b = reports["target_m8"], reports["target_mix"]
    assert a["counts"]["macs"] == b["counts"]["macs"]
    assert b["time_ms"] < a["time_ms"] < reports["without_ping_pong"]["time_ms"]
    assert b["energy_mJ"]["dram"] < a["energy_mJ"]["dram"]
    assert b["area_mm2"] == a["area_mm2"]
    assert reports["with_fp16_intermediate_spills"]["energy_mJ"]["dram"] > a["energy_mJ"]["dram"]
    assert reports["half_target_bandwidth"]["time_ms"] >= a["time_ms"]
    assert a["time_ms"] >= reports["double_target_bandwidth"]["time_ms"]
    assert reports["low_pe_and_static_activity"]["core_mJ"] < a["core_mJ"]
    assert a["core_mJ"] < reports["high_pe_and_static_activity"]["core_mJ"]
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=ROOT / "INPUTS.json")
    parser.add_argument("--output", type=Path, default=ROOT / "RESULTS.json")
    parser.add_argument("--workspace", type=Path, help="Verify the frozen project source files and add reference rows.")
    args = parser.parse_args()
    config = load_json(args.inputs)
    reference_rows = []
    if args.workspace:
        verify_source_files(config, args.workspace)
        ref = load_json(args.workspace / "architecture_tlm/process_28nm/results_20261111/SUMMARY.json")
        reference_rows = [r for r in ref["rows"] if r["model"] == "qwen3_4b"]
        assert len(reference_rows) == 4
    results = scenarios(config)
    fields = ("time_ms", "area_mm2", "core_mJ", "total_mJ", "average_core_W", "average_total_W")
    result = {
        "evidence": "analytical full-decode replay; paper RTL calibration; no Qwen numeric inference",
        "input_sha256": hashlib.sha256(args.inputs.read_bytes()).hexdigest(),
        "source_files_verified": bool(args.workspace),
        "project_native_tlm": reference_rows,
        "main_cases": {name: results[name] for name in ("target_m8", "target_mix")},
        "sensitivities": {
            name: {**{key: r[key] for key in fields}, "changes": r["scenario_changes"]}
            for name, r in results.items() if not name.startswith("target_")
        },
    }
    args.output.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    for name, row in results.items():
        print(name, *(f"{row[key]:.4f}" for key in fields))


if __name__ == "__main__":
    main()
