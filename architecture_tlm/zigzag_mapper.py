"""ZigZag 3.8.5 LOMA -> realizable memory-block candidates for DecodeModel.

The adapter deliberately preserves existing arithmetic and input-stationary SC
loops. ZigZag's digital-MAC latency is NOT used to price stochastic tiles.
"""
import hashlib
import json
import logging
import math
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
DEPS = ROOT / '.deps/zigzag385'
if DEPS.exists():
    sys.path.insert(0, str(DEPS))


def generate(shape, cfg, output):
    import yaml
    import zigzag
    from zigzag.mapping.temporal_mapping import TemporalMappingType
    from zigzag.opt.loma.engine import LomaEngine
    from zigzag.opt.loma.memory_allocator import (
        MemoryAllocator, MemoryHierarchyTooSmallException, MemoryTooSmallException,
    )
    from zigzag.stages.main import MainStage
    from zigzag.stages.stage import Stage
    from zigzag.stages.parser.workload_parser import WorkloadParserStage
    from zigzag.stages.parser.accelerator_parser import AcceleratorParserStage
    from zigzag.stages.workload_iterator import WorkloadStage
    from zigzag.stages.mapping.spatial_mapping_generation import SpatialMappingGeneratorStage

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    logging.getLogger().setLevel(logging.ERROR)
    records = []

    class CaptureLOMA(Stage):
        def is_leaf(self):
            return True

        def run(self):
            kw = self.kwargs
            engine = LomaEngine(
                accelerator=kw['accelerator'], layer=kw['layer'],
                spatial_mapping=kw['spatial_mapping'],
                mapping_type=TemporalMappingType.UNEVEN, loma_lpf_limit=4,
                loma_show_progress_bar=False,
            )
            engine.temporal_loop_dim_size = engine.get_temporal_loops()
            engine.update_min_lpf_factor(engine.temporal_loop_dim_size)
            engine.get_prime_factors()
            for ordering in engine.ordering_generator():
                try:
                    temporal = MemoryAllocator(
                        kw['accelerator'], kw['layer'], kw['spatial_mapping'],
                        ordering, TemporalMappingType.UNEVEN,
                    ).run()
                except (MemoryHierarchyTooSmallException, MemoryTooSmallException):
                    continue
                records.append(dict(
                    layer=kw['layer'].name,
                    ordering_inner_to_outer=[[str(d), int(n)] for d, n in ordering],
                    memory_allocation={str(op): [[[str(d), int(n)] for d, n in level]
                                                for level in levels]
                                       for op, levels in temporal.mapping_dic_origin.items()},
                ))
            # Upstream spatial stage expects only this attribute. No fake CME costs.
            yield SimpleNamespace(accelerator=kw['accelerator']), None

    def memory(bits, operands, bw, served):
        allocation = [f'{op}, {direction}' for op in operands
                      for direction in ('fh', 'tl', 'fl', 'th')]
        return dict(size=int(bits), r_cost=0.0, w_cost=0.0, area=0.0, latency=1,
                    operands=operands,
                    ports=[dict(name='rw_port_1', type='read_write',
                                bandwidth_min=8, bandwidth_max=int(bw),
                                allocation=allocation)], served_dimensions=served)

    # One logical operation is a 64x64 tile; array lanes express eight tile slots.
    # Core cycles/energy and random replay buffers are evaluated by our scheduler.
    hardware = dict(name='qwen_fixed_resources_tile_mapping',
        operational_array=dict(unit_energy=0.0, unit_area=0.0,
                               dimensions=['D1'], sizes=[cfg['sc_engines']]),
        memories={
            'tile_weight_hold': memory(4096*8, ['I2'], 4096*8, []),
            'tile_partial_hold': memory(64*32, ['O'], 64*32, []),
            'weight_sram': memory(cfg['weight_macro']['cache_MiB']*2**20*8,
                                  ['I2'], cfg['weight_macro']['load_bandwidth_GBs']*80, ['D1']),
            'scratch': memory(cfg['scratchpad']['capacity_MiB']*2**20*8,
                              ['I1', 'O'], cfg['scratchpad']['bandwidth_GBs']*80, ['D1']),
            'dram': memory(8*2**30*8, ['I1', 'I2', 'O'],
                           cfg['external_memory']['bandwidth_GBs']*80, ['D1']),
        })
    mapping = [dict(name='default', spatial_mapping={'D1': ['K, 8']},
                    memory_operand_links={'O': 'O', 'W': 'I2', 'I': 'I1'})]
    # The parser requires a list of [dimension, factor] pairs encoded as strings.
    mapping[0]['spatial_mapping'] = {'D1': ['K, 8']}
    workloads = []
    h = shape['hidden_size']; m = shape['intermediate_size']
    kv = shape['num_key_value_heads']*(h//shape['num_attention_heads'])
    for i, (name, inp, out) in enumerate([
        ('qkv', h, h+2*kv), ('Wo', h, h), ('gate_up', h, 2*m),
        ('down', m, h), ('lm_head', h, shape['vocab_size']),
    ]):
        workloads.append(dict(id=i, name=name, operator_type='Gemm',
            equation='O[k] += W[k][c] * I[c]', loop_dims=['K', 'C'],
            loop_sizes=[math.ceil(out/64), inp//64],
            operand_precision={'I': 64*16, 'W': 4096*8,
                               'O': 64*32, 'O_final': 64*16}, operand_source={'W': i}))
    hp = output/'hardware.yaml'; mp = output/'mapping.yaml'; wp = output/'workload.yaml'
    for path, value in [(hp, hardware), (mp, mapping), (wp, workloads)]:
        path.write_text(yaml.safe_dump(value, sort_keys=False), encoding='utf-8')
    MainStage([WorkloadParserStage, AcceleratorParserStage, WorkloadStage,
               SpatialMappingGeneratorStage, CaptureLOMA],
              workload=str(wp), accelerator=str(hp), mapping=str(mp),
              nb_mappings_generated=1).run()
    # Project LOMA loop-prefix footprints onto the supported contiguous DMA tiling.
    # Full loop-order changes are not silently executed by this adapter.
    chunks = {cfg['digital']['weight_chunk_bytes']}
    for record in records:
        tiles = cfg['sc_engines']
        for _, count in record['ordering_inner_to_outer']:
            tiles *= count
            size = tiles*4096
            if 4096 <= size <= 1024**2:
                chunks.add(size)
    result = dict(tool='ZigZag', version=zigzag.__version__, engine='LOMA + MemoryAllocator',
                  lpf_limit=4, valid_mappings=len(records), mappings=records,
                  dma_chunk_bytes=sorted(chunks),
                  scope='tile-level logical GEMV mapping; preserve arithmetic/SC loop order; real core and replay costs rescored by TLM',
                  input_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in (hp, mp, wp)})
    (output/'loma_candidates.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    from system_decode import load
    c, _, s = load()
    r = generate(s, c, ROOT/'results/mapping_20261015/zigzag')
    print(json.dumps({k: v for k, v in r.items() if k != 'mappings'}, indent=2))
