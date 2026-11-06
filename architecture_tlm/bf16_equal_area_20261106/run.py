"""Immutable native prefix/full execution with source, byte and area seals."""
from pathlib import Path
import argparse
import hashlib
import json
import time

HERE = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_bytes((json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode())


def check_sources(root):
    for rel, expected in load(root / 'EXECUTION_MANIFEST.json')['files_sha256'].items():
        assert sha(root / rel) == expected, rel
    return sha(root / 'EXECUTION_MANIFEST.json')


def validate(result, budget):
    from architecture_tlm.digital_fair_20261105.joint_handoff.batch import validate as original_validate
    original_validate(result, budget)
    m, a = result['model'], result['actions']
    d, f = m['hidden'], m['ffn']
    q, kv = m['q_heads'] * 128, m['kv_heads'] * 128
    expected = m['layers'] * (d * (q + 2 * kv) + q * d + 3 * d * f) + m['vocab'] * d
    assert a['digital_BF16_MAC'] == expected
    assert a['digital_BF16_SwiGLU_elements'] == m['layers'] * f
    assert not any(a.get(k, 0) for k in ('digital_W8_N64_dot_update', 'digital_W8_BF16_FMA', 'digital_x_quantized_elements'))
    assert sum(r['logical_MAC'] for r in result['matrix_wait_audit']) == expected
    assert sum(r['weight_bytes'] for r in result['matrix_wait_audit']) == 2 * expected
    assert len(result['matrix_wait_audit']) == m['layers'] * 5 + 1
    assert result['executed_resources']['physical_ordinary_FMA_lanes'] == 1888
    assert result['clock_contract']['chip_hz'] == 100000000
    assert abs(budget['covered_area_gap_percent']) < .4
    return dict(status='PASS', full36_and_lm_head=True, logical_BF16_MAC=expected,
                all_matrix_weight_bytes=2 * expected, queues_bytes_area_energy_conserved=True)


class PrefixDone(Exception):
    pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument('root', type=Path)
    p.add_argument('--scope', choices=('prefix', 'full'), required=True)
    args = p.parse_args()
    root = args.root.resolve()
    manifest_sha = check_sources(root)
    from architecture_tlm.digital_fair_20261105.run import bootstrap
    identity = bootstrap(root / 'base')
    from architecture_tlm.digital_baselines_20261104.backend import RamulatorBackend
    from .model import make_model
    from .budget import price, allocate
    profile = load(HERE / 'PROFILE.json')
    prices = load(root / 'PRICES.json')
    reference = load(root / 'BF16_AREA_REFERENCE.json')
    assert profile == allocate(prices, reference)
    dram_profile = next(x for x in load(root / 'base/profiles/PROFILES.json') if x['name'] == 'derived8533')
    config = root / 'base/profiles/derived8533.yaml'
    assert sha(config) == dram_profile['sha256']
    identity.update(execution_manifest_sha256=manifest_sha, config_sha256=sha(config),
                    bridge_sha256=sha(root / 'base/liblpbridge.so'), profile_sha256=sha(HERE / 'PROFILE.json'),
                    prices_sha256=sha(root / 'PRICES.json'))
    output = root / ('preflight_bf16' if args.scope == 'prefix' else 'results/BF16_dense_equal_area')
    output.mkdir(parents=True, exist_ok=False)
    backend = RamulatorBackend(root / 'base/liblpbridge.so', config, dram_profile['period_ns'], 256)
    started = time.time()
    try:
        h, model = make_model(backend, profile, layers=36, include_lm=True, seed=17,
                             attention_input=load(root / 'inputs/representative.json'))
        original_phase = model.phase
        def phase(stage, generators, layer):
            value = original_phase(stage, generators, layer)
            if stage in ('QKV', 'attention', 'GU_g', 'GU_u', 'Wd', 'lm_head'):
                print(json.dumps(dict(event='phase_completed', layer=layer, stage=stage,
                    simulated_ms=h.now * 1e-6, wall_seconds=time.time() - started)), flush=True)
            if args.scope == 'prefix' and stage == 'residual' and layer == 0:
                raise PrefixDone()
            return value
        model.phase = phase
        if args.scope == 'prefix':
            try:
                model.run()
                raise AssertionError('prefix boundary missed')
            except PrefixDone:
                pass
            assert model.prefetched == {(1, 'QKV', 0), (1, 'QKV', 1)}
            assert {v[:3] for v in model.slot_leases.values()} == model.prefetched
            result = dict(status='completed', scope='first_layer_full36_allocation',
                phases=model.phases, actions=dict(model.actions), matrix_wait_audit=model.matrix_audit,
                digital_contract=model.digital_contract)
        else:
            result = model.run()
            result.update(status='completed', scope='whole36+lm_head')
        result.update(backend='native', source_identity=identity, memory=h.report(),
            simulated_ms=h.now * 1e-6, simulated_chip_cycles=h.now / 10,
            wall_seconds=time.time() - started, PPL_measured=False, PPA_measured=False,
            timing_workload='dense deterministic Attention; existing three captured layer input boundary unchanged')
        assert result['memory']['final_pending'] == result['memory']['final_response_occupied'] == 0
        assert not h.mem.queue
        assert all(x <= y for x, y in zip(h.mem.bank_allocated, h.mem.bank_depths))
        result['native'] = backend.finish(h.now)
        total = result['memory']['counts']['dram_read_bytes'] + result['memory']['counts']['dram_write_bytes']
        assert result['native']['counts']['logical64_completed'] * 64 == total
        if args.scope == 'full':
            budget = price(result, prices, profile)
            verification = validate(result, budget)
            save(output / 'BUDGET.json', budget)
        else:
            assert sum(x['logical_MAC'] for x in result['matrix_wait_audit']) == 100925440
            verification = dict(status='PASS', first_layer_full36_allocation=True,
                finite_cross_layer_prefetch=True, native_bytes_match=True)
        save(output / 'RESULT.json', result)
        save(output / 'VALIDATION.json', verification)
        save(output / 'SEAL.json', dict(result_sha256=sha(output / 'RESULT.json'),
            validation_sha256=sha(output / 'VALIDATION.json'), source_identity=identity,
            budget_sha256=sha(output / 'BUDGET.json') if args.scope == 'full' else None))
        print(json.dumps(dict(status='completed', scope=args.scope, simulated_ms=result['simulated_ms'],
                             wall_seconds=result['wall_seconds'], validation=verification)), flush=True)
    finally:
        backend.close()


if __name__ == '__main__':
    main()
