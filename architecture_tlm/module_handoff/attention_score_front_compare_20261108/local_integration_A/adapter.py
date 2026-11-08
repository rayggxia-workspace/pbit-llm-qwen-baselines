"""Explicit A frontend adapter; opt-in, no edits to the host TLM or frozen jobs.

This is a numerical/price-boundary adapter, not a new timing-qualified RTL core.
"""
import re
from pathlib import Path
from architecture_tlm.attention_score_front_20261108 import profile, oracle

ROOT = Path(__file__).resolve().parents[4]
KIND = 's12_max_gap'
SAMPLER = ROOT / 'tmp/attention-compare-issue198-20261027/architecture_tlm/attention_compare_20261027/sampler_gate_hold_20261105'


def lut():
    pairs = re.findall(r"8'd(\d+):sigmoid=8'd(\d+);", (SAMPLER / 'sigmoid.vh').read_text())
    table = dict((int(a), int(b)) for a, b in pairs)
    if set(table) != set(range(256)):
        raise ValueError('Expected the archived complete 256-entry P8 LUT')
    return [table[i] for i in range(256)]


def forward_a(score_bits, mask):
    gaps, active, flags = profile.forward(score_bits, mask, frontend_kind=KIND)
    table = lut()
    return dict(frontend_kind=KIND, gap_u8=gaps, active_mask=active,
                threshold_p8=[table[g] if a else 0 for g, a in zip(gaps, active)],
                numeric_error=bool(flags & 4), input_saturated=bool(flags & 2),
                skip_sampler=bool(flags & 1))


def legacy_s12_payload(score_bits, mask):
    """Only the currently supported old-core contract: 128 finite, valid scores.

    Its candidate_mask is hardwired to all ones and initial winner to zero.
    General mask support requires a new hardware interface, not sentinel scores.
    """
    if len(score_bits) != 128 or len(mask) != 128:
        raise ValueError('Current price/interface covers K128 only')
    if not all(mask) or any(((u >> 23) & 255) == 255 for u in score_bits):
        raise ValueError('Old sampler requires all 128 candidates finite and valid')
    return [oracle.q12(u)[0] for u in score_bits]


def standalone_front_quote(clock_MHz, queries, physical_instances=1, **kwargs):
    result = profile.quote(frontend_kind=KIND, clock_MHz=clock_MHz,
                           queries=queries, physical_instances=physical_instances, **kwargs)
    result.update(frontend_kind=KIND, process='55nm_area_equivalent',
                  scope='standalone_frontend_only', host_default_changed=False,
                  integrated_sampler_replacement_ready=False,
                  integrated_area_mm2=None, integrated_query_nJ=None)
    return result


def integration_contract():
    return dict(
        frontend_kind=KIND, candidate_count=128, input_lanes=4,
        preferred_path='FP32_to_S12_plus_handshake_then_original_S12_sampler',
        preferred_area_formula='old_sampler_area + measured_converter_handshake_increment',
        preferred_energy_formula='old_sampler_query_energy + measured_converter_handshake_increment',
        alternative_path='standalone_A_then_deduplicated_gap_sampler',
        alternative_area_formula='A_area + gap_backend_area (matching process/PVT/interface)',
        alternative_energy_formula='A_query_energy + matched_backend_energy + uncovered_wait_energy',
        cycle_policy='schedule handshake events; do not sum two complete prepare latencies',
        old_sampler_blocks=['S12_store', 'S12_max', 'integer_gap_clip', 'LUT_load', 'P8_store', 'RNG', 'compare', 'arbiter'],
        keep_in_gap_backend=['LUT_load', 'P8_store', 'RNG', 'compare', 'arbiter'],
        remove_from_gap_backend=['S12_store', 'S12_max', 'integer_gap_clip'],
        remove_old_proxies=['wide_score_front_reserve', 'old_front_arithmetic_proxy', 'superseded_score_read_reserve'],
        input_score_bytes_per_query=512, nominal_score_reads16B=32,
        input_write_owner='QK producer', mask_reads='additional physical events if SRAM-backed',
        count_frontend_once_per_query=True, multiply_frontend_by_sample_count=False,
        work_gross_already_includes_work_leakage=True,
        idle_time_unit='sum of instance idle times outside accounted work/wait windows',
        integrated_sampler_replacement_ready=False,
        missing=['converter_handshake_increment_or_matched_gap_backend_PPA',
                 'integrated_handshake_latency_and_activity', '28nm_A_250_500_price_cards'],
        all_valid_only_old_backend=True,
        general_mask_requirements=['pass mask to arbiter', 'choose valid initial winner',
                                   'force invalid P8=0', 'skip all-masked query'])
