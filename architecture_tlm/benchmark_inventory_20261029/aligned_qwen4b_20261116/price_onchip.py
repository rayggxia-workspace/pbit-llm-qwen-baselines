import json
import sys
from pathlib import Path


directory = Path(__file__).resolve().parent
quick = json.loads((directory / "QUICK_BENCHMARK.json").read_text(encoding="utf-8"))
extension = json.loads((directory / "EVA_MANT_ESTIMATE.json").read_text(encoding="utf-8"))
runs = {item["candidate"]: item
        for item in quick["external_estimates"] + extension["external_estimates"]}

linear_macs = 3_633_315_840
attention_macs = 603_979_776
head_mj = 2.5983286409305357
sram_pj_per_byte = (10.360592 + 10.732592) / 16


def dram(row):
    return row.get("dram_transfer_mJ", row.get("external_mJ"))


def estimate(on_chip, row=None, **details):
    data = {"on_chip_mj": on_chip, **details}
    if row is not None:
        data["dram_mj"] = dram(row)
        data["priced_including_dram_mj"] = on_chip + dram(row)
    return data


results = {}
for bits in (3, 6):
    candidate = f"BitMoD W{bits}"
    run = runs[candidate]
    parts = run["bitmod_priced_components"]
    # Table X: 39.36 pJ per 64-PE tile cycle at the published activity.
    table_x = (run["decoder_matrix_cycles"] * 1024 * (39.36 / 64) * 1e-9
               + parts["sram_proxy_dynamic_mJ"] + parts["shared_head_core_mJ"])
    results[candidate] = estimate(
        parts["priced_onchip_subtotal_mJ"], run, table_x_mj=table_x,
        b1_shaped_array_mj=runs[f"{candidate}, B1-shaped array sensitivity"]
        ["bitmod_priced_components"]["priced_onchip_subtotal_mJ"],
    )

tender = runs["Tender W4, paper-style output-stationary mapping"]
# Native 28 nm PE+accumulator power / peak MACs/s.
tender_pe_mj = linear_macs * (1.09 / (4096 * 1e9)) * 1e3
fma_incremental_pj = 3.184765625 - 0.00012853333333333333 * 0.2568359375 * 1e3
tender_attention_mj = attention_macs * fma_incremental_pj * 1e-9
tender_sram_mj = (tender["dram_weight_bytes_ex_head"] + tender["kv_read_write_bytes"]) * sram_pj_per_byte * 1e-9
results["Tender W4"] = estimate(
    tender_pe_mj + tender_attention_mj + tender_sram_mj + head_mj, tender,
    pe_mj=tender_pe_mj, attention_mj=tender_attention_mj, sram_mj=tender_sram_mj,
)

mant = runs["M-ANT W4A8KV4 II=4"]
mant_pe_mj = (linear_macs + attention_macs) * 0.40 * 1e-9
mant_sram_mj = (mant["decoder_linear_traffic_bytes"] + mant["kv_read_write_bytes"]) * sram_pj_per_byte * 1e-9
results["M-ANT W4A8KV4"] = estimate(
    mant_pe_mj + mant_sram_mj + head_mj, mant, pe_mj=mant_pe_mj, sram_mj=mant_sram_mj,
)

# FC activity counted with the open EVA simulator SRAM access equations.
# At 80% bandwidth, timestamps are per-op overlap or serialized FC only.
eva_fc_cases = {
    2: (8_459_820, 1.20223, 70.88),
    3: (12_537_900, 1.80290, 102.56),
    4: (16_615_980, 2.40358, 134.24),
}
for bits, (fc_cycles, sram_dynamic_mj, serialized_on_chip_mj) in eva_fc_cases.items():
    candidate = f"EVA W{bits}"
    core_and_sram_base_pj_per_cycle = 6070.081642
    fc_mj = fc_cycles * core_and_sram_base_pj_per_cycle * 1e-9 + sram_dynamic_mj
    results[candidate] = estimate(
        fc_mj + 36 * 0.0833255048 + head_mj, runs[candidate], fc_mj=fc_mj,
        serialized_on_chip_mj=serialized_on_chip_mj,
    )

# Harmonia Qwen useful-operation proxy, separate from its B1 activity.
results["Harmonia arithmetic only"] = estimate(linear_macs * 2 / 8.176e12 * 1e3
                                               + attention_macs * 2 / 4.088e12 * 1e3)
# OASIS native GEMV calibration at 1% outliers, not an estimate of all stages.
oasis_reduction_j = 2304 / 500e6 * 16 * 0.254
results["OASIS linear GEMV only"] = estimate(
    oasis_reduction_j / 0.331 * linear_macs / (4096 ** 2) * 1e3,
)
# Figure 3, original DeepScaleTool paper. Rounded graph readings.
energy_ratio_28_from_45 = 0.58
energy_ratio_28_from_65 = 0.37
kelle_rsa_native_mj = (6.52 * 0.17) * (2 * linear_macs / 4.13e12) * 1e3
results["Kelle INT8 RSA only"] = estimate(
    kelle_rsa_native_mj * energy_ratio_28_from_45,
    native_node_logic_mj=kelle_rsa_native_mj, logic_energy_scale=energy_ratio_28_from_45,
)
# OPAL: Fig. 8(a) W4A4/7 core segment, read as approximately 0.63 J.
# Shape ratio uses decoder linear MACs as the scaling proxy. Leave the
# original on-chip SRAM, softmax memory and leakage costs at native scope.
opal_native_linear_macs = 80 * (2 * 8192**2 + 2 * 8192 * 1024 + 3 * 8192 * 28672)
results["OPAL core only"] = estimate(
    630 * linear_macs / opal_native_linear_macs * energy_ratio_28_from_65,
    native_node_logic_mj=630, logic_energy_scale=energy_ratio_28_from_65,
    native_decoder_linear_macs=opal_native_linear_macs,
)

if __name__ == "__main__":
    payload = json.dumps(results, ensure_ascii=False, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")

