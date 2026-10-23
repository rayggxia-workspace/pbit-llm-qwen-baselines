"""Short projection consumer of the existing feed, restore and cycle contracts.

Each wave is one input group and all explicitly configured output tiles. This
module owns no kernel, full FFN, encoder/RNG timing, upstream DRAM or PPA model.
"""
from collections import deque
from dataclasses import asdict, dataclass
import copy
import hashlib
import json
import math


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Config:
    groups: int = 4
    tiles: int = 8
    rows_per_tile: int = 64
    samples: int = 32
    weight_slots: int = 1
    counter_slots: int = 1
    counter_read_bytes: int = 16
    counter_read_ports: int = 1
    staging_packets: int = 4
    partial_write_slots: int = 4
    partial_word_bytes: int = 16
    packet_metadata_bytes: int = 16
    w8_macs_per_cycle: int = 512
    w8_scale_latency: int = 2
    w8_scale_ii: int = 1
    profile: object = None
    feed_overrides: object = None
    sink_start_ps: int = 0

    def validate(self):
        for key, value in vars(self).items():
            if key in ('profile', 'feed_overrides'):
                continue
            if type(value) is not int or value < (0 if key == 'sink_start_ps' else 1):
                raise ValueError('invalid integer configuration: '+key)
        if self.weight_slots not in (1, 2) or self.counter_slots not in (1, 2):
            raise ValueError('this bounded study supports one or two wave slots')
        if not 1 <= self.rows_per_tile <= 64 or self.samples != 32:
            raise ValueError('full 64-input B4/T32 contract and at most64 output rows/tile required')
        if self.counter_read_bytes not in (16, 64, 128):
            raise ValueError('counter port width must be16,64 or128 bytes')
        if self.packet_metadata_bytes != 16 or self.partial_word_bytes != 16:
            raise ValueError('explicit16B metadata and conservative16B partial transactions required')
        if self.w8_macs_per_cycle != 512:
            raise ValueError('fixed512-MAC conditional W8 reference required')


def _shift_preload(events, offset):
    """Whole trace translation preserves both clock phases and cycle labels."""
    if offset % 50000:
        raise ValueError('feed offset must align both100MHz and80MHz clocks')
    shifted = []
    for original in events:
        if original['kind'].startswith('sample_') or original['kind'] == 'consume_resident':
            continue
        event = dict(original)
        for key in ('t_ps', 'start_ps', 'end_ps'):
            if key in event:
                event[key] += offset
        if 'sram_cycle' in event:
            event['sram_cycle'] += offset//12500
        for key in ('core_cycle', 'start_core_cycle', 'end_core_cycle'):
            if key in event:
                event[key] += offset//10000
        shifted.append(event)
    return shifted


