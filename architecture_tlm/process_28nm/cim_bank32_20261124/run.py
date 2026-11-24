"""Replay the existing whole TLM with a finite single-zone CIM overlay."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import model as bank_model

HERE = Path(__file__).resolve().parent
def load(p): return json.loads(Path(p).read_bytes())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p, value): p.write_bytes((json.dumps(value, indent=2, allow_nan=False)+'\n').encode('utf-8'))


def main():
    p = argparse.ArgumentParser()
    for name in ('process-root','snapshot','runtime','dependencies'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--config', type=Path, default=HERE/'CONFIG.json')
    p.add_argument('--cores', type=int)
    p.add_argument('--scope', choices=('ffn','layer','full'), default='layer')
    p.add_argument('--backend', choices=('analytic','native'), default='analytic')
    p.add_argument('--legacy-control', action='store_true')
    p.add_argument('--seed', type=int, default=17)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); cfg = load(a.config); cores = a.cores or cfg['default_cores']
    assert 1 <= cores <= 16
    a.out.mkdir(parents=True, exist_ok=False)
    sources = {x.name: sha(x) for x in HERE.glob('*.py')}
    sources['CONFIG.json'] = sha(a.config)
    parent_sources = {x.name: sha(x) for x in a.process_root.glob('*.py')}
    save(a.out/'SOURCE_MANIFEST.json', dict(overlay=sources, parent=parent_sources,
        binding_sha256=sha(a.process_root/'250MHz/BINDINGS.json'),
        parent_config_sha256=sha(a.process_root/'250MHz/WHOLE_CONFIG.json')))
    print(json.dumps(dict(stage='preflight', cores=cores, scope=a.scope)), flush=True)
    sys.path.insert(0, str(a.process_root.resolve()))
    import whole_model
    import whole_pricing
    binding = load(a.process_root/'250MHz/BINDINGS.json')
    macros = load(a.process_root/'250MHz/WHOLE_CONFIG.json')
    binding_sha = sha(a.process_root/'250MHz/BINDINGS.json')
    frozen = load(a.snapshot/'SNAPSHOT_MANIFEST.json')
    for name, item in frozen['sources'].items():
        assert sha(a.snapshot/name) == item['sha256'], name
    spec = importlib.util.spec_from_file_location('bank32_host', a.snapshot/'glue/current_mainline.py')
    boot = importlib.util.module_from_spec(spec); spec.loader.exec_module(boot)
    boot.environment(a.snapshot, a.runtime, a.dependencies, 250)
    from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
    if a.backend == 'analytic':
        backend = AnalyticDRAM(latency_ns=30, bandwidth_GBs=136.4606)
    else:
        from architecture_tlm.digital_baselines_20261104.backend import RamulatorBackend
        profile = next(x for x in load(a.runtime/'base/profiles/PROFILES.json') if x['name']=='derived8533')
        path = a.runtime/'base/profiles/derived8533.yaml'
        assert sha(path) == profile['sha256']
        backend = RamulatorBackend(a.runtime/'base/liblpbridge.so', path, profile['period_ns'], 256)
    started = time.time(); layers = 36 if a.scope == 'full' else 1
    try:
        h, m, host, shape, identity = whole_model.build(a.snapshot, a.runtime, a.dependencies,
            binding, binding_sha, backend, cores, 1, macros, a.seed, a.scope=='full', layers)
        if not a.legacy_control:
            bank_model.install(m, cfg, macros, binding, whole_model.finish_output)
            whole_pricing.sram_budget = bank_model.sram_budget
        print(json.dumps(dict(stage='built', cores=cores, SRAM_KiB=h.mem.capacity//1024)), flush=True)
        if a.scope == 'ffn':
            h.execute([m.prefetch_gu(0)])
            m.phase('GU', [m.sc_gu(0)], 0)
            m.phase('NL_Wd', [m.sc_down(0)], 0)
        else:
            def progress(stage, layer, ns):
                print(json.dumps(dict(stage=stage, layer=layer, simulated_us=ns/1000,
                    wall_seconds=round(time.time()-started, 2))), flush=True)
            host.full_run(m, [load(a.snapshot/'inputs/SHAPE_FIXTURES.json')['qwen3_4b']]*3,
                layers, a.scope=='full', progress)
        memory = h.report(); sram = h.mem.report(h.now)
        assert not h.events and not h.mem.queue and not memory['final_pending']
        assert not memory['final_response_occupied'] and not m.common_prefetched
        assert m.kernel_active['GU_frames'] == layers*6080
        assert m.kernel_active['Wd_M128_frames'] == layers*3040
        assert m.actions['SC_equivalent_MAC'] == layers*74711040
        assert memory['ingress']['captured_beats'] == memory['ingress']['landed_beats']
        if not a.legacy_control:
            assert not any(m.cim_compute_busy) and all(x == 'free' for x in m.cim_states)
            assert sram['capacity_bytes'] == (576+8*cores)*1024
        result = dict(status='completed', scope=a.scope, model='Qwen3-4B', layers=layers,
            process='TSMC28HPC+', clock_MHz=250, time_ns=h.now, time_ms=h.now/1e6,
            includes_lm_head=a.scope=='full', seed=a.seed, backend=a.backend,
            FFN_cores=cores, legacy_control=a.legacy_control, phases=m.phases,
            common_FFN_stages=m.common_stats, actions=dict(m.actions),
            kernel_active=dict(m.kernel_active), process28_counts=dict(m.p28_counts),
            memory=memory, SRAM=sram, macro_config=macros,
            source_identity=identity, source_sha256=sources, bindings_sha256=binding_sha,
            snapshot_manifest_sha256=sha(a.snapshot/'SNAPSHOT_MANIFEST.json'),
            numeric_model_or_PPL=False, physical_wholechip_verified=False,
            wall_seconds=time.time()-started,
            CIM_contract=None if a.legacy_control else m.cim_contract)
        if a.backend == 'native': result['native'] = backend.finish(h.now)
        if a.scope != 'ffn':
            budget = whole_pricing.price(m, result, binding)
            if not a.legacy_control:
                for row in budget['rows']:
                    if row['component'].startswith('SRAM28_'):
                        row['component'] = 'ordinary_S0_and_custom_CIM512_proxy'
                        row['basis'] = cfg['CIM_price_status']
                budget['CIM_interface_status'] = cfg['CIM_price_status']
            save(a.out/'BUDGET.json', budget)
        save(a.out/'RESULT.json', result)
        validation = dict(status='PASS', queues_drained=True, exact_frame_and_MAC_coverage=True,
            single_zone_write_compute_exclusion=not a.legacy_control,
            no_hidden_32slot_pool=not a.legacy_control,
            new_RTL_or_PPA=False, full36_layer_run=a.scope=='full')
        save(a.out/'VALIDATION.json', validation)
        assert all(sha(HERE/name)==value for name,value in sources.items()), 'overlay changed during execution'
        assert all(sha(a.process_root/name)==value for name,value in parent_sources.items()), 'parent changed during execution'
        files = [x for x in a.out.glob('*.json') if x.name != 'SEAL.json']
        save(a.out/'SEAL.json', dict(status='completed', files_sha256={x.name:sha(x) for x in files}))
        print(json.dumps(dict(status='completed', scope=a.scope, cores=cores,
            time_ms=h.now/1e6, SRAM_KiB=sram['capacity_bytes']//1024,
            wall_seconds=round(time.time()-started, 2))), flush=True)
    finally:
        if hasattr(backend, 'close'): backend.close()


if __name__ == '__main__': main()
