"""S/S2 full-task extension; reuse the frozen official S/S4 scoring path."""
import argparse
from contextlib import nullcontext
import gc
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

OWN = Path(__file__).resolve().parent
SOURCE = OWN.parents[1]
TASK_SOURCE = OWN.parent / 't64_scale_task_accuracy_20261126'
HALF_SOURCE = OWN.parent / 't64_onebit_half_20261126'
PARENT = OWN.parent / 't64_dynamic_scale_20261125'
ONEBIT = OWN.parent / 't64_group64_onebit_20261126'
sys.path[:0] = [str(TASK_SOURCE), str(HALF_SOURCE), str(PARENT), str(ONEBIT)]
import runner as previous
from half import FractionOverride


class TaskFractionOverride(FractionOverride):
    def report(self):
        report = super().report()
        return dict(report['probability_codes'], integer_backend=report['integer_backend'],
                    group_scales=report['group_scales'], step_bits=self.step_bits,
                    small_scale_divisor=1 << self.step_bits)


def cases(plan):
    return [dict(id=f'S2_{p}_{tx}_{ta}', policy=p, T_x=tx, T_and=ta,
                 input_law='stratified_T', and_law='joint_grid', grid_g_sig_u=grid)
            for (tx, ta), grid in zip(plan['budgets'], plan['grids'])
            for p in plan['policies']]


def scale_context(policy):
    if policy == 'BF16':
        return nullcontext()
    if policy in ('gu_onebit64', 'all64_onebit'):
        return TaskFractionOverride(policy, 1)
    raise ValueError(policy)


def configure_parent():
    previous.OWN = OWN
    previous.SOURCE = SOURCE
    previous.cases = cases
    previous.scale_context = scale_context


def preflight(settings, root):
    from score_reference import save
    sys.path.insert(0, settings['runtime'])
    tests = unittest.TestSuite()
    for folder, pattern in [(ONEBIT, 'test_onebit.py'), (PARENT, 'test_dynamic.py'),
                            (HALF_SOURCE, 'test_half.py'), (OWN, 'test_tasks.py')]:
        tests.addTests(unittest.TestLoader().discover(str(folder), pattern=pattern))
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    assert result.wasSuccessful() and result.testsRun == 18
    save(root / 'CPU_PREFLIGHT.json', dict(status='completed', tests=result.testsRun))


