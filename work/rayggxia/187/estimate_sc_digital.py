"""Arithmetic estimate from recorded anchors, not a circuit/TLM experiment."""
from pathlib import Path
import json
import hashlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DOC = ROOT / 'architecture_tlm/simulator_survey_20261025'
inputs = json.loads((HERE / 'SC_DIGITAL_INPUTS.json').read_text(encoding='utf-8'))
c = inputs['counter_g0']
front = inputs['shared_frontend_proxy']
N, O = 64, 64
macs = N * O
power_mw = (O * c['power_uW'] + front['power_uW']) / 1000
area_mm2 = (O * c['area_um2'] + front['area_um2']) / 1e6
ns64 = c['window_ns'] / c['completed_frames']
rows = []
for T in (32, 64, 128):
    ns = ns64 + (T - 64) * 10
    nj = power_mw * ns / 1000
    rows.append({'T': T, 'area_mm2': area_mm2, 'power_mW': power_mw,
                 'ns_per_gemv_window_equivalent': ns, 'nJ_per_gemv': nj,
                 'pJ_per_effective_MAC': nj * 1000 / macs,
                 'effective_GOPS': 2 * macs / ns,
                 'TOPS_per_W': (2 * macs / ns) / power_mw,
                 'us_per_64x64x64_gemm': ns * 64 / 1000,
                 'uJ_per_64x64x64_gemm': nj * 64 / 1000,
                 'status': 'T64 measurement-based replication; other T fixed-power sensitivity, not new RTL'})
refs = []
for r in inputs['digital_references']:
    pj_mac = 2 * r['power_W'] / r['throughput_GOPS'] * 1000
    refs.append({**r, 'pJ_per_equivalent_MAC': pj_mac,
                 'nJ_per_4096_MAC_equivalent': pj_mac * macs / 1000,
                 'ns_per_4096_MAC_throughput_equivalent': 2 * macs / r['throughput_GOPS'],
                 'uJ_per_262144_MAC_equivalent': pj_mac * 262144 / 1e6,
                 'us_per_262144_MAC_throughput_equivalent': 2 * 262144 / r['throughput_GOPS'] / 1000,
                 'target_matrix_latency_measured': False})
scale_area = (55 / 28) ** 2
scale_energy = (55 / 28) * (1.08 / 0.72) ** 2
projected = []
for name, area, ee in [('TPU', .370631, 8.05), ('Trapezoid', .283704, 9.31)]:
    e_mac = 2 / ee * scale_energy
    a64 = area / 16 * scale_area
    projected.append({'kind': name, 'node_nm': 55, 'voltage_V': 1.08, 'MAC_units': 64,
                      'frequency_MHz': 100, 'area_mm2': a64,
                      'power_mW': 64 * 100e6 * e_mac * 1e-9,
                      'pJ_per_MAC': e_mac, 'nJ_per_4096_MAC': macs * e_mac / 1000,
                      'ideal_compute_ns_per_4096_MAC': 640,
                      'sc_area_ratio': area_mm2 / a64,
                      'sc_energy_ratio': rows[1]['nJ_per_gemv'] / (macs * e_mac / 1000),
                      'status': 'illustrative process/voltage and linear resource projection, not ported RTL'})
g2 = inputs['counter_g2']
g2_power = (O * g2['power_uW'] + front['power_uW']) / 1000
leak_mw = (O * c['leakage_uW'] + front['leakage_uW']) / 1000
voltage12_power = (power_mw - leak_mw) * (1.2 / 1.08) ** 2 + leak_mw
out = {'kind': 'MEASUREMENT_ANCHORED_ARITHMETIC_ESTIMATE_NOT_NEW_PPA',
       'date': '2026-10-27', 'workload': 'X[M,64] times W[64,64]; 4096 effective MAC per vector',
       'counted_boundary': 'replicated merged counters plus one shared64 frontend proxy',
       'excluded_costs': ['full-parallel weight readout/holding/driver', 'weight programming',
                          'BF16 input encoding/common coefficient/output conversion',
                          'complete array wiring/CTS', 'external memory'],
       'sc_rows': rows, 'digital_reference_equivalents': refs,
       'area_scaling_factor_28_to_55': scale_area,
       'energy_scaling_factor_cap_linear_voltage_squared': scale_energy,
       'projected_64mac_digital': projected,
       'voltage_only_1p2V_same_leakage_nJ_gemv': voltage12_power * ns64 / 1000,
       'counter_ICG': {'continuous_total_power_mW': g2_power,
                       'continuous_nJ_gemv': g2_power * ns64 / 1000,
                       'counter_idle_mW_g0': O * c['idle_uW'] / 1000,
                       'counter_idle_mW_g2': O * g2['idle_uW'] / 1000},
       'B7_T128_bitwork_proxy_nJ_gemv':
           (O * c['power_uW'] * inputs['b7_scale'] + front['power_uW']) / 1000 * rows[2]['ns_per_gemv_window_equivalent'] / 1000,
       'one_ordinary_E_macro_storage_proxy': {
           'capacity_bytes': 4096, 'area_mm2': inputs['sram']['area_um2'] / 1e6,
           'cold_program_nJ': 256 * inputs['sram']['write_pJ_per_16B'] / 1000,
           'full_parallel_interface_verified': False},
       'OS32_GEMM_ideal_wavefront_example': {'cycles_per_tile': 64 + 32 + 32 - 2,
                                           'tiles': 4, 'frequency_MHz': 1000,
                                           'total_compute_us': 4 * (64 + 32 + 32 - 2) / 1000,
                                           'includes': 'wavefront fill',
                                           'excludes': 'load, output draining bandwidth, control and RTL input stage'},
       'T_break_even_against_55nm_mobile_workload_energy':
           refs[2]['nJ_per_4096_MAC_equivalent'] * 1000 / power_mw / 10 - (ns64 / 10 - 64),
       'source_inputs_sha256': hashlib.sha256((HERE / 'SC_DIGITAL_INPUTS.json').read_bytes()).hexdigest(),
       'new_digital_runs': 0, 'quality_equivalence_verified': False}
assert abs(rows[1]['nJ_per_gemv'] - 30.48338425) < 1e-8
assert abs(rows[1]['us_per_64x64x64_gemm'] - 44.88) < 1e-8
(DOC / 'SC_DIGITAL_ESTIMATE.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({'T64': rows[1], '55nm_projection': projected,
                  'B7_T128_nJ': out['B7_T128_bitwork_proxy_nJ_gemv']}, ensure_ascii=False))