def execute(deps, fixture, cfg=None, method='sc', mode='event'):
    cfg = Config() if cfg is None else (Config(**cfg) if isinstance(cfg, dict) else cfg)
    cfg.validate()
    if method not in ('sc', 'w8') or mode not in ('cycle', 'event'):
        raise ValueError('unknown method/execution mode')
    for key in ('groups', 'tiles', 'rows_per_tile', 'samples'):
        if fixture[key] != getattr(cfg, key):
            raise ValueError('fixture/config mismatch: '+key)
    rows = cfg.tiles*cfg.rows_per_tile
    if fixture['rows'] != rows or fixture['count_width'] != 12 or fixture['representation'] != 'input_sign_twos_complement':
        raise ValueError('explicit12bit input-sign/twos-complement count packets required')
    api = deps.api
    profile = (deps.Profile() if cfg.profile is None else
               deps.Profile(**cfg.profile) if isinstance(cfg.profile, dict) else cfg.profile)
    if profile.period_ps != 10000:
        raise ValueError('fixed100MHz consumer clock required')
    overrides = dict(cfg.feed_overrides or {})
    forbidden = {'mode', 'inputs', 'outputs', 'tiles', 'samples', 'bins', 'core_hz', 'sram_hz', 'word_bytes',
                 'sample_ii_core_cycles', 'resident_sample_core_cycles'} & overrides.keys()
    if forbidden:
        raise ValueError('fixed feed dimensions/clocks overridden: '+str(sorted(forbidden)))
    feed_cfg = deps.feed.candidate_config('resident', inputs=64, outputs=cfg.rows_per_tile,
        tiles=cfg.tiles, samples=cfg.samples, **overrides)
    deps.feed._check_config(feed_cfg)
    fabric_ps = (cfg.partial_word_bytes*10**12+feed_cfg.fabric_bytes_per_second-1)//feed_cfg.fabric_bytes_per_second
    partial_raw_ps = feed_cfg.read_latency_sram_cycles*12500+feed_cfg.cdc_delay_ps+fabric_ps
    partial_cycles = (partial_raw_ps+12499)//12500
    partial_io_contract = dict(transaction_bytes=cfg.partial_word_bytes,
        sram_read_latency_cycles=feed_cfg.read_latency_sram_cycles, sram_period_ps=12500,
        read_latency_ps=feed_cfg.read_latency_sram_cycles*12500, cdc_delay_ps=feed_cfg.cdc_delay_ps,
        fabric_bytes_per_second=feed_cfg.fabric_bytes_per_second, fabric_transfer_ps=fabric_ps,
        unrounded_service_ps=partial_raw_ps, service_sram_cycles=partial_cycles,
        service_ps=partial_cycles*12500, rounding_guard_ps=partial_cycles*12500-partial_raw_ps,
        shared_lock_full_service=True,
        scope='symmetric conservative read/write endpoint; write timing is assumed, not PR120 native write validation')
    partial_base = math.ceil(cfg.groups*feed_cfg.wave_bytes/16)*16
    partial_physical_bytes = math.ceil(rows*4/16)*16
    if partial_base+partial_physical_bytes > feed_cfg.sram_capacity_bytes:
        raise ValueError('distinct immutable weight waves plus partial SRAM exceed capacity')
    templates = [deps.feed.simulate(feed_cfg, [group*feed_cfg.wave_bytes+address
                  for address in range(0, feed_cfg.wave_bytes, feed_cfg.word_bytes)])
                 for group in range(cfg.groups)]
    preload_ps = [max(event['t_ps'] for event in template['events'] if event['kind'] == 'hold_write')
                  for template in templates]
    feed_cycles = [math.ceil(duration/50000) for duration in preload_ps]
    # Address-bearing data store at the same boundary as the imported trace.
    # Upstream fill is excluded; timed callbacks verify the bytes actually read.
    sram_bytes = bytearray(feed_cfg.sram_capacity_bytes)
    weight_payloads, resident_payloads = [], {}
    for group in range(cfg.groups):
        payload = bytes(value & 255 for weights in fixture['inputs'][group]['weights'] for value in weights)
        if len(payload) != feed_cfg.wave_bytes:
            raise ValueError('fixture weight payload does not match feed wave')
        weight_payloads.append(payload)
        base = group*feed_cfg.wave_bytes
        sram_bytes[base:base+len(payload)] = payload
    feed = templates[0]
    core, sram, common = api.Clock('consumer_core', 10000), api.Clock('consumer_sram', 12500), api.Clock('feed_common', 50000)
    Resource, Buffer, Operation = api.Resource, api.Buffer, api.Operation
    resources = [Resource('feed', common, feed_cycles[0]), Resource('sample_or_mac', core, 1),
                 Resource('control', core, 1, capacity=4),
                 Resource('counter_read', core, 1, instances=cfg.counter_read_ports),
                 Resource('partial_io', sram, partial_cycles),
                 Resource('add', core, profile.add_latency, ii_cycles=profile.add_ii,
                          capacity=profile.add_capacity)]
    buffers = [Buffer('fabric_free', 1, 1, 'exclusive SRAM/fabric service'),
               Buffer('weight_free', cfg.weight_slots, cfg.weight_slots, 'complete weight wave'),
               Buffer('counter_free', cfg.counter_slots, cfg.counter_slots, 'complete producer-result wave'),
               Buffer('staging_free', cfg.staging_packets, cfg.staging_packets, 'complete copied row packet'),
               Buffer('write_free', cfg.partial_write_slots, cfg.partial_write_slots, 'pending FP32 partial write')]
    for lane in range(profile.restore_lanes):
        resources.append(Resource('restore'+str(lane), core,
            profile.restore_latency if method == 'sc' else cfg.w8_scale_latency,
            ii_cycles=profile.restore_ii if method == 'sc' else cfg.w8_scale_ii,
            capacity=profile.restore_depth))
        buffers += [Buffer('out_free'+str(lane), profile.restore_depth, profile.restore_depth,
                           'result plus old partial; held through add completion')]
    kernel = api.Kernel(resources, buffers)
    counted, staged, restored, old_values, pending_writes = {}, {}, {}, {}, {}
    partials = [0]*rows
    receipts, feed_receipts, partial_receipts = [], [], []
    next_row, read_done = {}, {}
    lane_queue = [deque() for _ in range(profile.restore_lanes)]
    last_lane_add = {}
    all_final_writes = []

    def op(name, resource, **kwargs):
        kwargs.setdefault('cdc_cycles', 1)
        kernel.add(Operation(name, resource, **kwargs))
        return name

    def row_name(group, row):
        return 'k%04d.r%05d' % (group, row)

    def attach_row(group):
        row = next_row[group]
        if row >= rows:
            return
        next_row[group] += 1
        name = row_name(group, row)
        lane = row % profile.restore_lanes
        packet_bytes = (96 if method == 'sc' else 4)+cfg.packet_metadata_bytes
        beats = math.ceil(packet_bytes/cfg.counter_read_bytes)
        read_id = name+'.counter_read'

        def read_complete(k, operation):
            # A real, paid copy frees the counter bank independently of restore.
            staged[name] = copy.deepcopy(counted[group][row])
            read_done[group].append(operation.id)
            if len(read_done[group]) == rows:
                def release(k2, operation2):
                    counted.pop(group)
                op('k%04d.counter_release' % group, 'control', deps=tuple(read_done[group]),
                   outputs={'counter_free': 1}, on_complete=release)
            attach_restore(group, row, lane, name, operation.id)
            attach_row(group)

        op(read_id, 'counter_read', deps=('k%04d.produce' % group,),
           inputs={'staging_free': 1}, latency_cycles=beats, ii_cycles=beats,
           actions={'local_packet_read_bytes': packet_bytes,
                    'local_packet_physical_bytes': beats*cfg.counter_read_bytes,
                    'counter_read_beats': beats},
           metadata={'group': group, 'row': row, 'payload_bytes': packet_bytes,
                     'port_bytes': cfg.counter_read_bytes}, on_complete=read_complete)

    def attach_restore(group, row, lane, name, read_id):
        stage_id, add_id, write_id = name+'.restore', name+'.add', name+'.partial_write'
        lane_name = 'restore'+str(lane)

        def complete_restore(k, operation):
            packet = staged.pop(name)
            if method == 'sc':
                bins = deps.restore.normalize_counts(packet['counts'],
                    representation=fixture['representation'], count_width=fixture['count_width'],
                    samples=cfg.samples)
                word = deps.restore.restore_bins(bins, top_exp=packet['top_exp'],
                    weight_scale_word=packet['weight_scale_word'], samples=cfg.samples)
            else:
                word = deps.restore._oracle().mul(packet['unscaled'], packet['weight_scale_word'])
            expected = fixture['sc_partials' if method == 'sc' else 'w8_partials'][group][row]
            if word != expected:
                raise AssertionError('restore/scale numerical mismatch')
            restored[name] = word
            lane_queue[lane].append(name)
            receipts.append(dict(group=group, row=row, lane=lane, word=word,
                                 counter_read=read_id, restore=operation.id, restore_done_ps=k.now_ps))

        op(stage_id, lane_name, deps=(read_id,), inputs={'out_free'+str(lane): 1},
           outputs={'staging_free': 1}, on_complete=complete_restore,
           actions={'complete_b4_restore' if method == 'sc' else 'w8_fp32_scale': 1},
           metadata={'group': group, 'row': row, 'lane': lane,
                     'unit': 'one full four-bin output' if method == 'sc' else 'one FP32 scale multiply'})
        dependencies = [stage_id]
        if group:
            previous = row_name(group-1, row)+'.partial_write'
            partial_read = name+'.partial_read'
            def read_partial(k, operation):
                address = partial_base+row*4
                old_values[name] = int.from_bytes(sram_bytes[address:address+4], 'little')
                if old_values[name] != partials[row]:
                    raise AssertionError('partial SRAM bytes disagree with ordered accumulator')
                physical = address//16*16
                beat = bytes(sram_bytes[physical:physical+16]).hex()
                partial_receipts.append(dict(kind='read', group=group, row=row,
                    operation=operation.id, completion_ps=k.now_ps, address=address,
                    physical_address=physical, byte_enable=15 << (address % 16),
                    word=old_values[name], before_hex=beat, after_hex=beat))
            op(partial_read, 'partial_io', deps=(stage_id, previous),
               inputs={'fabric_free': 1}, outputs={'fabric_free': 1}, on_complete=read_partial,
               actions={'partial_read_logical_bytes': 4, 'partial_read_physical_bytes': cfg.partial_word_bytes},
               metadata={'group': group, 'row': row, 'address': partial_base+row*4,
                         'physical_address': partial_base+(row*4//16)*16,
                         'byte_enable': 15 << (row*4 % 16),
                         'conservative_transaction_bytes': cfg.partial_word_bytes})
            dependencies.append(partial_read)
        if lane in last_lane_add:
            dependencies.append(last_lane_add[lane])
        last_lane_add[lane] = add_id

        def add_complete(k, operation):
            if not lane_queue[lane] or lane_queue[lane].popleft() != name:
                raise AssertionError('output FIFO identity mismatch')
            before = old_values.pop(name) if group else 0
            pending_writes[name] = deps.restore.add_words(before, restored.pop(name))

        op(add_id, 'add', deps=tuple(dict.fromkeys(dependencies)),
           inputs={'write_free': 1}, outputs={'out_free'+str(lane): 1},
           earliest_ps=cfg.sink_start_ps, on_complete=add_complete,
           actions={'cross_k_fp32_add': 1}, metadata={'group': group, 'row': row, 'lane': lane})

        def write_complete(k, operation):
            partials[row] = pending_writes.pop(name)
            address = partial_base+row*4
            physical, lane = address//16*16, address % 16
            before = bytes(sram_bytes[physical:physical+16])
            replacement = partials[row].to_bytes(4, 'little')
            mask = 15 << lane
            after = bytes(replacement[index-lane] if mask & (1 << index) else before[index]
                          for index in range(16))
            sram_bytes[physical:physical+16] = after
            partial_receipts.append(dict(kind='write', group=group, row=row,
                operation=operation.id, completion_ps=k.now_ps, address=address,
                physical_address=physical, byte_enable=mask, word=partials[row],
                before_hex=before.hex(), after_hex=after.hex()))

        op(write_id, 'partial_io', deps=(add_id,), inputs={'fabric_free': 1},
           outputs={'fabric_free': 1, 'write_free': 1}, on_complete=write_complete,
           actions={'partial_write_logical_bytes': 4, 'partial_write_physical_bytes': cfg.partial_word_bytes},
           metadata={'group': group, 'row': row, 'address': partial_base+row*4,
                     'physical_address': partial_base+(row*4//16)*16,
                     'byte_enable': 15 << (row*4 % 16),
                     'conservative_transaction_bytes': cfg.partial_word_bytes})
        if group == cfg.groups-1:
            all_final_writes.append(write_id)

    for group in range(cfg.groups):
        prefix = 'k%04d' % group
        feed_id, produce_id = prefix+'.feed', prefix+'.produce'
        def loaded(k, operation, group=group):
            resident_payloads[group] = b''.join(bytes(sram_bytes[address:address+feed_cfg.word_bytes])
                                                for address in templates[group]['addresses'])
            if resident_payloads[group] != weight_payloads[group]:
                raise AssertionError('weight source address/payload mismatch')
        op(feed_id, 'feed', inputs={'fabric_free': 1, 'weight_free': 1}, outputs={'fabric_free': 1},
           latency_cycles=feed_cycles[group], on_complete=loaded,
           actions={'weight_preload_bytes': feed_cfg.wave_bytes,
                    'weight_read_transactions': feed_cfg.word_count},
           metadata={'group': group, 'template_sha256': digest(templates[group]), 'actual_preload_ps': preload_ps[group],
                     'weight_base': group*feed_cfg.wave_bytes,
                     'weight_payload_sha256': hashlib.sha256(weight_payloads[group]).hexdigest(),
                     'common_edge_guard_ps': feed_cycles[group]*50000-preload_ps[group]})

        def produced(k, operation, group=group):
            if resident_payloads.pop(group) != weight_payloads[group]:
                raise AssertionError('consumer did not retain its own complete weight wave')
            if method == 'sc':
                counted[group] = copy.deepcopy(fixture['packets'][group])
            else:
                counted[group] = [dict(unscaled=word,
                    weight_scale_word=fixture['packets'][group][row]['weight_scale_word'])
                    for row, word in enumerate(fixture['w8_unscaled'][group])]
            next_row[group], read_done[group] = 0, []
            for _ in range(min(cfg.counter_read_ports, rows)):
                attach_row(group)

        # W8 preserves the fixture's64 serial non-FMA input dependencies per
        # output;512 MACs/cycle is a conditional aggregate rate, never64/512ns.
        duration = cfg.samples if method == 'sc' else max(64, math.ceil(rows*64/cfg.w8_macs_per_cycle))
        op(produce_id, 'sample_or_mac', deps=(feed_id,), inputs={'counter_free': 1},
           outputs={'weight_free': 1}, latency_cycles=duration, ii_cycles=duration,
           on_complete=produced,
           actions=({'sc_accepted_samples': cfg.samples, 'sc_weight_input_trials': rows*64*cfg.samples}
                    if method == 'sc' else {'w8_mac': rows*64}),
           metadata={'group': group, 'rows': rows, 'samples': cfg.samples if method == 'sc' else 0})

    result = kernel.run(mode)
    expected = fixture['expected_sc' if method == 'sc' else 'expected_w8']
    if partials != expected or len(all_final_writes) != rows:
        raise AssertionError('projection output/cross-k coverage mismatch')
    if counted or staged or restored or old_values or pending_writes or resident_payloads or any(lane_queue):
        raise AssertionError('unreleased data payloads')
    if result.buffer_final != {name: spec.initial for name, spec in kernel.buffer_specs.items()}:
        raise AssertionError('finite credits not returned')
    # Replay absolute feed transactions and actual accepted SC sample windows.
    for group in range(cfg.groups):
        prefix = 'k%04d' % group
        start = result.accepted_ps[prefix+'.feed']
        template = templates[group]
        shifted = _shift_preload(template['events'], start)
        producer_start = result.accepted_ps[prefix+'.produce']
        validated = None
        if method == 'sc':
            tokens = ['k%d.sample%d' % (group, index) for index in range(cfg.samples)]
            for index, token in enumerate(tokens):
                begin = producer_start+index*10000
                end = begin+10000
                shifted.extend([
                    dict(kind='sample_begin', t_ps=begin, sample=index, token=token,
                         core_cycle=begin//10000, sequence_index=index, held_sample_bits=feed_cfg.sample_state_bits),
                    dict(kind='consume_resident', t_ps=end, sample=index, token=token,
                         start_ps=begin, start_core_cycle=begin//10000, end_core_cycle=end//10000,
                         nbytes=feed_cfg.wave_bytes),
                    dict(kind='sample_end', t_ps=end, sample=index, token=token, consumed_bytes=feed_cfg.wave_bytes)])
            shifted.sort(key=lambda event: (event['t_ps'], deps.feed._RANK[event['kind']], event.get('read_id', -1)))
            validated = deps.feed.validate(feed_cfg, shifted, template['addresses'], tokens)
        feed_receipts.append(dict(group=group, offset_ps=start, last_hold_write_ps=start+preload_ps[group],
            weight_base=group*feed_cfg.wave_bytes, template_sha256=digest(template),
            weight_payload_sha256=hashlib.sha256(weight_payloads[group]).hexdigest(),
            exclusive_end_ps=result.completion_ps[prefix+'.feed'], consumer_start_ps=producer_start,
            consumer_end_ps=result.completion_ps[prefix+'.produce'], shifted_trace_sha256=digest(shifted),
            replay_validation=validated, scope='complete imported feed+actualSC stream' if method == 'sc' else 'same imported preload; deterministic W8 consumer'))
    used = {name: spec.initial for name, spec in kernel.buffer_specs.items()}
    peak = {name: 0 for name in used}
    for event in result.trace:
        if event['kind'] == 'accept':
            for name, amount in event['inputs'].items():
                used[name] -= amount
        elif event['kind'] == 'complete':
            for name, amount in event['outputs'].items():
                used[name] += amount
        for name, spec in kernel.buffer_specs.items():
            peak[name] = max(peak[name], spec.initial-used[name])
    payload = (96 if method == 'sc' else 4)+cfg.packet_metadata_bytes
    storage = dict(weight_hold_bytes=cfg.weight_slots*feed_cfg.local_weight_hold_bytes,
        counter_allocated_bytes=cfg.counter_slots*rows*(96+cfg.packet_metadata_bytes),
        producer_payload_bytes_per_slot=rows*payload,
        w8_accumulator_allocated_bytes=rows*4,
        counter_payload_bytes_per_output=96 if method == 'sc' else 4,
        metadata_bytes_per_output=cfg.packet_metadata_bytes,
        staging_allocated_bytes=cfg.staging_packets*(96+cfg.packet_metadata_bytes),
        staging_payload_bytes_per_packet=payload,
        output_slots=profile.restore_lanes*profile.restore_depth,
        output_slot_bytes=8+cfg.packet_metadata_bytes,
        pending_partial_write_bytes=cfg.partial_write_slots*(4+cfg.packet_metadata_bytes),
        partial_sram_bytes=partial_physical_bytes, partial_logical_bytes=rows*4,
        sram_layout=dict(weight_wave_bases=[group*feed_cfg.wave_bytes for group in range(cfg.groups)],
                         weight_wave_bytes=feed_cfg.wave_bytes, partial_base=partial_base,
                         reserved_bytes=partial_base+partial_physical_bytes,
                         capacity_bytes=feed_cfg.sram_capacity_bytes),
        metadata_layout='group32,row32,top_exp16,weight_scale32,samples8,representation8',
        uncharacterized_restore_pipeline_internal_bits=None,
        feed_response_bytes=feed_cfg.response_buffer_bytes,
        sample_hold_bits=feed_cfg.sample_hold_capacity_bits,
        credit_peak_used=peak,
        allocation_policy='same provisioned max-bitplane budgets for both methods; W8 unused bytes remain provisioned')
    return dict(result=result, kernel=kernel, output_words=partials,
        metrics=dict(finish_ps=result.finish_ps, latency_ns=result.finish_ps/1000,
                     area_mm2=None, energy_J=None, full_model_quality=None),
        storage=storage, partial_io_contract=partial_io_contract,
        feed_template=feed, feed_templates=templates, feed_receipts=feed_receipts,
        row_receipts=receipts, partial_receipts=partial_receipts,
        final_sram_sha256=hashlib.sha256(sram_bytes).hexdigest(),
        config={**asdict(cfg), 'profile': asdict(profile)}, method=method,
        source_boundary=['short multi-wave projection, not fullFFN/decode or an Issue123 integration',
            'feedSRAM is already loaded; upstreamDRAM and encoder/RNG generation excluded',
            'distinct weight-wave SRAM addresses and separate aligned partial storage; callbacks check actual bytes',
            'partial16B transactions assume byte-enable preserves neighbouring values; not new SRAM RTL',
            'partial read/write service charges SRAM read latency+configured CDC+fabric transfer, rounded toSRAMcycles; symmetric write timing is assumed',
            'encoded exponent and scale arrive at the explicit16B/row metadata boundary; upstream delivery excluded',
            'feed and16B partial transactions share an exclusivefabric token; no free overlap',
            'fixturecount producer is frozen numeric evidence; SC executes declaredTcycle service',
            'conditional512-MAC W8 service retains one4B accumulator per row and64 serial input steps',
            'localcounter words copied into paidstaging before bankrelease',
            'all timings conditional; profile latency/II do not establish STA/PPA'])
