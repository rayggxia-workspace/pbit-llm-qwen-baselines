"""Audit the archived FFN loop, isolating SC service from memory/RNG overhead.

The function excerpt is trusted repository source; never supply untrusted Python.
This is an accounting replay, not an RTL/LLM/DRAM simulation.
"""
import argparse
import ast
from collections import defaultdict
import json
import math
from pathlib import Path
from types import SimpleNamespace


def formula(inp, out, tile, engines, samples, frequency):
    if min(inp, out, tile, engines, samples, frequency) <= 0 or inp % tile or out % tile:
        raise ValueError('positive and tile-aligned dimensions required')
    blocks = inp // tile
    groups = out // tile
    waves = blocks * math.ceil(groups / engines)
    frames = blocks * groups
    return dict(input_blocks=blocks, output_tiles=groups, waves=waves, frames=frames,
        active_slot_fraction=frames/(engines*waves),
        core_service_ns=waves*(samples+1)/frequency*1e9,
        partial_read_write_bytes=blocks*out*4*2,
        int8_weight_payload_bytes=inp*out)


class Probe:
    def __init__(self, cfg):
        self.cfg = cfg
        self.engines = cfg['sc_engines']
        self.period = 1e9/cfg['frequency_hz']
        self.other_peak = self.tile_serial = 0
        self.raw_bits = self.sc_compute_ns = self.rng_service_ns = 0
        self.sc_active_engine_ns = self.sc_wait_engine_ns = 0
        self.actions = defaultdict(int)
        self.energy = defaultdict(float)
        self.traffic = defaultdict(int)
        self.body_W = self.front_W = 0
        self.weight_bytes = 0
        self.partial_bytes = 0
        self.vector_calls = []
        self.weights = SimpleNamespace(tile_ready=self.load, release=lambda t: None)
        self.rng_hierarchy = SimpleNamespace(begin_tile=lambda t, identity: t,
            restore_wave=lambda t: t, input_wave=lambda t, n, T: (t+T*self.period, T*self.period),
            end_tile=lambda: None)
        self.work_mem = SimpleNamespace(transfer=self.transfer)

    def vectors(self, ready, ops=0, nonlinear=0):
        self.vector_calls.append((ops, nonlinear))
        return ready  # Deliberately isolate SC core service, not all FFN time.

    def load(self, name, address, size, ready, tiles):
        self.weight_bytes += size
        return ready

    def transfer(self, ready, address, size, write, label):
        self.partial_bytes += size
        return ready