def gate(settings, root):
    import torch
    from adapter import SamplingOverride
    from driver import kernel_gate
    from reference import load_model
    from score_reference import save, score, sealed
    from onebit import OnebitOverride
    sys.path.insert(0, settings['runtime'])
    cpu = sealed(root / 'CPU_PREFLIGHT.json')
    assert cpu['status'] == 'completed' and cpu['tests'] == 18
    out = root / 'gate'
    out.mkdir(exist_ok=False)
    inputs, tokens, ledger, plan, tokenizer, tasks, provenance = previous.setup(settings, out)
    old_root = Path(settings['s4_reference_root'])
    old_gate = sealed(old_root / 'gate/RESULT.json')
    assert old_gate['status'] == 'completed'
    for key in ['protocol', 'task_identity', 'harness']:
        assert provenance[key] == old_gate['provenance'][key], key
    integer = kernel_gate()
    model, context, modules, native_identity = load_model(inputs, native=True)
    assert native_identity == old_gate['native_identity']
    bf = score(model, context, modules, tokens, ledger, list(range(292)), 101, out / 'BF16_full')
    assert bf['targets'] == 299077 and abs(bf['ppl'] - old_gate['BF16_full']['ppl']) < .000001
    native = dict(id='BF16', policy='BF16')
    native_checks = []
    for name in tasks:
        a = previous.run_task(model, context, modules, tokenizer, tasks[name], name, native,
                              101, 0, 2, out / f'plain_{name}', plain=True)
        previous.scale_context = lambda p: nullcontext() if p == 'BF16' else scale_context(p)
        b = previous.run_task(model, context, modules, tokenizer, tasks[name], name, native,
                              101, 0, 2, out / f'audited_{name}')
        for key in ['document_identity', 'metrics']:
            assert a[key] == b[key]
        av = sealed(out / f'plain_{name}' / 'OFFICIAL_RESULT.json')['samples'][name]
        bv = sealed(out / f'audited_{name}' / 'OFFICIAL_RESULT.json')['samples'][name]
        assert [x['resps'] for x in av] == [x['resps'] for x in bv]
        native_checks.append(dict(task=name, official_HFLM_scores_bitwise=True))
    del model, context, modules
    gc.collect()
    torch.cuda.empty_cache()
    model, context, modules, identity = load_model(inputs)
    assert identity == old_gate['identity']
    ids = torch.as_tensor(tokens[:128].astype('int64'), device='cuda')[None]
    checks = []
    for case in cases(plan):
        p = SamplingOverride(case)
        p.configure(modules)
        def probe(extra):
            context.seed = 101
            context.begin(0, 0, domain='S2-task-wrapper-check')
            with p, extra, torch.no_grad():
                return model(ids, use_cache=False).logits.detach().clone()
        expected = probe(OnebitOverride(case['policy']))
        actual = probe(TaskFractionOverride(case['policy'], 2))
        assert torch.equal(expected, actual), 'S4 wrapper changed numerical forward'
        s2 = probe(TaskFractionOverride(case['policy'], 1))
        assert torch.equal(s2, probe(TaskFractionOverride(case['policy'], 1)))
        checks.append(dict(case=case['id'], S4_wrapper_bitwise=True, S2_repeat_bitwise=True))
    del ids, expected, actual, s2
    pilots = []
    for case in cases(plan):
        s4case = dict(case, id=f'{case["policy"]}_{case["T_x"]}_{case["T_and"]}')
        for name in tasks:
            previous.scale_context = lambda p: TaskFractionOverride(p, 2)
            z4 = previous.run_task(model, context, modules, tokenizer, tasks[name], name,
                                   s4case, 101, 0, 2, out / f'S4_{s4case["id"]}_{name}')
            old_part = old_root / 'gate' / f'{s4case["id"]}_{name}'
            old_value = sealed(old_part / 'RESULT.json')
            for key in ['document_identity', 'metrics', 'audit']:
                assert z4[key] == old_value[key], key
            current = sealed(out / f'S4_{s4case["id"]}_{name}' / 'OFFICIAL_RESULT.json')['samples'][name]
            original = sealed(old_part / 'OFFICIAL_RESULT.json')['samples'][name]
            assert [x['resps'] for x in current] == [x['resps'] for x in original]
            previous.scale_context = scale_context
            z2 = previous.run_task(model, context, modules, tokenizer, tasks[name], name,
                                   case, 101, 0, 2, out / f'{case["id"]}_{name}')
            assert z2['document_identity'] == z4['document_identity']
            assert z2['audit'] == z4['audit']
            pilots.append(dict(case=case['id'], task=name, S4_old_resps_bitwise=True,
                               S2_documents=2, S2_metrics=z2['metrics']))
    previous.scale_context = scale_context
    save(out / 'RESULT.json', dict(status='completed', tests=cpu['tests'],
         BF16_full=bf, native_identity=native_identity, identity=identity, provenance=provenance,
         native_task_checks=native_checks, integer_kernel_oracle=integer,
         wrapper_checks=checks, pilots=pilots,
         s4_reference_gate_sha256=hashlib.sha256((old_root/'gate/RESULT.json').read_bytes()).hexdigest(),
         job=os.environ['SLURM_JOB_ID'], device=torch.cuda.get_device_name(0)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--settings', type=Path, required=True)
    ap.add_argument('--phase', choices=['cpu', 'gate', 'worker'], required=True)
    a = ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    raw = a.settings.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == a.settings.with_suffix('.sha256').read_text().strip()
    settings = json.loads(raw)
    root = a.settings.parent
    configure_parent()
    import torch
    torch.set_num_threads(4)
    if a.phase == 'cpu':
        preflight(settings, root)
    else:
        assert torch.cuda.is_available() and torch.cuda.device_count() == 1
        if a.phase == 'gate':
            gate(settings, root)
        else:
            previous.worker(settings, root)


if __name__ == '__main__':
    main()
