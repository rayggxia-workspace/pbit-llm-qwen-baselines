"""Exhaust the SUPPORTED memory-schedule candidate space, not all architectures."""
import copy
import csv
import itertools
import json
from run_mapping_optimization import OUTPUT, checked_run, score, verify_same_work
from system_decode import load


def main():
    cfg, evidence, shape = load()
    loma = json.loads((OUTPUT/'zigzag/loma_candidates.json').read_text())
    selected = json.loads((OUTPUT/'selection.json').read_text())
    rows = []; summary = {}
    for context in (2048, 8192):
        for variant in ('digital_int8_ffn', 'fixed_sc_exact'):
            c = copy.deepcopy(cfg); c['context_tokens'] = context
            reference = json.loads((OUTPUT/f'{variant}_{context}_before.json').read_text())
            results = []
            for chunk, pin, attention, early in itertools.product(
                loma['dma_chunk_bytes'], (False, True), (64, 128, 256, 512),
                (False, True) if variant == 'fixed_sc_exact' else (True,)):
                plan = dict(chunk_bytes=chunk, pin=pin, attention_tokens=attention,
                            early_sc_weights=early)
                r = checked_run(c, variant, evidence, shape, plan)
                verify_same_work(reference, r)
                results.append(r)
                rows.append(dict(context=context, variant=variant, **plan, **r['metrics']))
            best = min(results, key=score)
            best_plan = best['mapping_plan']
            old = selected[str(context)][variant]
            # Tie-equivalent plans are permitted, compare actual objective too.
            same_score = abs(score(best)-old['after']['metrics']['mean_TPOT_ms']
                             *old['after']['metrics']['scenario_mJ_per_token']) < 1e-6
            summary[f'{variant}_{context}'] = dict(
                candidates=len(results), best_plan=best_plan, best_metrics=best['metrics'],
                coordinate_search_found_same_EDP=same_score,
                matches_validated_plan=best_plan == old['selected_plan'])
            (OUTPUT/f'{variant}_{context}_exhaustive_best.json').write_text(json.dumps(best, indent=2)+'\n')
            (OUTPUT/'exhaustive_verification.json').write_text(json.dumps(summary, indent=2)+'\n')
            print(json.dumps(dict(case=f'{variant}_{context}', **summary[f'{variant}_{context}'])), flush=True)
    with (OUTPUT/'exhaustive_search.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=rows[0]); w.writeheader(); w.writerows(rows)


if __name__ == '__main__':
    main()
