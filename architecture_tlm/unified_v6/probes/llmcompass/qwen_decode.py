"""Qwen3-4B graph adapter to unmodified LLMCompass operators, Issue186.

Performance only: FP16 is the upstream two-byte proxy for BF16. M=1 uses
upstream GEMV analytic fast path; grouped QK/PV and Softmax use native mapping.
No claims of numerical model execution or full-chip cycle accuracy.
"""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time

UPSTREAM = '2e015fd2ee750e6cad8d7152df52551e5b41ef20'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def inventory(shape, length):
    d, f = shape['hidden_size'], shape['intermediate_size']
    h, kv, hd = shape['num_attention_heads'], shape['num_key_value_heads'], shape['head_dim']
    n = shape['num_hidden_layers']
    q, k = h*hd, kv*hd
    dims = [('q_proj', d, q), ('k_proj', d, k), ('v_proj', d, k),
            ('o_proj', q, d), ('gate_proj', d, f), ('up_proj', d, f), ('down_proj', f, d)]
    dense = sum(a*b for _, a, b in dims)*n + d*shape['vocab_size']
    attn = h*hd*length*n
    return dict(projections=dims, dense_mac=dense, qk_mac=attn, pv_mac=attn,
                total_mac=dense+2*attn, weight_bytes=2*dense,
                kv_read_bytes=2*kv*hd*length*2*n)


def make_devices(case):
    from hardware_model.device import Device, device_dict
    from hardware_model.compute_module import VectorUnit, SystolicArray, Core, ComputeModule, Overhead
    from hardware_model.io_module import IOModule
    from hardware_model.memory_module import MemoryModule
    if case == 'a100_native':
        dev = copy.deepcopy(device_dict['A100_80GB_fp16'])
        return dev, copy.deepcopy(dev), dict(kind='official builtin A100_80GB_fp16', nonlinear_lanes=None,
                    gemv_fabric_override=False, launch='official legacy plus uncalibrated Qwen additions')
    bw = {'small_native_hbm256': 256e9, 'small_native_hbm186': 185.7856946955787e9,
          'small_fabric32': 185.7856946955787e9, 'small_native_ddr': 29.850746268656714e9}[case]
    core = Core(VectorUnit(64, 2, 35, 64, 1), SystolicArray(16, 16, 1, 2, 2), 2, 192*1024)
    comp = ComputeModule(core, 1, 100e6, 8*1024**2, 640, Overhead(0, 0, 0, 0))
    dev = Device(comp, IOModule(bw, 0), MemoryModule(16*1024**3))
    gemv = copy.deepcopy(dev)
    # Upstream's M=1 branch dispatches to VECTOR throughput. Route the ASIC's
    # separately specified 512 MAC/cycle engine through that interface, only
    # for GEMV; do not turn the 64-lane vector/nonlinear unit into 1024 lanes.
    gemv.compute_module.core.vector_unit.total_vector_flops_per_cycle = 1024
    gemv.compute_module.total_vector_flops_per_cycle = 1024
    gemv.compute_module.total_vector_flops = 1024*100e6
    if case == 'small_fabric32':
        # Explicit sensitivity, not an upstream native L2 model: every weight
        # byte crosses a shared 64 GB/s write+read fabric => <=32 GB/s.
        gemv.io_module.bandwidth = min(bw, 32e9)
    return dev, gemv, dict(kind='nominal small-resource match; not identical microarchitecture',
                nonlinear_lanes=16, gemv_fabric_override=case == 'small_fabric32',
                launch='none: ASIC operator service, not GPU software')


def device_record(dev, gemv, notes):
    c = dev.compute_module
    return dict(**notes, clock_hz=c.clock_freq, core_count=c.core_count,
                vector_flops_per_cycle=c.total_vector_flops_per_cycle,
                systolic_mac_per_second=c.total_systolic_array_flops/2,
                gemv_mac_per_second=gemv.compute_module.core.vector_unit.total_vector_flops_per_cycle*c.core_count*c.clock_freq/2,
                shared_bytes=c.l2_size, local_bytes_per_core=c.core.SRAM_size,
                l2_bandwidth_bytes_s=c.l2_bandwidth_per_cycle*c.clock_freq,
                dram_bandwidth_bytes_s=dev.io_module.bandwidth,
                gemv_effective_io_bytes_s=gemv.io_module.bandwidth,
                input_word_bytes=2, partial_sum_word_bytes=2)


