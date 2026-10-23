"""Read-only P0 resource inventory and conditional lower bounds (Issue 117).

``resource_ledger(cfg, shape, result)`` and ``lower_bounds(cfg, shape, result)``
accept the exact configuration/model/result dictionaries of one unified_v6 run.
They return JSON-serializable dictionaries, never modify inputs or read files.
Optional ``result['_source_path']`` identifies the archived result; callers own
the file hash/commit manifest. New configurations require their own result.

No function turns a timing contract, priced subtotal or state-bit ratio into
physical whole-chip PPA. All times returned by lower_bounds are nanoseconds
for the complete run (not implicitly per token); GB/s means bytes/ns.
"""

import copy
import math


CORE = 'architecture_tlm/unified_v6/core.py'
MODEL = 'architecture_tlm/unified_v6/model.py'
GAPS = 'architecture_tlm/digital_ppa_v1/LATEST_TLM_RTL_GAPS_ZH.md'
REQUESTS = 'architecture_tlm/digital_ppa_v1/LATEST_TLM_RTL_REQUESTS.json'


def _number(value, name, *, positive=False, integer=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0
            or (positive and value == 0)
            or (integer and int(value) != value)):
        raise ValueError('invalid ' + name)
    return int(value) if integer else value


def _ceildiv(a, b):
    return (a + b - 1) // b


def _validate(cfg, shape, result):
    # Refuse to silently combine changed hardware with an old traffic trace.
    if 'config' in result and result['config'] != cfg:
        raise ValueError('configuration differs from result; execute candidate first')
    if 'model' in result and result['model'] != shape:
        raise ValueError('model shape differs from result')
    for name in ('hidden_size', 'intermediate_size', 'num_hidden_layers',
                 'num_attention_heads', 'num_key_value_heads'):
        _number(shape[name], name, positive=True, integer=True)
    if (shape['hidden_size'] % shape['num_attention_heads']
            or shape['num_attention_heads'] % shape['num_key_value_heads']):
        raise ValueError('invalid GQA geometry')
    _number(cfg['core_hz'], 'core_hz', positive=True)
    _number(cfg['context_tokens'], 'context_tokens', positive=True, integer=True)
    _number(cfg['decode_tokens'], 'decode_tokens', positive=True, integer=True)
    for name in ('capacity_bytes', 'banks', 'word_bytes', 'macro_depth'):
        _number(cfg['sram'][name], 'sram.' + name, positive=True, integer=True)
    for name in ('clock_hz', 'fabric_GBs'):
        _number(cfg['sram'][name], 'sram.' + name, positive=True)


def _physical_traffic(traffic, label):
    return sum(_number(v, label + '.' + k, integer=True)
               for k, v in traffic.items() if k.endswith('_physical_bytes'))


def _entry(name, evidence, **fields):
    return dict(module=name, area_mm2=None, energy_J=None,
                physical_instances=None, physical_state_bits=None,
                evidence=evidence, **fields)


