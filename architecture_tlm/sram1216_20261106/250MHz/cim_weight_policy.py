"""Ordinary-SRAM energy proxy for resident CIM weights (user, 2026-11-09).

Charge one read-equivalent per used 8KiB weight tile, reused across samples.
Writes, physical SRAM area and leakage remain owned by the memory ledger.
This price policy adds no serial SRAM transactions to the CIM timing model.
"""
import math

POLICY_ID = 'ordinary_sram_resident_weight_v1_20261109'


def weight_read_cost(result, read_pJ_per_word, word_bytes=16):
    frames = result.get('kernel_active', {})
    n = sum(frames.get(k, 0) for k in ('GU_frames', 'Wd_M128_frames'))
    if n < 0 or int(n) != n or 8192 % word_bytes:
        raise ValueError('invalid resident M128/K64 weight footprint')
    if not math.isfinite(read_pJ_per_word) or read_pJ_per_word < 0:
        raise ValueError('invalid ordinary SRAM read tariff')
    expected = int(n) * (8192 // word_bytes)
    # A later execution model may emit these reads itself. Do not bill twice.
    tags = result['memory']['SRAM'].get('by_tag', {})
    already = sum(tags.get(k, {}).get('read_words', 0) for k in (
        'CIM_weight_presentation_read', 'GU_weight_presentation_read',
        'Wd_weight_presentation_read'))
    if not 0 <= already <= expected:
        raise ValueError('weight presentation reads exceed used weight tiles')
    extra = expected - already
    return dict(policy_id=POLICY_ID, weight_frames=int(n),
                tile_bytes=8192, word_bytes=word_bytes,
                equivalent_read_words=expected, reads_already_in_memory=already,
                additional_read_words=extra, read_pJ_per_word=read_pJ_per_word,
                additional_uJ=extra * read_pJ_per_word / 1e6,
                writes_area_leakage_owner='existing physical SRAM ledger',
                repeated_sample_reads=False, timing_changed=False,
                status='USER_SELECTED_ORDINARY_SRAM_PROXY_NOT_CUSTOM_CIM_PPA')
