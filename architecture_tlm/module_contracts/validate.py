"""Validate target P-CIM task records; does not execute RTL or numeric models."""
import argparse
import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def require(ok, message):
    if not ok:
        raise ValueError(message)


def validate(tasks, contract):
    seen, ancestors, states, retired = set(), {}, {}, {}
    pcim = contract['pcim']
    for t in tasks:
        require(all(k in t for k in contract['task_fields']), 'missing task field')
        ident = t['id']
        require(isinstance(ident, str) and ident and ident not in seen, 'duplicate/invalid task id')
        deps = t['depends_on']
        require(isinstance(deps, list) and all(d in seen for d in deps), 'dependency not previously defined')
        closure = set(deps)
        for d in deps:
            closure.update(ancestors[d])
        require(t['mode'] in pcim['modes'], 'unsupported P-CIM mode')
        require(t['input_format'] == pcim['input_formats'][t['mode']], 'wrong sampled input format')
        require(t['output_format'] == pcim['output_format'], 'intermediate output must be FP24 E8/M15')
        require(t['samples'] in pcim['samples'], 'unsupported sampling budget')
        require(t['weight_bits'] == pcim['weight_bits'], 'unbound weight width')
        integer_fields = ['request', 'layer', 'token_begin', 'output_group', 'm', 'n',
                          'k_total', 'k_begin', 'k_end', 'state_id']
        require(all(type(t[f]) is int and t[f] >= 0 for f in integer_fields), 'nonnegative integer field required')
        require(t['m'] > 0 and t['n'] == 128, 'invalid physical M/N shape')
        # This minimal example format has no lane mask yet. Tail blocks must be
        # explicitly described in a later schema, never silently counted as full.
        require(0 <= t['k_begin'] < t['k_end'] <= t['k_total'], 'invalid K range')
        require(all(t[f] % 64 == 0 for f in ['k_begin', 'k_end', 'k_total']), 'K tail mask not defined')
        expected_layout = 'CIM_K64_G64_U64_OUTPUT_MAJOR' if t['mode'] == 'GU' else 'CIM_K64_N128_OUTPUT_MAJOR'
        require(t['weight_layout'] == expected_layout, 'GU/WD physical weight layout mismatch')
        expected_input = pcim['input_storage_bytes'][t['mode']]
        require(t['input_storage_bytes'] == expected_input, 'wrong probability record size')
        scale = t['scale_metadata']
        require(scale.get('source') in ['COMMAND', 'SRAM'] and scale.get('exponent_bits') == 8,
                'scale source and signed8 exponent must be explicit')
        names = ['x_exp', 'g_weight_exp', 'u_weight_exp'] if t['mode'] == 'GU' else ['g_top', 'u_top', 'weight_exp']
        require(all(type(scale.get(n)) is int and -128 <= scale[n] <= 127 for n in names), 'invalid scale exponent')
        if scale['source'] == 'SRAM':
            require(type(scale.get('address')) is int and scale['address'] >= 0 and scale.get('bytes', 0) >= len(names),
                    'missing scale SRAM transaction')
        if t['mode'] == 'WD':
            require(scale.get('alignment') == 'SG_SU_DIV4' and scale.get('offset') == -2,
                    'Wd shared unit and exponent offset must agree exactly once')
        block_count = (t['k_end'] - t['k_begin']) // 64
        for name in ['src', 'weights', 'dst']:
            mem = t[name]
            require(all(k in mem for k in contract['memory_reference_fields']), 'incomplete memory reference')
            require(isinstance(mem['space'], str) and mem['space'], 'invalid memory space')
            require(all(type(mem[f]) is int and mem[f] >= 0 for f in ['address', 'bytes', 'row_stride_bytes']), 'invalid memory range')
        require(t['weights']['bytes'] >= block_count * 8192, 'weight extent too short')
        require(t['src']['row_stride_bytes'] >= expected_input * block_count and
                t['src']['bytes'] >= (t['m'] - 1) * t['src']['row_stride_bytes'] + expected_input * block_count,
                'input extent/row stride too short')
        require(t['dst']['row_stride_bytes'] >= 384 and
                t['dst']['bytes'] >= (t['m'] - 1) * t['dst']['row_stride_bytes'] + 384,
                'FP24 output extent/row stride too short')
        rng = t['rng']
        require(rng.get('binding') and type(rng.get('stream_id')) is int and rng['stream_id'] >= 0 and
                rng.get('advance') == 'ACCEPTED_SAMPLE_EVENT_ONLY', 'RNG must be bound and advance on acceptance')
        sid = t['state_id']
        owner = tuple(t[f] for f in ['request', 'layer', 'token_begin', 'm', 'output_group', 'mode', 'k_total'])
        action = t['accumulation']
        if action in ['INIT', 'INIT_FINAL']:
            require(sid not in states and t['k_begin'] == 0, 'state initialized while live or nonzero first K')
            require(sid not in retired or retired[sid] in closure, 'state reuse lacks prior final-release dependency')
            states[sid] = {'owner': owner, 'next_k': 0, 'last': None, 'dst': t['dst']}
        else:
            require(action in ['CONTINUE', 'FINAL'] and sid in states, 'continuation missing initialized state')
        state = states[sid]
        require(state['owner'] == owner and state['dst'] == t['dst'], 'state owner or destination changed')
        require(state['next_k'] == t['k_begin'], 'K gap, overlap or reset')
        require(state['last'] is None or state['last'] in closure, 'same-state update lacks commit dependency')
        final = action in ['FINAL', 'INIT_FINAL']
        require(final == (t['k_end'] == t['k_total']), 'final flag does not match full K completion')
        state.update(next_k=t['k_end'], last=ident)
        if final:
            del states[sid]
            retired[sid] = ident
        seen.add(ident)
        ancestors[ident] = closure
    require(not states, 'plan ends with unfinished state')
    return {'tasks': len(tasks), 'format': pcim['output_format'], 'status': 'PASS'}


