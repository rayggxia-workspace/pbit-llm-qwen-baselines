"""Post-run small-artifact summary and budget estimate, never execute a model."""
import json
from pathlib import Path
import statistics
from .validate_results import validate
from .vendor.scoring import full_window_plan, suffix_plan, plan_batches


def main():
    output = Path(__file__).resolve().parents[1] / 'results/stochastic_20261023'
    root = output / 'checkpoints/complete'
    audit = validate(root, require_complete=True)
    full = full_window_plan(299078, 2048, 1024)
    suffix = suffix_plan(299078, 2048, 128, 32)
    def costs(plan):
        batches = list(plan_batches(plan, 2))
        return dict(targets=sum(p['scored_tokens'] for p in plan), segments=len(plan),
            decode_calls=sum(b[0]['scored_tokens'] for b in batches),
            prefill_calls=sum(b[0]['prefill_tokens'] > 0 for b in batches),
            prefill_tokens=sum(p['prefill_tokens'] for p in plan))
    fc, sc = costs(full), costs(suffix)
    dr = fc['decode_calls'] / sc['decode_calls']
    pr = fc['prefill_tokens'] / sc['prefill_tokens']
    models = {}
    for name, entry in audit['models'].items():
        summaries = {}
        for label in ['bf16', 'ffn', 'screen_exact_ffn', 'rejection128_ffn', 'winner1024_ffn']:
            cases = [r for r in entry['cases'] if r['label'] == label]
            raw = [json.loads((root / 'results' / name / f'{label}_s{r["seed"]}.json').read_bytes()) for r in cases]
            estimates = [(d['decode_seconds'] * dr + d['prefill_seconds'] * pr) / 3600 for d in raw]
            row = dict(entry['summary'][label],
                seeds=[r['seed'] for r in cases], ppl=[r['perplexity'] for r in cases],
                wall_seconds=[r['seconds'] for r in cases],
                mean_wall_seconds=statistics.mean(r['seconds'] for r in cases),
                mean_prefill_seconds=statistics.mean(d['prefill_seconds'] for d in raw),
                mean_decode_seconds=statistics.mean(d['decode_seconds'] for d in raw),
                full_estimate_gpu_hours_per_seed=statistics.mean(estimates),
                full_estimate_gpu_hours_all_seeds=sum(estimates))
            if label not in ('bf16', 'ffn'):
                row['selected_candidate_fraction'] = [d['sampling_stats']['totals']['selected_fraction'] for d in raw]
                row['gqa_union_fraction'] = [d['sampling_stats']['totals']['GQA_union_fraction'] for d in raw]
            summaries[label] = row
        total = sum(r['full_estimate_gpu_hours_all_seeds'] for r in summaries.values())
        models[name] = dict(summary=summaries, full_all_13_nominal_gpu_hours=total,
            planning_gpu_hours_range=[total * .7, total * 1.3])
    result = dict(status='26_CASES_VERIFIED', execution_commit=audit['source']['commit'],
        protocol=audit['protocol'], full_candidate_submitted=False,
        server_package_sha256='a3d0df3f043d4a1fee23f9da547d585bcde0f28e9c325d665880fdd5c1a2ace3',
        full_plan=fc, suffix_plan=sc, decode_scaling=dr, prefill_token_scaling=pr,
        budget_method='decode_seconds * decode-call ratio + prefill_seconds * prefill-token ratio; not a measurement or confidence interval',
        budget_limits='same GPU/software and batch2 assumed; full contexts are shorter, batch1 tails and runtime/JIT vary; +/-30% is planning allowance only; excludes queue/setup/calibration',
        models=models)
    (output / 'SUMMARY.json').write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + '\n').encode())
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
