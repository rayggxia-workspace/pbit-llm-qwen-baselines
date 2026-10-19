"""Llama 2 7B identity, shape, budget and finite-resource contracts (stdlib)."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('llama2_tlm_runner', ROOT / 'run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
from dramsys_backend import AddressSpace


class ModelContract(unittest.TestCase):
    def test_exact_model_parameters_and_distinct_embeddings(self):
        cfg, _, shape, _, _ = runner.build(4096, 0)
        h, m, v, layers = (shape[k] for k in ('hidden_size', 'intermediate_size', 'vocab_size', 'num_hidden_layers'))
        parameter_count = 2*v*h + layers*(4*h*h + 3*h*m + 2*h) + h
        self.assertEqual(parameter_count, 6738415616)
        layout = AddressSpace(shape, 'digital_bf16', 4096, 1)
        parameters = sum(row['logical_bytes'] for name, row in layout.regions.items() if not name.endswith('/KV'))
        self.assertEqual(parameters, parameter_count*2)
        self.assertNotEqual(layout.regions['embedding']['base'], layout.regions['lm_head']['base'])
        self.assertFalse(shape['attention_bias'])
        self.assertEqual(shape['rms_norm_eps'], 1e-5)
        self.assertLess(layout.total_bytes, 16*2**30)

    def test_4k_active_kv_is_2gib_with_explicit_next_slot(self):
        _, _, shape, _, _ = runner.build(4096, 0)
        layout = AddressSpace(shape, 'digital_bf16', 4096, 1)
        self.assertEqual(layout.kv_token_bytes * 4096 * 32, 2*2**30)
        # Shared address space reserves context+decode_tokens, conservatively one
        # future slot beyond the context-1 prefill + one measured decode token.
        reserved = sum(row['logical_bytes'] for name, row in layout.regions.items() if name.endswith('/KV'))
        self.assertEqual(reserved, 2*2**30 + 32*layout.kv_token_bytes)

    def test_native_context_and_proportional_budget(self):
        for context, budget in [(512, 32), (1024, 64), (2048, 128), (4096, 256)]:
            cfg, _, shape, _, _ = runner.build(context, 0)
            self.assertEqual(cfg['attention_v3']['samples'], budget)
            self.assertEqual(shape['max_position_embeddings'], 4096)
        for context, tokens in [(4097, 1), (4096, 2), (1, 1), (4096, 0)]:
            with self.assertRaises(ValueError):
                runner.build(context, 0, tokens=tokens)

    def test_current_rng_sram_and_mha_contract(self):
        cfg, evidence, shape, plan, calibration = runner.build(4096, 0)
        self.assertEqual(shape['num_attention_heads'], shape['num_key_value_heads'])
        self.assertEqual(shape['num_key_value_heads'], 32)
        self.assertEqual(cfg['rng']['input_bits_per_decision'], 8)
        self.assertEqual(cfg['local_shared_input']['share_group'], 64)
        self.assertEqual(cfg['local_shared_input']['state_bits'], 32)
        self.assertEqual(cfg['samples'], 4096)
        self.assertEqual(cfg['sc_engines'], 8)
        self.assertEqual(cfg['weight_macro']['per_weight_validity_bits'], 0)
        self.assertIsNone(cfg['attention_v3']['calibration_file'])
        self.assertEqual(plan['unified_bytes'], 8*2**20)
        self.assertEqual(plan['weight_lanes'], 16)
        self.assertEqual(plan['scratch_lanes'], 16)
        self.assertEqual(plan['fabric_GBs'], 16)
        model = runner._adapter.LlamaLocalDecode(cfg, 'fixed_sc_exact', evidence, shape, calibration, plan)
        self.assertEqual(model.group, 1)
        self.assertEqual(model.work_mem.capacity, 8*2**20)
        self.assertEqual(model.work_mem.period, 12.5)
        self.assertEqual(model.work_mem.lanes, 16)

    def test_synthetic_requires_explicit_opt_in(self):
        _, _, shape, _, _ = runner.build(4096, 0)
        with self.assertRaises(ValueError):
            runner.validate_workload(None, None, False, 4096, 1, shape)
        result = runner.validate_workload(None, None, True, 4096, 1, shape)
        self.assertEqual(result['kind'], 'SYNTHETIC_LLAMA2_SHAPE')
        self.assertFalse(result['real_model_trace'])
        with self.assertRaises(ValueError):
            runner.validate_workload(Path('x'), None, True, 4096, 1, shape)

    def test_formal_trace_rejects_wrong_model_or_missing_bitwise_check(self):
        # Tiny fixture tests provenance validation without serializing 4M logits.
        _, _, shape, _, _ = runner.build(4096, 0)
        shape = copy.deepcopy(shape)
        shape.update(num_hidden_layers=1, num_attention_heads=1, num_key_value_heads=1)
        identity = dict(repository=runner.IDENTITY_REPOSITORY, revision='1'*40,
            model_shape={key: shape[key] for key in runner.SHAPE_KEYS}, files={
                name: dict(sha256='2'*64, bytes=1) for name in
                ('config.json', 'model.safetensors', 'tokenizer.model')})
        with tempfile.TemporaryDirectory(dir=ROOT, prefix='identity_test_') as directory:
            identity_path, trace = (Path(directory)/name for name in ('identity.json', 'trace.json'))
            identity_path.write_text(json.dumps(identity)+'\n', encoding='utf-8', newline='\n')
            provenance = dict(kind=runner.REAL_KIND, model_identity=identity,
                identity_manifest_sha256=runner.sha(identity_path), model_shape=identity['model_shape'],
                context=2, decode_tokens=1, validation=[dict(token=0, bitwise_equal=True, max_abs_difference=0)])
            data = dict(provenance=provenance, rows=[dict(token=0, layer=0, head=0, logits=[0., 1.])])
            def save():
                trace.write_text(json.dumps(data)+'\n', encoding='utf-8', newline='\n')
            save()
            self.assertTrue(runner.validate_workload(trace, identity_path, False, 2, 1, shape)['real_model_trace'])
            for key, wrong in [('kind', 'REAL_LLAMA1_7B_POST_ROPE_QK_LOGITS'),
                               ('model_identity', dict(identity, revision='3'*40)),
                               ('identity_manifest_sha256', '4'*64), ('context', 3),
                               ('validation', [dict(token=0, bitwise_equal=False, max_abs_difference=0)])]:
                correct = provenance[key]
                provenance[key] = wrong
                save()
                with self.assertRaises(ValueError, msg=key):
                    runner.validate_workload(trace, identity_path, False, 2, 1, shape)
                provenance[key] = correct

    def test_declared_task_counts_and_no_array_sensitivity_mixed_in(self):
        sweep_spec = importlib.util.spec_from_file_location('llama2_tlm_sweep', ROOT / 'sweep.py')
        sweep = importlib.util.module_from_spec(sweep_spec)
        sweep_spec.loader.exec_module(sweep)
        self.assertEqual(len(sweep.tasks('link')), 72)
        self.assertEqual(len(sweep.tasks('dramsys')), 36)
        self.assertEqual({r['context'] for r in sweep.tasks('link')}, {512, 1024, 2048, 4096})
        self.assertEqual({r['engines'] for r in sweep.tasks('link')}, {8})


if __name__ == '__main__':
    unittest.main()