def self_test(contract, example):
    good = example['tasks']
    checks = [{'name': 'two_commands_keep_one_fp24_state', **validate(good, contract)}]
    bad_cases = [
        ('fp32_hidden_interface', 0, 'output_format', 'FP32'),
        ('integer_sample_input_replaced', 0, 'input_format', 'FP24_E8_M15'),
        ('unsupported_t', 0, 'samples', 256),
        ('wrong_weight_width', 0, 'weight_bits', 4),
        ('state_reset_on_continuation', 1, 'accumulation', 'INIT_FINAL'),
        ('missing_commit_dependency', 1, 'depends_on', []),
        ('k_overlap', 1, 'k_begin', 0),
        ('owner_changed', 1, 'request', 2),
        ('wrong_probability_record', 0, 'input_storage_bytes', 64),
        ('unknown_activation_as_mode', 0, 'mode', 'GEGLU'),
        ('unmasked_k_tail', 0, 'k_end', 63),
        ('missing_scale', 0, 'scale_metadata', {}),
        ('too_small_fp24_state', 0, 'dst', {'space': 'STATE_SRAM', 'address': 0, 'bytes': 256, 'row_stride_bytes': 256}),
        ('wrong_gu_weight_layout', 0, 'weight_layout', 'CIM_K64_N128_OUTPUT_MAJOR')
    ]
    for name, index, field, value in bad_cases:
        task = copy.deepcopy(good)
        task[index][field] = value
        try:
            validate(task, contract)
        except ValueError as exc:
            checks.append({'name': name, 'status': 'EXPECTED_REJECTION', 'reason': str(exc)})
        else:
            raise AssertionError(name)
    wd = copy.deepcopy(good[0])
    wd.update(id='wd', mode='WD', k_total=64, accumulation='INIT_FINAL',
              input_format='GU_EVENT_RECORD_S_S2', weight_layout='CIM_K64_N128_OUTPUT_MAJOR',
              input_storage_bytes=288,
              scale_metadata={'source': 'COMMAND', 'exponent_bits': 8,
                              'g_top': 1, 'u_top': 0, 'weight_exp': -8,
                              'alignment': 'SG_SU_DIV4', 'offset': -2},
              src={'space': 'GU_SCRATCH', 'address': 0, 'bytes': 288, 'row_stride_bytes': 288})
    checks.append({'name': 'wd_common_unit_and_fp24_output', **validate([wd], contract)})
    for offset in [0, -4]:
        bad = copy.deepcopy(wd)
        bad['scale_metadata']['offset'] = offset
        try:
            validate([bad], contract)
        except ValueError as exc:
            checks.append({'name': 'wd_wrong_offset_' + str(offset), 'status': 'EXPECTED_REJECTION', 'reason': str(exc)})
        else:
            raise AssertionError('Wd offset accepted')
    reused = copy.deepcopy(good[0])
    reused.update(id='new_group', output_group=1, accumulation='INIT_FINAL', k_total=64)
    try:
        validate(good + [reused], contract)
    except ValueError as exc:
        checks.append({'name': 'state_reuse_without_release_dependency', 'status': 'EXPECTED_REJECTION', 'reason': str(exc)})
    else:
        raise AssertionError('unsafe state reuse accepted')
    reused['depends_on'] = ['gu_b']
    checks.append({'name': 'state_reuse_after_final_commit', **validate(good + [reused], contract)})
    return {'scope': 'TARGET_DESCRIPTOR_VALIDATION_ONLY', 'checks': checks, 'count': len(checks), 'status': 'PASS'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--tasks', type=Path, default=HERE / 'examples.json')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    contract = json.loads((HERE / 'contract.json').read_text(encoding='utf-8'))
    example = json.loads(args.tasks.read_text(encoding='utf-8'))
    result = self_test(contract, example) if args.self_test else validate(example['tasks'], contract)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded.encode('utf-8'))
    print(encoded, end='')


if __name__ == '__main__':
    main()