def resource_ledger(cfg, shape, result):
    """Inventory configured resources, physical anchors and explicit gaps.

    Configured parallelism is not a synthesized physical instance count.
    Storage in SRAM.layout is already inside the macro bank inventory; SC
    local counters/weight retention are separate, unresolved interfaces.
    """
    _validate(cfg, shape, result)
    s, f = cfg['sram'], cfg['ffn']
    memory = result['SRAM']
    macro = memory['calibrated_macro']
    macro_bytes = s['word_bytes'] * s['macro_depth']
    macros = _ceildiv(s['capacity_bytes'], s['banks'] * macro_bytes) * s['banks']
    physical = macros * macro_bytes
    for field, expected in [('macros', macros), ('physical_bytes', physical),
                            ('configured_bytes', s['capacity_bytes']), ('banks', s['banks'])]:
        if field in memory and memory[field] != expected:
            raise ValueError('SRAM report/config mismatch: ' + field)
    macro_area = _number(macro['area_mm2'], 'macro.area_mm2', positive=True) * macros
    if 'area_mm2' in memory and not math.isclose(memory['area_mm2'], macro_area, rel_tol=1e-10):
        raise ValueError('SRAM macro area mismatch')
    peak = _number(memory['reserved_peak_bytes'], 'SRAM.reserved_peak_bytes', integer=True)
    if peak > s['capacity_bytes']:
        raise ValueError('SRAM reservation exceeds logical capacity')
    regions = copy.deepcopy(memory.get('layout', {}))
    intervals = []
    for name, r in regions.items():
        address = _number(r['address'], name + '.address', integer=True)
        size = _number(r['bytes'], name + '.bytes', positive=True, integer=True)
        if address + size > peak:
            raise ValueError('SRAM region outside reserved peak: ' + name)
        intervals.append((address, address + size, name))
    intervals.sort()
    if any(a[1] > b[0] for a, b in zip(intervals, intervals[1:])):
        raise ValueError('overlapping static SRAM regions')

    period = 1e9 / s['clock_hz']
    minimum_cycle = max(_number(macro['read_cycle_ns'], 'macro.read_cycle_ns', positive=True),
                        _number(macro['write_cycle_ns'], 'macro.write_cycle_ns', positive=True))
    if period < minimum_cycle:
        raise ValueError('SRAM period violates calibrated macro minimum')
    bank_GBs = s['banks'] * s['word_bytes'] * s['clock_hz'] / 1e9
    components = []
    components.append(dict(module='SRAM_macros', physical_instances=macros,
        physical_state_bits=physical * 8, area_mm2=macro_area,
        energy_J=None, configured_capacity_bytes=s['capacity_bytes'],
        physical_capacity_bytes=physical, macro_bytes=macro_bytes,
        bank_count=s['banks'], macros_per_bank=macros // s['banks'],
        port='one shared read/write port per bank; depth replication adds no ports',
        clock_hz=s['clock_hz'], period_ns=period, minimum_macro_cycle_ns=minimum_cycle,
        timing_status='period eligibility only; CDC/interface STA not established',
        macro=copy.deepcopy(macro),
        evidence=[CORE + ':SRAM', 'architecture_tlm/' + s['calibration'], 'result.SRAM'],
        exclusions=['wrapper/mux', 'clock tree', 'CDC', 'control/interconnect'],
        accounting='macro internal cost only; do not add SRAM.layout buffers again'))
    for name, throughput in [('mac_array', {'macs_per_core_cycle': cfg['macs_per_cycle']}),
                             ('vector_and_nonlinear', {'vector_lanes': cfg['vector_lanes'],
                                                       'nonlinear_lanes': cfg['nonlinear_lanes']})]:
        components.append(_entry(name, [MODEL + ':mac/vec', REQUESTS],
            configured_throughput=throughput, clock_hz=cfg['core_hz'],
            latency_II_status='configured TLM only; complete format-specific RTL/STA/PPA missing',
            scope='BF16/FP32/W8 formats, resource sharing and implementation need closure'))

    sc = f['mode'] == 'sc'
    for name in ('engines', 'bins', 'samples', 'strata'):
        _number(f[name], 'ffn.' + name, positive=True, integer=True)
    if sc and (shape['hidden_size'] % 64 or shape['intermediate_size'] % 64):
        raise ValueError('SC inventory requires full 64-lane groups')
    bits_per_count = (64 * f['samples']).bit_length()
    counter_per_tile = 64 * 8 * 2 * f['bins'] * bits_per_count
    counter_bits = f['engines'] * counter_per_tile if sc else 0
    observed_counter = result.get('FFN_activity', {}).get('SC_counter_peak_bits', 0)
    if observed_counter != counter_bits:
        raise ValueError('SC counter peak does not match current bit-plane mapping')
    sc_entry = _entry('SC_tiles_and_local_counters', [MODEL + ':matrix_sc', GAPS + ':R01'],
        configured_engines=f['engines'], active_for_path=sc,
        tile_inputs=64, tile_outputs=64, weight_bits=8,
        bins=f['bins'], samples=f['samples'], strata=f['strata'],
        counter_bits_per_value=bits_per_count,
        required_counter_bits_per_tile=counter_per_tile if sc else 0,
        required_counter_bits_total=counter_bits,
        state_status='required local state; physical implementation/clock/area not characterized',
        sample_II_core_cycles=f['sample_II_cycles'],
        frame_core_cycles=f['startup_cycles'] + f['samples'] * f['sample_II_cycles'] + f['drain_cycles'],
        alternative=dict(status='proposed_not_implemented',
            applicability='B4/T32: per-output/per-bin signed20 accumulation',
            required_bits_per_tile=5120, required_bytes_per_tile=640,
            restriction='not selected; 9.6x state-bit ratio is not total area/energy saving'))
    components.append(sc_entry)
    components.append(_entry('SC_weight_retention_and_feed', [MODEL + ':matrix_sc', GAPS + ':R02'],
        active_for_path=sc, required_visible_weight_bytes=4096 * f['engines'] if sc else 0,
        physical_retention_bits=None, macro_output_bits_per_beat=s['banks'] * s['word_bytes'] * 8,
        scope='32 KiB/wave for 8 engines needs a paid and verified output/retention interface',
        warning='SRAM allocation does not prove full-width visibility; no free DFF or CIM assumption'))
    components.append(_entry('encoding_restore_conversion', [MODEL + ':matrix_sc/vec', GAPS + ':R03-R05'],
        configured_vector_resource='shared vector; specialized pipeline not enabled',
        restore_proxy_actions=result.get('actions', {}).get('SC_restore_op', 0),
        scope='72 proxy ops/output at B4 are not 72 independent physical restorers',
        exclusions='do not duplicate restore costs already represented by shared vector actions'))

    rng = result.get('random_interface', {})
    ports = (rng.get('network') or {}).get('ports', {})
    components.append(_entry('random_service', ['architecture_tlm/unified_v6/rng_integrated.py',
        'digital_circuit_simulation_registry/README_ZH.md', 'result.random_interface'],
        backend=rng.get('backend'),
        configured_native_endpoints=len(ports) if ports or rng.get('actual_backend_executed') else None,
        native_port_profiles={name: copy.deepcopy(port.get('profile')) for name, port in ports.items()},
        calibrated_endpoint_area_mm2=rng.get('calibrated_endpoint_area_mm2'),
        conditional_endpoint_energy_J=rng.get('calibrated_endpoint_two_state_energy_J'),
        endpoint_ppa_provenance=copy.deepcopy(rng.get('ppa_provenance')),
        random_stream_SRAM_bytes=rng.get('random_stream_SRAM_bytes'),
        extra_random_FIFO_bytes=rng.get('extra_random_FIFO_bytes'),
        scope='native endpoints only; full random area/energy remain unknown',
        missing=['shared64 frontend', 'threshold/LUT holding', 'seed ingress', 'global distribution'],
        accounting='native endpoint compare/state/control already included in endpoint subtotal'))
    for name, scope in [
        ('attention_auxiliary', 'online softmax, reductions, selector, budget repair, index/histogram, V accumulation'),
        ('SRAM_fabric_DMA_CDC', 'real ports, mux, queues, arbitration, address generation and 100/80MHz crossing'),
        ('DRAM_controller_PHY', 'channel/width/rate, sustained controller throughput and I/O/PHY'),
        ('control_interconnect_clock', 'top-level control, clocks, wires, leakage and idle accounting')]:
        components.append(_entry(name, [REQUESTS, CORE, MODEL], scope=scope,
            status='physical implementation/STA/area/energy not closed'))

    d = shape['hidden_size'] // shape['num_attention_heads']
    ffn_layer = 3 * shape['hidden_size'] * shape['intermediate_size']
    kv_layer = 2 * cfg['context_tokens'] * shape['num_key_value_heads'] * d * 2
    return dict(schema_version=1, scope='P0 resource inventory; not full physical PPA',
        evidence=dict(result_path=result.get('_source_path'), result_config_sha256=result.get('config_sha256'),
            calibration_sha256=result.get('calibration_sha256'), model=copy.deepcopy(cfg.get('model_record'))),
        clocks_hz=dict(core=cfg['core_hz'], sram=s['clock_hz']),
        components=components, SRAM_allocation=dict(regions=regions, reserved_peak_bytes=peak,
            unused_configured_bytes=s['capacity_bytes'] - peak,
            unaddressable_physical_padding_bytes=physical - s['capacity_bytes'],
            extra_capacity_does_not_prove_residency=True),
        SRAM_bandwidth=dict(aggregate_bank_peak_GBs=bank_GBs, fabric_GBs=s['fabric_GBs'],
            ideal_sustained_cap_GBs=min(bank_GBs, s['fabric_GBs']),
            fabric_exceeds_bank_peak=s['fabric_GBs'] > bank_GBs,
            semantics='shared read+write; excludes conflicts/CDC/arbitration'),
        working_set_bytes=dict(ffn_W8_one_layer=ffn_layer,
            ffn_W8_all_layers=ffn_layer * shape['num_hidden_layers'],
            BF16_KV_one_layer_at_context=kv_layer,
            BF16_KV_all_layers_at_context=kv_layer * shape['num_hidden_layers']),
        full_physical_area_mm2=None, full_physical_energy_J=None, area_anchor_A0_mm2=None,
        ranking_eligible=False,
        limitations=['BF16/W8/SC full-core implementation is not characterized',
            'W8 applies to FFN only; other projections and lm_head remain BF16',
            'macro and native endpoint partial anchors do not close total ASIC area',
            'proxy priced_subtotal is intentionally not used as full physical energy'])


