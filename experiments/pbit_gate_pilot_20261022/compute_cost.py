"""Operation ledger from published gate results; no training or PPA coefficients."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import subprocess


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    repo = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=repo / 'qwen/results/pbit_gate_cost_20261022')
    args = parser.parse_args()
    source = repo / 'qwen/results/pbit_gate_optimization_20261022'
    results = json.loads((source / 'RESULTS.json').read_text(encoding='utf-8'))
    assert results['blind_docs'] == 48 and results['record_count'] == 90
    git = 'C:/Program Files/Git/cmd/git.exe'
    if not Path(git).is_file():
        git = 'git'
    head = '8f25afc5a2d1b46ce6e1b06dcbd7519f946bcc82'
    positions = [1023, 1535, 2047]
    cases = []
    for position in positions:
        blocks = math.ceil((position + 1) / 64)
        free = blocks - 3
        cases.append({
            'visible_tokens': position + 1, 'valid_blocks': blocks, 'forced_blocks': 3,
            'free_blocks': free, 'network_continuous_multiplications': 32 * free,
            'network_additions_including_bias': 40 * free,
            'network_bit_weight_gates': 8 * free, 'network_bernoulli_events': 9 * free,
            'max4_probabilistic_bernoulli_events': free,
            'common_summary_dot_multiplications': 256 * free,
            'common_summary_dot_additions': 252 * free,
            'query_relative_network_extra_center_subtracts': 4 * free,
            'query_relative_network_scale_multiplications': 4 * free,
            'query_relative_network_clip_comparisons': 8 * free,
            'max4_scale_multiplications_after_common_center': free,
            'network_fp32_feature_buffer_bytes': 4 * free * 4,
            'max4_fp32_feature_buffer_bytes': free * 4,
            'qk_only_multiplier_break_even_saved_blocks': 32 * free / 4096,
        })

    # Verify deployment bit gating against all hidden states of all long-trained models.
    model_checks = []
    for path in sorted((source / 'models').glob('refine1__*.json')):
        payload = json.loads(path.read_text(encoding='utf-8'))
        assert payload['kind'] == 'pbit_4_8_1' and payload['parameter_count'] == 49
        params = payload['parameters']
        assert len(params['hidden_weight']) == 4
        assert all(len(row) == 8 for row in params['hidden_weight'])
        assert len(params['hidden_bias']) == len(params['output_weight']) == 8
        assert payload['normalization']['mode'] == 'query_relative'
        for hidden in itertools.product((0, 1), repeat=8):
            multiply = sum(bit * weight for bit, weight in zip(hidden, params['output_weight'])) + params['bias']
            gate = sum(weight if bit else 0.0 for bit, weight in zip(hidden, params['output_weight'])) + params['bias']
            assert multiply == gate
        model_checks.append({'path': path.relative_to(repo).as_posix(), 'sha256': sha256(path),
                             'all_hidden_states_checked': 256})
    assert len(model_checks) == 9

    # Source results average equally many query/head groups at all three positions.
    # Preserve that mixture; do not apply its delta-k to a single 2K query.
    layers = []
    mean_free = statistics.mean(c['free_blocks'] for c in cases)
    for layer in results['layers']:
        strong = layer['strong_max4_chosen_by_val']
        net = layer['pbit_three_seed_mean']
        records = []
        for pos in positions:
            metric = 'expected_selected_blocks'
            k_net = statistics.mean(r['by_position'][str(pos)][metric] for r in layer['pbit_individual'])
            k_max = strong['by_position'][str(pos)][metric]
            free = math.ceil((pos + 1) / 64) - 3
            records.append({'visible_tokens': pos + 1, 'free_blocks': free,
                            'max4_selected_blocks': k_max, 'network_selected_blocks': k_net,
                            'saved_blocks': k_max - k_net,
                            'saved_candidate_qk_mac': 4096 * (k_max - k_net),
                            'network_continuous_multiplications': 32 * free})
        for key, expected in [('max4_selected_blocks', strong['metrics']['expected_selected_blocks']),
                              ('network_selected_blocks', net['expected_selected_blocks'])]:
            assert math.isclose(statistics.mean(r[key] for r in records), expected, abs_tol=1e-10)
        saved = strong['metrics']['expected_selected_blocks'] - net['expected_selected_blocks']
        layers.append({'layer': layer['layer'], 'strong_max4_id': strong['id'],
                       'max4_selected_blocks': strong['metrics']['expected_selected_blocks'],
                       'network_selected_blocks': net['expected_selected_blocks'],
                       'saved_blocks': saved, 'saved_candidate_qk_mac': 4096 * saved,
                       'network_continuous_multiplications': 32 * mean_free,
                       'additional_multiplier_count_net_minus_saved_qk': 32 * mean_free - 4096 * saved,
                       'by_context': records})
    binding = ['experiments/pbit_gate_pilot_20261022/network.py',
               'experiments/pbit_gate_pilot_20261022/optimize.py',
               'experiments/pbit_gate_pilot_20261022/train.py',
               'experiments/pbit_gate_pilot_20261022/capture_teacher.py',
               'qwen/results/pbit_gate_optimization_20261022/RESULTS.json']
    for path in binding:
        committed = subprocess.check_output([git, '-C', str(repo), 'show', head + ':' + path])
        assert hashlib.sha256(committed).hexdigest() == sha256(repo / path), path
    ledger = {'scope': 'Inference operation ledger, not synthesized/measured PPA or full-model PPL',
              'source_commit': head, 'integration_commit': '83e15289434af50fc09c35e699d8b39965389d98',
              'analysis_script_sha256': sha256(Path(__file__)),
              'source_files': [{'path': p, 'sha256': sha256(repo / p)} for p in binding],
              'inference_contract': 'one mask per query/head; skip forced and invalid slots; original Python evaluates all 32 slots before overriding masks',
              'numeric_format': 'FP32 software parameters/features; no quantized deployment quality assumed',
              'per_free_block_network': {'continuous_multiplications': 32, 'hidden_additions_with_bias': 32,
                                         'output_bit_weight_gates': 8, 'output_additions_with_bias': 8,
                                         'bernoulli_events': 9, 'sequential_sampling_stages': 2},
              'parameter_storage': {'scalars_per_layer': 49, 'fp32_bytes_per_layer': 196,
                                    'includes_device_area_or_drivers': False},
              'context_cases': cases, 'observed_mixture': {'mean_free_blocks': mean_free, 'layers': layers},
              'validation': {'long_models_checked': 9, 'hidden_state_equivalence_cases': 9 * 256,
                             'weighted_position_means_checked': 6, 'all_passed': True},
              'model_checks': model_checks,
              'ppa': {'area_mm2': None, 'energy_pj': None, 'power_mw': None, 'latency_ns': None,
                      'reason': 'No matching node/driver/arithmetic/RNG primitive characterization or selector RTL synthesis'}}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'COST.json').write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'validation': ledger['validation'], 'context_cases': cases,
                      'mixture_layers': layers}, ensure_ascii=False))


if __name__ == '__main__':
    main()
