"""Compact immutable raw outputs; distinguish Link, DRAMSys and quality evidence."""
import argparse
import csv
import hashlib
import json
import math
import statistics
from functools import lru_cache
from collections import defaultdict
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=3)
def trace_probabilities(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    rows = {}
    for row in data['rows']:
        top = max(row['logits'])
        p = [math.exp(x-top) for x in row['logits']]
        total = sum(p)
        rows[row['token'],row['layer'],row['head']] = [x/total for x in p]
    return rows


def compact(path, backend):
    d = json.loads(path.read_text(encoding='utf-8'))
    n = d['config']['decode_tokens']
    if n != 1:
        raise ValueError('This report contract is single-query decode; multi-token K/V denominators require length summation')
    a, tr, e, tm = d['actions'], d['traffic'], d['energy_J'], d['time_ns']
    assert math.isclose(sum(e.values()) * 1000 / n, d['metrics']['scenario_mJ_per_token'], rel_tol=1e-10)
    assert d['actual_shape']['num_hidden_layers'] == 32
    assert d['actual_shape']['num_attention_heads'] == d['actual_shape']['num_key_value_heads'] == 32
    assert d['quality_reference_ppl'] is None
    assert d['bounds'].get('random_word_replay_bytes', 0) == 0
    full_k = 32 * 32 * d['context'] * 128 * 2 * n
    fused = tr.get('attention_KV_fused_physical_bytes', 0)
    k = tr.get('attention_K_physical_bytes', 0) + fused / 2
    v = tr.get('attention_V_gather_physical_bytes', 0) + fused / 2
    selected = a['ATT_selected_QK_tokens'] / a['ATT_possible_QK_tokens']
    assert math.isclose(k / full_k, selected, abs_tol=1e-12), 'MHA K read ratio must equal selected fraction'
    if d['case'].endswith(('pv', 'ising')):
        expected = 32 * 32 * (d['context'] // 16) * n
        assert a['ATT_V_sample_events'] == expected
        assert a['ATT_V_group_union_rows'] == a['ATT_V_unique_head_indices']
        assert v <= full_k, 'sparse V must not read beyond all V'
    macro = d.get('ising_macro_v4')
    if macro:
        assert macro['calls'] == 32 * 32 * n
        assert not macro['internal_rng_separately_charged']
    # One table includes ALL configured terms; no conversion to MAC equivalents.
    categories = defaultdict(float)
    for key, value in e.items():
        if key.startswith('external_'):
            category = 'DRAM'
        elif key.startswith('SRAM_'):
            category = 'SRAM'
        elif key.startswith(('SC_', 'weight_macro', 'weight_resident')):
            category = 'SC_core_and_residence'
        elif key.startswith(('RNG_', 'input_mask')):
            category = 'FFN_RNG_and_distribution'
        elif key.startswith('ATT_'):
            category = 'Attention_logic_and_sampler'
        else:
            category = 'Digital_projection_norm_control'
        categories[category] += value / n * 1000
    memory = d['memory_v5']['SRAM']
    external = d['external_memory_model']
    power = external.get('power_at_system_end', {})
    row = dict(backend=backend, case=d['case'], context=d['context'], seed=d['seed'],
        engines=d['config']['sc_engines'], samples_per_head=(d['context']//16 if d['case'].endswith(('pv', 'ising')) else 0),
        ms_per_token=d['metrics']['mean_TPOT_ms'], mJ_per_token=d['metrics']['scenario_mJ_per_token'],
        area_mm2=d['metrics']['parameterized_area_mm2'], area_feasible=d['metrics']['area_budget_feasible'],
        attention_ms_per_token=d['metrics']['attention_ms_per_token'],
        FFN_ms_per_token=sum(tm.get(k, 0) for k in ['FFN_gate_up', 'FFN_SwiGLU', 'FFN_down']) / n / 1e6,
        QK_fraction=selected, K_physical_fraction=k/full_k, V_physical_fraction=v/full_k,
        K_MiB_per_token=k/n/2**20, V_MiB_per_token=v/n/2**20,
        summary_MiB_per_token=sum(value for key, value in tr.items() if key.startswith('external_ATT_summary') and key.endswith('_burst_bytes')) / n/2**20,
        weight_GiB_per_token=tr.get('external_weights_read_burst_bytes', 0)/n/2**30,
        work_peak_MiB=d['memory_v5']['work_peak_bytes']/2**20,
        SRAM_MiB=sum(x['capacity_bytes'] for x in memory.values())/2**20,
        SRAM_area_mm2=sum(x['area_mm2'] for x in memory.values()),
        DRAM_core_mJ_per_token=e.get('external_DRAMPower_core', 0)/n*1000 if power else None,
        DRAM_interface_proxy_mJ_per_token=e.get('external_DRAMPower_interface', 0)/n*1000 if power else None,
        energy_categories_mJ_per_token=dict(categories), time_categories_ms_per_token={k:v/n/1e6 for k,v in tm.items()},
        attention_phase_ms_per_token=d['llama_attention']['phase_ms_per_token'],
        energy_mJ_per_token={k:v/n*1000 for k,v in e.items()},
        traffic=tr, bounds=d['bounds'], rng=d.get('rng_hierarchy'),
        Ising=macro, source_commit=d.get('execution_source_commit'),
        configuration_sha256=d['configuration_sha256'], input_snapshot_sha256=d.get('execution_manifest_sha256'),
        trace=d['attention_v3']['trace'], wall_seconds=d['wall_seconds'],
        raw_artifact=dict(path=str(path), bytes=path.stat().st_size, sha256=digest(path)),
        source_hashes=d['source_hashes'])
    if 'screen' in d['case'] and d['config']['attention_v3'].get('trace_file'):
        probabilities = trace_probabilities(d['config']['attention_v3']['trace_file'])
        masses = []
        for selection in d['attention_v3']['rows']:
            p = probabilities[selection['token'],selection['layer'],selection['head']]
            masses.append(sum(p[i] for block in selection['selected_blocks']
                              for i in range(block*64, min(len(p),(block+1)*64))))
        row['offline_retained_attention_mass'] = {'mean':statistics.mean(masses), 'minimum_head':min(masses),
            'scope':'BF16-oracle diagnostic only; not PPL or joint-SC quality validation'}
    if 'dramsys' in backend:
        assert external.get('capacity_bytes') == 16*2**30
        assert external['final_simulation_time_ns'] >= sum(tm.values()) if 'final_simulation_time_ns' in external else True
        row['DRAM_configuration_sha256'] = external['configuration_sha256']
        row['DRAM_bursts'] = {k:external.get(k) for k in ['bursts', 'read_bursts', 'write_bursts', 'peak_pending']}
    return row


def collect(args):
    if args.output.exists():
        raise ValueError('refusing to overwrite report directory')
    args.output.mkdir(parents=True)
    rows = []
    for backend in ['link_Staggered', 'dramsys_Staggered', 'dramsys_NoPowerDown']:
        for path in sorted((args.project / 'outputs' / backend).glob('*.json')):
            # Backend debug outputs are not model result files.
            if '_dram' in path.name:
                continue
            rows.append(compact(path, backend))
    cases = ['bf16_dense','int8_dense','sc_dense','sc_pv','sc_screen_exact','sc_screen_pv','sc_ising','sc_screen_ising']
    expected = set()
    for backend, contexts in [('link_Staggered',[512,1024,2048]), ('dramsys_Staggered',[2048])]:
        for context in contexts:
            for case in cases:
                for seed in ([0] if case in cases[:3] else [0,1,2]):
                    expected.add((backend,context,case,8,seed))
    for engines in [16,32,64]:
        for case in ['sc_dense','sc_screen_pv']:
            expected.add(('link_Staggered',2048,case,engines,0))
    for case in ['bf16_dense','sc_dense','sc_screen_pv','sc_screen_ising']:
        expected.add(('dramsys_NoPowerDown',2048,case,8,0))
    actual = [(r['backend'],r['context'],r['case'],r['engines'],r['seed']) for r in rows]
    if len(set(actual)) != len(actual) or not set(actual) <= expected:
        raise ValueError('duplicate or unexpected scenario keys')
    (args.output / 'cases.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    scalar_keys = ['backend','case','context','seed','engines','samples_per_head','ms_per_token','mJ_per_token','area_mm2','area_feasible','attention_ms_per_token','FFN_ms_per_token','QK_fraction','K_physical_fraction','V_physical_fraction','K_MiB_per_token','V_MiB_per_token','summary_MiB_per_token','weight_GiB_per_token','work_peak_MiB','SRAM_MiB','SRAM_area_mm2','DRAM_core_mJ_per_token','DRAM_interface_proxy_mJ_per_token','wall_seconds']
    with (args.output / 'cases.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=scalar_keys, lineterminator='\n')
        writer.writeheader()
        writer.writerows({k:r[k] for k in scalar_keys} for r in rows)
    groups = defaultdict(list)
    for row in rows:
        groups[row['backend'],row['context'],row['case'],row['engines']].append(row)
    summary = []
    for key, values in groups.items():
        row = dict(backend=key[0], context=key[1], case=key[2], engines=key[3], seeds=[r['seed'] for r in values])
        for field in scalar_keys[5:]:
            if field in ('area_feasible',):
                row[field] = all(r[field] for r in values)
            elif all(isinstance(r[field], (float,int)) and r[field] is not None for r in values):
                row[field] = statistics.mean(r[field] for r in values)
                if field in ('ms_per_token','mJ_per_token','K_physical_fraction','V_physical_fraction'):
                    row[field+'_stdev'] = statistics.stdev(r[field] for r in values) if len(values)>1 else 0.
            else:
                row[field] = None
        summary.append(row)
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8', newline='\n')
    # Exact trace/validation identities remain distinct from new PPL or measured power.
    manifest = dict(project=str(args.project), report_source_sha256=digest(Path(__file__)),
        results=len(rows), expected_full_results=len(expected), missing_cases=sorted(expected-set(actual)),
        completeness_by_backend={b:sum(r['backend']==b for r in rows) for b in ['link_Staggered','dramsys_Staggered','dramsys_NoPowerDown']},
        scope='single public WT2 decode query per context; real BF16 QK address oracle, no joint SC numeric inference or new PPL',
        trace_artifacts=[dict(path=str(p),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted((args.project/'outputs/traces').glob('*.json'))],
        result_artifacts=[r['raw_artifact'] for r in rows])
    (args.output / 'ARTIFACT_INDEX.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'count':len(rows),'by_backend':manifest['completeness_by_backend'],'summary_path':str(args.output/'summary.json')}, ensure_ascii=True))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    collect(p.parse_args())