def audit(evidence, excerpt):
    tree = ast.parse(excerpt)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef) or tree.body[0].name != 'stochastic_matrix':
        raise ValueError('expected one archived stochastic_matrix function')
    scope = {'math': math}
    exec(compile(tree, '<archived-project-function>', 'exec'), scope)
    # The unchanged project function is replayed with zero-cost I/O stubs.
    function = scope['stochastic_matrix']
    cfg = evidence['config']; shape = evidence['shape']
    h = shape['hidden_size']; m = shape['intermediate_size']; layers = shape['num_hidden_layers']
    stages = {}
    for name, inp, out in [('gu', h, 2*m), ('down', m, h)]:
        expected = formula(inp, out, 64, cfg['sc_engines'], cfg['samples'], cfg['frequency_hz'])
        probe = Probe(cfg)
        end = function(probe, name, inp, out, 0)
        assert math.isclose(end, expected['core_service_ns'], abs_tol=1e-4)
        assert probe.actions['sc_tile_frames'] == expected['frames']
        assert probe.partial_bytes == expected['partial_read_write_bytes']
        assert probe.weight_bytes == expected['int8_weight_payload_bytes']
        expected['replay_verified'] = True
        expected['encode_vector_ops'] = sum(x[0] for x in probe.vector_calls[:1]) * expected['input_blocks']
        expected['finalize_vector_ops'] = out*cfg['sc_cost']['finalize_vector_ops_per_partial']*expected['input_blocks']
        stages[name] = expected
    total_frames = sum(s['frames'] for s in stages.values())
    total_waves = sum(s['waves'] for s in stages.values())
    d = cfg['digital']
    swiglu_cycles = math.ceil(2*m/d['vector_ops_per_cycle'])+math.ceil(m/d['nonlinear_ops_per_cycle'])
    swiglu_bytes = 2*m*d['vector_interface_bytes_per_op']+m*d['nonlinear_interface_bytes_per_op']
    hist = evidence['historical']; n = cfg['decode_tokens']
    history_ms = {k: v/n/1e6 for k,v in hist['time_ns'].items() if k.startswith('FFN_')}
    history_ffn_ms = sum(history_ms.values())
    token_core_ms = sum(s['core_service_ns'] for s in stages.values())*layers/1e6
    assert hist['actions']['sc_tile_frames'] == total_frames*layers*n
    assert hist['partial_bytes'] == sum(s['partial_read_write_bytes'] for s in stages.values())*layers*n
    assert history_ffn_ms >= token_core_ms
    scratch_by_origin = dict(
        explicit_partial_RW=sum(s['partial_read_write_bytes'] for s in stages.values()),
        vector_encode_interface=(h+m)*cfg['sc_cost']['input_encode_vector_ops']*d['vector_interface_bytes_per_op'],
        vector_finalize_interface=sum(s['finalize_vector_ops'] for s in stages.values())*d['vector_interface_bytes_per_op'],
        swiglu_interface=swiglu_bytes)
    return dict(kind='source loop accounting + previous TLM timing extraction; NOT chip measurements or new PPL',
        source_files=evidence['sources'],historical_result_sha256=hist['sha256'],shape=dict(h=h,m=m,layers=layers),
        frequency_hz=cfg['frequency_hz'],samples=cfg['samples'],engines=cfg['sc_engines'],
        per_layer=stages,token_core_service_ms=token_core_ms,
        all_frames_per_token=total_frames*layers,active_slot_fraction=total_frames/(cfg['sc_engines']*total_waves),
        unconstrained_ideal_wave_packing=dict(waves=math.ceil(total_frames/cfg['sc_engines']),
            current_waves=total_waves,max_service_reduction_fraction=1-math.ceil(total_frames/cfg['sc_engines'])/total_waves,
            warning='requires different input/weight/reduction routing; not achievable for free under current same-input broadcast contract'),
        swiglu_proxy_compute_ms_per_token=swiglu_cycles*1e3/cfg['frequency_hz']*layers,
        swiglu_proxy_interface_bytes_per_layer=swiglu_bytes,
        scratch_interface_bytes_per_layer=scratch_by_origin,
        scratch_interface_MiB_per_token=sum(scratch_by_origin.values())*layers/2**20,
        int8_weight_payload_MiB_per_token=total_frames*4096*layers/2**20,
        historical_ms_per_token=history_ms,historical_ffn_ms_per_token=history_ffn_ms,
        historical_extra_beyond_SC_core_ms=history_ffn_ms-token_core_ms,
        historical_swiglu_fraction_of_FFN=history_ms['FFN_SwiGLU']/history_ffn_ms,
        limitations=['zero-cost stub replay is a service-count check, not a faster architecture',
            'vector conversion/arithmetic costs remain proxies and are not separate BF16/INT8 RTL costs',
            'scratch traffic is modeled interface traffic; logical tensors must not be double counted as extra traffic',
            'current macro power does not validate the parallel resident-weight physical interface',
            'no new runtime, memory scheduler, nonlinear hardware, PPL, or foundry simulation'])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--excerpt', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise SystemExit('Refusing to overwrite previous audit output')
    result = audit(json.loads(args.evidence.read_text(encoding='utf-8')), args.excerpt.read_text(encoding='utf-8'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: result[k] for k in ['token_core_service_ms','historical_ffn_ms_per_token',
        'scratch_interface_MiB_per_token','active_slot_fraction']}))


if __name__ == '__main__':
    main()
