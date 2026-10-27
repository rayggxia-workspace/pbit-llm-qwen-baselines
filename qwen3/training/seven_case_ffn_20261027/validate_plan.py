"""Check the seven-case design and published file references; never launch jobs."""
import json
from pathlib import Path


def validate(plan, index, root):
    expected = {
        'B0': (8, 'tile64', 32), 'W6': (6, 'tile64', 32),
        'W10': (10, 'tile64', 32), 'S1': (8, 'all_ffn', 32),
        'S3': (8, 'projection_role', 32), 'T16': (8, 'tile64', 16),
        'T64': (8, 'tile64', 64)}
    rows = plan['cases']; factors = plan['factor_names']
    if len(rows) != 7 or len({r['id'] for r in rows}) != 7:
        raise ValueError('exactly seven unique cases required')
    by_id = {r['id']: r for r in rows}
    if set(by_id) != set(expected):
        raise ValueError('case names do not match the user-confirmed seven')
    baseline = by_id['B0']
    for name, row in by_id.items():
        if tuple(row[k] for k in factors) != expected[name]:
            raise ValueError('changed experiment definition: '+name)
        changed = [k for k in factors if row[k] != baseline[k]]
        if name == 'B0':
            if changed or row['changed_factor'] is not None:
                raise ValueError('invalid baseline')
        elif len(changed) != 1 or changed[0] != row['changed_factor']:
            raise ValueError('not a one-factor ablation: '+name)
    common = plan['common']
    if not common['weight_scales_power_of_two'] or not common['weight_scales_frozen_during_training_and_inference']:
        raise ValueError('scales must be frozen powers of two')
    if common['weight_tile'] != [64,64] or not common['weight_bits_include_sign']:
        raise ValueError('incorrect tile/bitwidth contract')
    if common['sample_count_controls'] != ['input_samples','nonlinear_samples']:
        raise ValueError('both sample stages must be explicit')
    if common['trainable_scope'] != 'full_model' or plan['executable']:
        raise ValueError('this is a full-model plan, not an executable reference-runner config')
    if 'IID' not in common['nonlinear_sampler'] or common['stochastic_weights'] or common['or_grouping']:
        raise ValueError('unexpected random nonlinear or weight/counting scheme')
    curriculum = common['curriculum']
    if curriculum[0]['start_token'] != 0 or curriculum[-1]['end_token'] != common['max_tokens_per_case']:
        raise ValueError('curriculum budget mismatch')
    if any(a['end_token'] != b['start_token'] for a,b in zip(curriculum,curriculum[1:])):
        raise ValueError('curriculum gaps or overlaps')
    for entry in index['files']:
        path = root/entry['path']
        if not path.is_file():
            raise ValueError('listed source file does not exist: '+entry['path'])
        if '/blob/'+index['branch']+'/'+entry['path'] not in entry['github_url']:
            raise ValueError('GitHub file URL does not match path')
    return {'status':'passed','cases':7,'one_factor_variants':6,
            'file_references':len(index['files']),
            'note':'plan/components checked; no full-model training or remote jobs launched'}


def main():
    folder=Path(__file__).resolve().parent
    plan=json.loads((folder/'CASES.json').read_text(encoding='utf-8'))
    index=json.loads((folder/'FILE_INDEX.json').read_text(encoding='utf-8'))
    root=folder.parents[2]
    print(json.dumps(validate(plan,index,root),ensure_ascii=False))


if __name__=='__main__':main()