def lower_bounds(cfg, shape, result, *, include_fixed_service=True,
                 dram_descriptor_physical_bytes=None):
    """Fixed-traffic bounds; optionally supply ALL burst-rounded descriptors.

    descriptor bytes refer to each distinct DRAM.ranges call after within-call
    burst deduplication, not logical bytes or individual ranges. For legacy Link,
    sum(ceil(descriptor/window))*latency + total/B is exact resource service.
    Without descriptors, ceil(total/window) is only an aggregate lower bound.
    A complete event trace can independently recover exact window service.
    Resource busy includes conservative reservations, and its separate bound
    applies only if that reservation/service contract remains unchanged.
    """
    _validate(cfg, shape, result)
    s, d = cfg['sram'], cfg['dram']
    tokens = cfg['decode_tokens']
    physical_sram = _physical_traffic(result['SRAM']['traffic'], 'SRAM.traffic')
    physical_dram = _physical_traffic(result['DRAM']['traffic'], 'DRAM.traffic')
    b = _number(d['bandwidth_GBs'], 'dram.bandwidth_GBs', positive=True)
    burst = _number(d['burst_bytes'], 'dram.burst_bytes', positive=True, integer=True)
    pending = _number(d['max_pending'], 'dram.max_pending', positive=True, integer=True)
    latency = _number(d['latency_ns'], 'dram.latency_ns')
    if physical_dram % burst:
        raise ValueError('DRAM physical bytes are not burst aligned')
    if physical_sram % s['word_bytes']:
        raise ValueError('SRAM physical bytes are not word aligned')
    resources = dict(sram_fabric=physical_sram / s['fabric_GBs'], dram_data_link=physical_dram / b)
    # At least this many words hit the busiest bank. Drop first-cycle service
    # rather than mislabel a steady-state rate as an exact finite-transfer bound.
    bank_words_min = _ceildiv(physical_sram // s['word_bytes'], s['banks'])
    resources['sram_bank_balanced_minimum'] = max(0, bank_words_min - 1) * 1e9 / s['clock_hz']
    link = dict(backend=d['backend'], aggregate_min_windows=None,
                aggregate_service_lower_bound_ns=None, exact_descriptor_service_ns=None,
                exact_trace_window_service_ns=None, exact_window_count=None,
                note='bounds are resource service, not elapsed time or achievable overlap')
    if d['backend'] == 'link':
        window = burst * pending
        minimum_windows = _ceildiv(physical_dram, window)
        aggregate = physical_dram / b + minimum_windows * latency
        resources['dram_legacy_link_aggregate'] = aggregate
        link.update(window_bytes=window, aggregate_min_windows=minimum_windows,
            aggregate_service_lower_bound_ns=aggregate,
            full_window_effective_GBs=window / (latency + window / b))
        if dram_descriptor_physical_bytes is not None:
            sizes = [_number(x, 'descriptor bytes', integer=True) for x in dram_descriptor_physical_bytes]
            if any(x % burst for x in sizes) or sum(sizes) != physical_dram:
                raise ValueError('descriptor physical bytes must match full burst-aligned traffic')
            windows = sum(_ceildiv(x, window) for x in sizes)
            exact = physical_dram / b + windows * latency
            link.update(exact_descriptor_service_ns=exact, descriptor_count=len(sizes),
                        exact_window_count=windows)
            resources['dram_legacy_link_descriptors'] = exact
        events = result.get('events', [])
        complete = result.get('trace_truncated') is False and result.get('event_count') == len(events)
        if complete:
            windows = [e for e in events if e.get('stage', '').startswith('dram_')
                       and 'dram_dma' in e.get('resources', [])]
            sizes = [_number(e['bytes'], 'trace window bytes', positive=True, integer=True) for e in windows]
            if sum(sizes) != physical_dram or any(x % burst or x > window for x in sizes):
                raise ValueError('complete Link trace does not match physical window traffic')
            exact = sum(latency + x / b for x in sizes)
            if link['exact_window_count'] is not None and link['exact_window_count'] != len(windows):
                raise ValueError('descriptor/trace Link window count mismatch')
            link.update(exact_trace_window_service_ns=exact, exact_window_count=len(windows))
            resources['dram_legacy_link_complete_windows'] = exact
    elif dram_descriptor_physical_bytes is not None:
        raise ValueError('descriptor drain formula applies only to legacy Link')

    busy = {}
    if include_fixed_service:
        busy = {k: _number(v, 'resource_busy_ns.' + k)
                for k, v in result.get('resource_busy_ns', {}).items()}
    fixed = max(busy.values(), default=0)
    traffic_lb = max(resources.values(), default=0)
    combined = max(traffic_lb, fixed)
    elapsed = _number(result['metrics']['elapsed_ns'], 'metrics.elapsed_ns')
    if combined > elapsed + max(1e-6, elapsed * 1e-9):
        raise ValueError('conditional lower bound exceeds recorded elapsed time')
    return dict(schema_version=1, scope='fixed physical traffic / selected service contracts',
        unit='ns for complete run', decode_tokens=tokens,
        physical_bytes=dict(DRAM=physical_dram, SRAM=physical_sram),
        resource_traffic_lower_bounds_ns=resources,
        fixed_traffic_lower_bound_ns=traffic_lb,
        legacy_link=link,
        fixed_service_resource_busy_ns=busy, fixed_service_lower_bound_ns=fixed,
        conditional_lower_bound_ns=combined,
        conditional_lower_bound_ms_per_token=combined / tokens / 1e6,
        elapsed_over_conditional_lower_bound=elapsed / combined if combined else None,
        aggregate_rule='maximum across resources; never sum banks/engines/stages/waits',
        limitations=['not an architecture-independent communication lower bound',
            'fixed busy is the unchanged reservation contract, including blocked/held resources',
            'truncated events cannot establish exact descriptor/window overhead',
            'mapping or buffering changes require new physical traffic and service evidence',
            'ideal resource overlap need not be realizable by dependencies or finite queues'])
