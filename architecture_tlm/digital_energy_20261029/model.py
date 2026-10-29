"""Measured scalar data mapped onto the existing TLM MAC lifetime.

This changes an energy quote, not the numeric or timing implementation.
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROFILES = ('nonfused_pair', 'fma2', 'fma3')


def anchors():
    return json.loads((HERE / 'ANCHORS.json').read_text(encoding='utf-8'))


def estimate(config, actions, resource_busy_ns, elapsed_ns, *, profile=None):
    a = anchors()
    options = config.get('digital_power', {})
    name = profile or options.get('profile', 'nonfused_pair')
    if name not in PROFILES:
        raise ValueError('digital power profile is not a scalar drop-in: ' + name)
    keep = options.get('idle_dynamic_keep', .1)
    frequency = config['core_hz']
    lanes = config['macs_per_cycle']
    work = actions.get('bf16_mac', 0)
    busy = resource_busy_ns.get('mac', 0)
    numbers = (keep, frequency, lanes, work, busy, elapsed_ns)
    if any(not math.isfinite(x) or x < 0 for x in numbers) or keep > 1 or frequency == 0 or lanes < 1:
        raise ValueError('invalid digital lifetime contract')
    if int(lanes) != lanes or busy > elapsed_ns + 1e-5:
        raise ValueError('invalid MAC geometry or lifetime')
    seconds = elapsed_ns * 1e-9
    cycles = seconds * frequency
    parts = ['mul1', 'add2'] if name == 'nonfused_pair' else [name]
    rows = []
    for part in parts:
        unit = a['units'][part]
        active, idle = unit['normal'], unit['idle']
        window_per_op = active['window_ns'] / active['operations']
        cycle_per_op = window_per_op * a['reference_hz'] * 1e-9
        # Normalize to completed operations, including the measured drain.
        work_cycles = work * cycle_per_op
        on = max(work_cycles, busy * frequency * 1e-9 * lanes)
        capacity = cycles * lanes
        if on > capacity * (1 + 1e-9):
            raise ValueError('measured action activity exceeds installed instance-cycle capacity')
        on = min(on, capacity)
        idle_edge_pJ = (idle['total_W'] - idle['leakage_W']) / a['reference_hz'] * 1e12
        increment_pJ = (active['total_W'] - idle['total_W']) * window_per_op * 1e3
        if min(idle_edge_pJ, increment_pJ) < 0:
            raise ValueError('negative measured dynamic increment')
        leak = idle['leakage_W'] * lanes * seconds
        background = idle_edge_pJ * (on + keep * (capacity - on)) * 1e-12
        increment = work * increment_pJ * 1e-12
        rows.append(dict(unit=part, energy_J=leak + background + increment,
            leakage_J=leak, background_dynamic_J=background, work_increment_J=increment,
            raw_area_mm2=unit['raw_area_um2'] * lanes * 1e-6,
            area_55eq_mm2=unit['raw_area_um2'] * lanes * 1e-6 * a['area_multiplier'],
            instance_clock_on_cycles=on, instance_total_cycles=capacity,
            work_increment_pJ_per_operation=increment_pJ,
            measured_gross_pJ_per_operation=active['total_W'] * window_per_op * 1e3,
            measured_window_cycles_per_operation=cycle_per_op,
            scalar_STA=unit['STA']))
    sums = {k: sum(r[k] for r in rows) for k in ('energy_J', 'leakage_J',
        'background_dynamic_J', 'work_increment_J', 'raw_area_mm2', 'area_55eq_mm2')}
    return dict(schema_version=1, profile=name, **sums,
        average_W=sums['energy_J'] / seconds if seconds else 0.,
        operations=work, instances=lanes, elapsed_ns=elapsed_ns,
        target_hz=frequency, reference_hz=a['reference_hz'], idle_dynamic_keep=keep,
        measured_PVT=a['PVT'], area_multiplier=a['area_multiplier'], components=rows,
        timing_changed=False, physical_timing_validated=False, full_chip_PPA=False,
        source=a['source'],
        evidence=('sum of independently measured multiplier and adder; not integrated MAC PT'
                  if name == 'nonfused_pair' else 'measured scalar FMA; array and numerical substitution are not validated'),
        excluded=['SRAM and operand supply', 'array interconnect and CTS/ICG',
                  'external accumulator contexts and feedback/format interfaces',
                  'FP32 operand MAC arithmetic', '500MHz pipeline and cell-sizing changes'],
        FP32_MAC_unpriced_count=actions.get('fp32_mac', 0),
        limits=['fixed-voltage energy-per-edge extrapolation when target differs from reference',
                'idle keep fraction is a scenario, not a measured gated array',
                'existing MAC latency/II and memory reservations retained',
                'synthetic normal activity is not a model-activation trace',
                'DOT64 four-lane data cannot replace scalar prices without a schedule change'])


def attach(result, ledger):
    """Replace the exact legacy bf16_mac charge; preserve all other actions."""
    cfg = result['config']
    profile = cfg.get('digital_power', {}).get('profile', 'legacy_proxy')
    if profile == 'legacy_proxy':
        return result
    q = estimate(cfg, result['actions'], result['resource_busy_ns'], result['metrics']['elapsed_ns'])
    old = ledger.replace_action_energy('bf16_mac', q['energy_J'], 'digital_MAC_calibrated')
    result['energy_J'] = dict(ledger.energy)
    result['unpriced_actions'] = dict(ledger.missing)
    result['digital_power'] = dict(q, replaced_legacy_charges_J=old,
        price_scope='only bf16_mac replaced; vector/PV/FP32 and other modules keep their existing prices',
        anchor_sha256=__import__('hashlib').sha256((HERE / 'ANCHORS.json').read_bytes()).hexdigest())
    result['metrics']['priced_subtotal_mJ_per_token'] = sum(ledger.energy.values()) / cfg['decode_tokens'] * 1000
    result['metrics']['digital_MAC_mJ_per_token'] = q['energy_J'] / cfg['decode_tokens'] * 1000
    result['metrics']['digital_MAC_average_W'] = q['average_W']
    result['limitations'].append('BF16 MAC lifetime uses digital_power profile; 100MHz data, conditional target-frequency/idle mapping; complete chip remains unknown')
    return result
