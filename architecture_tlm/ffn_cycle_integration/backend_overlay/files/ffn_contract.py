"""Opt-in PR122 B4 arithmetic and finite per-output scheduling.

The FFN owns encoded-group lifetime across gate/up tiles and waves. This module
reuses PR122 Profile/arithmetic, not its single-tile group-lifetime Adapter.
Result credits include in-flight, queued and downstream-add state. The kernel's
old-state edges are conservative and are not cycle-identical ready/valid RTL.
"""
from dataclasses import asdict, fields, replace
import math
import struct
from types import SimpleNamespace

from .contracts import Buffer, Clock, Resource
from .memory import MemoryRequest
from ..encoding_restore_contract.adapter import Profile
from ..encoding_restore_contract.arithmetic import encode, normalize_counts, restore_bins, add_words

CONTRACT = 'pr122_b4_fused0'


def word(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def number(value):
    return struct.unpack('<f', struct.pack('<I', value))[0]


def profile(config):
    values = config.encoding_restore_profile
    names = {f.name for f in fields(Profile)}
    if not isinstance(values, dict) or set(values) != names:
        raise ValueError('PR122 requires an explicit complete Profile dictionary: '+','.join(sorted(names)))
    result = Profile(**values)
    if result.period_ps != 10000:
        raise ValueError('FFN integration currently binds the existing 10000ps core clock')
    if config.bins != 4 or config.samples not in (16, 32, 64) or config.counter_layout != 'bitplane':
        raise ValueError('PR122 integration requires B4, T16/T32/T64 and input-sign W8 bitplanes')
    if config.restore_rounding != 'rtl_fused0_order':
        raise ValueError('PR122 integration requires explicit restore_rounding=rtl_fused0_order')
    return result


def specs(config, prefix='ffn'):
    p = profile(config)
    api = SimpleNamespace(Clock=Clock, Resource=Resource, Buffer=Buffer)
    resources, buffers = p.specs(api, prefix+'.er')
    # Same physical clock, so there is no fabricated CDC between arithmetic
    # stages. Existing FFN byte credits own the shared encoded group lifetime.
    resources = [replace(r, clock=Clock('core', p.period_ps)) for r in resources
                 if r.name != prefix+'.er.release']
    buffers = [b for b in buffers if b.name != prefix+'.er.encoded_free']
    return resources, buffers


def encode_values(values):
    if not 1 <= len(values) <= 64:
        raise ValueError('one active 1..64-lane group required')
    fields = encode([word(v) for v in values]+[0]*(64-len(values)), frac=23)
    items = [dict(q=fields['q'][i], sign=-1 if fields['input_sign'][i] else 1,
                  scale=math.ldexp(1.0, fields['top_exp']-2*fields['bins'][i]),
                  bin=fields['bins'][i], full_one=bool(fields['true_one'][i]))
             for i in range(len(values))]
    return items, fields['top_exp']


def schedule_tile(*, add, state, config, prefix, label, key, tile_key, nr,
                  previous, read_previous, partial_address, count_bytes,
                  values, row_start):
    """Restore every output once; release tile state after all ordered adds.

    Adds are appended on actual restore completion, in each lane's completion
    order. Chaining them in registration order could deadlock a full result
    queue when a lexically earlier or late producer changes acceptance order.
    """
    p = profile(config)
    scratch_bytes = nr*12  # old partial, new partial, pending packed write
    if scratch_bytes > config.restore_capacity_bytes:
        raise ValueError('tile restore scratch exceeds configured capacity')
    reserve = add(label+'.restore_reserve', 'control', deps=(previous,),
                  inputs={prefix+'.restore':scratch_bytes})
    deps = [reserve]
    readp = None
    if read_previous is not None:
        readp = add(label+'.partial_read', 'sram', deps=(read_previous, reserve),
                    memory=MemoryRequest(partial_address, nr*4), actions={'partial_read_bytes':nr*4})
        deps.append(readp)
    def prepare(kernel, operation):
        raw = state['counters'][tile_key]
        flat = [v for row in raw for b in row for rail in b for v in rail]
        old = list(struct.unpack('<'+'f'*nr, kernel.memory_reads[readp])) if readp else [0.0]*nr
        state['restore_intermediates'][tile_key] = dict(old=old, total=[0.0]*nr,
            counter_peak=max(flat), nonzero_slots=sum(v!=0 for v in flat), integer_peak=0)
    prepared = add(label+'.restore_prepare', 'control', deps=tuple(deps), on_complete=prepare)
    er = state['encoding_restore']
    adds = []
    for row in range(nr):
        lane = row % p.restore_lanes
        resource = f'{prefix}.er.restore{lane}'
        suffix = label+f'.er_row{row:03d}'
        restore_id = prefix+'.'+suffix+'.restore'
        add_id = prefix+'.'+suffix+'.add'
        adds.append(add_id)
        def restored(kernel, operation, row=row, lane=lane, resource=resource,
                     suffix=suffix, restore_id=restore_id, add_id=add_id):
            integers = normalize_counts(state['counters'][tile_key][row],
                representation='input_sign_twos_complement', count_width=config.counter_width,
                samples=config.samples)
            scale = state['resident_weights'][tile_key][1]
            result = restore_bins(integers, top_exp=er['top_exp'][key],
                                  weight_scale_word=word(scale), samples=config.samples)
            er['results'][restore_id] = result
            er['peak_live_results'] = max(er['peak_live_results'], len(er['results']))
            scratch = state['restore_intermediates'][tile_key]
            scratch['integer_peak'] = max(scratch['integer_peak'], *(abs(v) for v in integers))
            dependencies = (restore_id,)
            if lane in er['last_lane_add']:
                dependencies += (er['last_lane_add'][lane],)
            def accumulated(k, op):
                scratch['total'][row] = number(add_words(word(scratch['old'][row]), er['results'].pop(restore_id)))
            add(suffix+'.add', prefix+'.er.add', deps=dependencies,
                inputs={resource+'.ready':1}, outputs={resource+'.free':1},
                actions={'cross_k_fp32_add':1}, on_complete=accumulated,
                metadata={'row':row_start+row, 'rounding':'separate RNE FP32 cross-k add'})
            er['last_lane_add'][lane] = add_id
        add(suffix+'.restore', resource, deps=(prepared,),
            inputs={resource+'.free':1}, outputs={resource+'.ready':1},
            actions={'complete_restore_output_b4':1}, on_complete=restored,
            metadata={'row':row_start+row, 'bins':4, 'count_representation':'input_sign_twos_complement',
                      'rounding':'PR122 FUSED0', 'timing':'conditional Profile; not STA or RTL handshake equivalence'})
    def finished(kernel, operation):
        scratch = state['restore_intermediates'].pop(tile_key)
        state['counters'].pop(tile_key)
        state['resident_weights'].pop(tile_key)
        values[row_start:row_start+nr] = scratch['total']
        add(label+'.partial_write', 'sram', deps=(operation.id,),
            memory=MemoryRequest(partial_address, nr*4, write=True,
                                 data=struct.pack('<'+'f'*nr, *scratch['total'])),
            outputs={prefix+'.restore':scratch_bytes},
            actions={'partial_write_bytes':nr*4})
        state['tile_receipts'].append(dict(tile=label, counter_peak=scratch['counter_peak'],
            nonzero_counter_slots=scratch['nonzero_slots'], integer_equivalent_peak=scratch['integer_peak'],
            counter_layout=config.counter_layout, restored_rows=nr, complete_ps=kernel.now_ps,
            encoding_restore_contract=CONTRACT))
    return add(label+'.restore', 'control', deps=tuple(adds), on_complete=finished,
               outputs={prefix+'.counters':count_bytes},
               metadata={'bookkeeping':'tile join only; scalar restores and adds already charged'})


def initial_state(config):
    p = profile(config)
    return dict(contract=CONTRACT, profile=asdict(p), top_exp={}, results={}, last_lane_add={},
                peak_live_results=0, result_slot_bytes=p.restore_lanes*p.restore_depth*8,
                slot_boundary='one FP32 result plus declared 32-bit transaction identity per reserved slot',
                timing='conditional old-state kernel Profile; not cycle-identical ready/valid RTL or STA')
