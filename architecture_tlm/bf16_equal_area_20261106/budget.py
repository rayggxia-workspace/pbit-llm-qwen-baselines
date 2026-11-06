"""BF16 resource allocation from calibrated FMA16+c4 costs, not W8 prices."""
import copy
import math

TARGET_MM2 = 67.54144608182283


def allocate(prices, dense_reference):
    excluded = {'ordinary_BF16_FMA', 'ordinary_W8_decode_delta_proxy',
                'FFN_W8_GU_dot64', 'Wd_extension'}
    fixed = {k: v for k, v in dense_reference['covered_areas55_mm2'].items()
             if k not in excluded}
    unit = prices['digital']['fma16_c4']['area55_mm2']
    fixed_sum = math.fsum(fixed.values())
    # K32, four output contexts, BF16 K128 tiles fit one64KiB slot.
    candidates = [dict(lanes=n, area55_mm2=fixed_sum + n / 16 * unit)
                  for n in range(1024, 2049, 32)]
    chosen = min(candidates, key=lambda r: (abs(r['area55_mm2'] - TARGET_MM2), r['lanes']))
    return dict(format='BF16-total-covered-area-1', target_total_area55_mm2=TARGET_MM2,
                **chosen, area_gap_percent=(chosen['area55_mm2'] / TARGET_MM2 - 1) * 100,
                fixed_areas55_mm2=fixed, FMA16_c4_area55_mm2=unit,
                K_parallel=32, K_tile=128, contexts=4, prefetch_slots=4,
                output_tile=chosen['lanes'] // 32 * 4,
                weight_element_bytes=2, physical_activation_hold_bytes=19456,
                FMA_pool_shared_by=['QKV', 'O', 'g', 'u', 'down', 'lm_head'],
                QK_and_PV_unchanged=True, raw65_area_factor_already_applied=0.81,
                selection='nearest feasible32-lane step; no timing-driven area retuning',
                unpriced_adapter_interconnect_delta=True)


def price(result, prices, profile):
    from architecture_tlm.ffn_total_area_20261105.evidence.historical_accounting import price as host_price
    from architecture_tlm.digital_fair_20261105.joint_handoff.accounting import attention_budget
    assert result['scheme'] == 'D_BF16_dense' and result['ffn'] == 'bf16'
    out = host_price(result, prices)
    attention = attention_budget(result, prices, mode='dense')
    for field in ('onchip_components_mJ', 'covered_areas55_mm2'):
        out[field] = {k: v for k, v in out[field].items() if not k.startswith('Attention_')}
        out[field].update(attention[field])
    energy, area = out['onchip_components_mJ'], out['covered_areas55_mm2']
    fma = prices['digital']['fma16_c4']
    units = profile['lanes'] // 16
    # All matrix FMA activity was counted by the execution actor; price physical
    # idle once for the entire token, including waits and non-FFN phases.
    energy['ordinary_BF16_FMA'] = (result['actions']['digital_BF16_MAC'] * fma['incremental_pJ'] * 1e-9
                                  + units * fma['idle_W'] * result['simulated_ms'])
    area['ordinary_BF16_FMA'] = units * fma['area55_mm2']
    old_hold = max(prices['legacy']['remaining_proxy']['digital_local_holding_bytes'],
                   result['unpriced_state_and_actions'].get('digital_activation_hold_bytes_peak', 0))
    hold = max(old_hold, profile['physical_activation_hold_bytes'])
    ingress = prices['legacy']['ingress']
    area['digital_holding_proxy'] += (hold - old_hold) / 24576 * ingress['data_area55_mm2']
    energy['digital_holding_proxy'] += (hold - old_hold) / 24576 * ingress['data_leak_W'] * result['simulated_ms']
    assert not any(k in area for k in ('FFN_W8_GU_dot64', 'ordinary_W8_decode_delta_proxy', 'Wd_extension', 'FFN_common_core'))
    out.update(covered_area55_mm2=math.fsum(area.values()), covered_onchip_mJ=math.fsum(energy.values()),
               BF16_equal_area_profile=copy.deepcopy(profile),
               covered_area_target55_mm2=TARGET_MM2)
    assert abs(out['covered_area55_mm2'] - profile['area55_mm2']) < 1e-8
    out['covered_area_gap_percent'] = (out['covered_area55_mm2'] / TARGET_MM2 - 1) * 100
    out['covered_system_mJ_at4pJ'] = out['covered_onchip_mJ'] + out['external_mJ_by_pJ_per_bit']['4.0']
    out['covered_system_W_at4pJ'] = out['covered_system_mJ_at4pJ'] / result['simulated_ms']
    out['comparison_limitations'] = [
        'near-equal covered area, not full-die area or matched numerical quality',
        'BF16 operands and FP32 feedback; deterministic BF16 LUT SwiGLU reference, not exact real-valued SiLU',
        'same512-lane QK and512-lane online-softmax/PV hardware as current dense W8 comparison',
        'calibrated action energy and explicit shared-memory/format proxies, not new circuit PPA',
        'operand/context interconnect, PHY/IO/CTS and inherited QK reduction remain incomplete boundaries']
    return out