def run(case, cfg, length, output):
    from hardware_model.device import device_dict
    from software_model.matmul import Matmul
    from software_model.softmax import Softmax
    from software_model.utils import Tensor, data_type_dict
    dt = data_type_dict['fp16']
    dev, gemv, notes = make_devices(case)
    hardware = device_record(dev, gemv, notes)
    s = cfg['shape']; n = s['num_hidden_layers']; d = s['hidden_size']; f = s['intermediate_size']
    h, kv, hd = s['num_attention_heads'], s['num_key_value_heads'], s['head_dim']
    inv = inventory(s, length); rows = []
    gpu = case == 'a100_native'

    def matrix(name, m, k, cols, repeat, grouped=False):
        op = Matmul(dt); result = op(Tensor([m, k], dt), Tensor([k, cols], dt))
        assert result.shape == [m, cols]
        start = time.perf_counter()
        target = dev if grouped else gemv
        duration = op.compile_and_simulate(target, 'heuristic-GPU')
        assert math.isfinite(duration) and 0 < duration < 100
        mapping = vars(op.best_mapping) if op.best_mapping else None
        row = dict(name=name, category='native_grouped_tile' if grouped else 'native_gemv_analytic',
             m=m, k=k, n=cols, repeat=repeat, mac=m*k*cols*repeat,
             logical_io_bytes=(m*k+k*cols+m*cols)*2*repeat,
             operator_seconds=duration, service_seconds=duration*repeat, mapping=mapping,
             simulator_wall_seconds=time.perf_counter()-start,
             launch_seconds=(21e-6*(n if grouped else repeat)) if gpu else 0.0)
        # The logical QK/PV each launches once per layer, not once per KV group.
        rows.append(row)
        print(json.dumps(dict(case=case, op=name, seconds=row['service_seconds'], wall=row['simulator_wall_seconds'])), flush=True)

    for name, k, cols in inv['projections']:
        matrix(name, 1, k, cols, n)
    # Serial KV groups preserve exactly one K/V read per group; no fake 32-head
    # KV replication. Eight group service times is an explicit conservative
    # scheduling choice. Within each group all four Q heads share K/V.
    matrix('qk', h//kv, hd, length, n*kv, True)
    matrix('pv', h//kv, length, hd, n*kv, True)
    matrix('lm_head', 1, d, s['vocab_size'], 1)
    op = Softmax(dt); op(Tensor([h, length], dt))
    start = time.perf_counter(); st = op.compile_and_simulate(dev)
    rows.append(dict(name='softmax', category='native_softmax_tile', repeat=n, mac=0,
                     operator_seconds=st, service_seconds=st*n, launch_seconds=12e-6*n if gpu else 0,
                     simulator_wall_seconds=time.perf_counter()-start, mapping=vars(op.best_mapping)))

    # Qwen-only operators absent from upstream. These are transparent
    # performance macros with counts, not claims of calibrated device cycles.
    # 4 vector ops/element for RMSNorm includes sum-square/mean/scale/gamma;
    # inverse square root is counted separately once per normalized row.
    def macro(name, elements, vector_ops, special_ops, io_bytes, repeat, gpu_launch=0):
        c = dev.compute_module
        if gpu:
            compute = (vector_ops + special_ops*c.core.vector_unit.flops_per_exp)/c.total_vector_flops
        else:
            compute = (math.ceil(vector_ops/64)+math.ceil(special_ops/16))/c.clock_freq
        io = io_bytes/min(dev.io_module.bandwidth, c.l2_bandwidth_per_cycle*c.clock_freq)
        t = max(compute, io)
        rows.append(dict(name=name, category='explicit_Qwen_macro', repeat=repeat, elements=elements,
                         vector_ops=vector_ops*repeat, special_ops=special_ops*repeat,
                         logical_io_bytes=io_bytes*repeat, mac=0, operator_seconds=t, service_seconds=t*repeat,
                         launch_seconds=gpu_launch*repeat if gpu else 0, macro_compute_seconds=compute,
                         macro_io_seconds=io, calibrated=False))
    macro('rmsnorm_block', d, 4*d, 1, 6*d, 2*n, 45e-6)
    macro('qk_head_norm', (h+kv)*hd, 4*(h+kv)*hd, h+kv, 6*(h+kv)*hd, n, 45e-6)
    macro('rope', (h+kv)*hd, 3*(h+kv)*hd, 0, 8*(h+kv)*hd, n, 21e-6)
    macro('attention_scale', h*length, h*length, 0, 4*h*length, n, 21e-6)
    macro('residual_add', d, d, 0, 6*d, 2*n, 21e-6)
    macro('swiglu', f, 5*f, f, 6*f, n, 45e-6)
    macro('final_rmsnorm', d, 4*d, 1, 6*d, 1, 45e-6)
    # Cache is already allocated: append new token only, no copy-concat of
    # the entire historical KV on each step. L includes the current token.
    macro('kv_append', 2*kv*hd, 0, 0, 2*kv*hd*2, n)
    macro('embedding_lookup', d, 0, 0, 2*d, 1)
    assert sum(r['mac'] for r in rows) == inv['total_mac']
    native = sum(r['service_seconds'] for r in rows if r['category'] != 'explicit_Qwen_macro')
    extras = sum(r['service_seconds'] for r in rows if r['category'] == 'explicit_Qwen_macro')
    official_launch = sum(r['launch_seconds'] for r in rows if r['category'] != 'explicit_Qwen_macro')
    proxy_launch = sum(r['launch_seconds'] for r in rows if r['category'] == 'explicit_Qwen_macro')
    result = dict(status='completed', case=case, upstream_commit=UPSTREAM,
        scope='full Qwen3-4B decode operator graph; native operators plus explicit Qwen macros',
        numerical_execution=False, dataset=None, weights=None, ppl=None,
        batch=1, context_including_current=length, tokens=1, model=cfg, inventory=inv,
        hardware=hardware, rows=rows,
        native_seconds=native, explicit_macro_seconds=extras,
        service_seconds=native+extras,
        native_legacy_launch_seconds=official_launch, extra_macro_launch_proxy_seconds=proxy_launch,
        with_legacy_launch_seconds=native+extras+official_launch+proxy_launch,
        limitations=['native M1 GEMV bypasses L2 and tile search',
            'QK/PV groups sequential; no fused FlashAttention kernel',
            'FP16 two-byte timing proxy for BF16, no numerical equivalence test',
            'native tile partial sums two bytes; TLM has wider accumulators',
            'Qwen vector macros and extra kernel overhead uncalibrated',
            'DRAM bandwidth is analytic, not DRAMSys command replay',
            'small nominal resources do not make upstream topology identical to our ASIC',
            'energy and area not evaluated'])
    save(output, result)
    return result


def main():
    p = argparse.ArgumentParser(); p.add_argument('--upstream', required=True)
    p.add_argument('--config', required=True); p.add_argument('--output', required=True)
    p.add_argument('--case', choices=['a100_native','small_native_hbm256','small_native_hbm186','small_fabric32','small_native_ddr'], required=True)
    p.add_argument('--context', type=int, default=2048)
    args = p.parse_args(); src = Path(args.upstream).resolve(); out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    # Native mapping appends cache entries; source stays immutable.
    scratch = out/'scratch'; (scratch/'systolic_array_model'/'temp').mkdir(parents=True)
    shutil.copyfile(src/'systolic_array_model/look_up_table_16_16.csv', scratch/'systolic_array_model/look_up_table_16_16.csv')
    cfg_path = Path(args.config).resolve(); cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    sys.path.insert(0, str(src)); os.chdir(scratch)
    before = sha(scratch/'systolic_array_model/look_up_table_16_16.csv')
    start = time.perf_counter()
    try:
        result = run(args.case, cfg, args.context, out/'RESULT.json')
        save(out/'EXECUTION.json', dict(status='completed', slurm_job_id=os.getenv('SLURM_JOB_ID'),
            slurm_array_task_id=os.getenv('SLURM_ARRAY_TASK_ID'), command=sys.argv, adapter_sha256=sha(__file__),
            model_config_sha256=sha(cfg_path), model_weights_and_data='N/A: architecture timing only',
            upstream_commit=UPSTREAM, wall_seconds=time.perf_counter()-start,
            lookup_initial_sha256=before,lookup_final_sha256=sha(scratch/'systolic_array_model/look_up_table_16_16.csv'),
            result_sha256=sha(out/'RESULT.json')))
        save(out/'MANIFEST.json', dict(status='completed', files={x:sha(out/x) for x in ['RESULT.json','EXECUTION.json']}))
        print(json.dumps({x:result[x] for x in ['case','service_seconds','with_legacy_launch_seconds']}),flush=True)
    except BaseException as e:
        save(out/'FAILURE.json', dict(status='failed', exception=repr(e), wall_seconds=time.perf_counter()-start))
        raise


if __name__ == '__main__':
    main()
