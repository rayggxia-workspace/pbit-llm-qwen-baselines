"""Small synthetic records test report rejection contracts, never model quality."""
import copy
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('llama2_issue14_report', ROOT/'report.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)
render_spec = importlib.util.spec_from_file_location('llama2_issue14_render', ROOT/'render_report.py')
renderer = importlib.util.module_from_spec(render_spec)
render_spec.loader.exec_module(renderer)


def identity():
    return dict(repository=report.REPOSITORY, revision=report.REVISION, model_shape=report.SHAPE,
                files={name:dict(bytes=1, sha256='1'*64, mirror_revision='fixture-metadata',
                                 official_lfs_match=True) for name in
                       ('config.json', 'tokenizer.json', 'tokenizer.model', 'tokenizer_config.json',
                        'model-00001-of-00002.safetensors', 'model-00002-of-00002.safetensors')})


def raw_record(sampled=False):
    context, possible = 512, 32*32*512
    samples, unique = 32, 32*32*32
    traffic = ({'attention_K_physical_bytes':possible*256,
                'attention_V_gather_physical_bytes':unique*256} if sampled else
               {'attention_KV_fused_physical_bytes':possible*512})
    actions = dict(ATT_possible_QK_tokens=possible, ATT_selected_QK_tokens=possible)
    if sampled:
        actions.update(ATT_V_sample_events=32*32*samples, ATT_V_additions=32*32*samples*128,
                       ATT_V_group_union_rows=unique, ATT_V_unique_head_indices=unique)
    workload = dict(kind=report.REAL_KIND, real_model_trace=True, bf16_capture_bitwise_equal=True,
                    model_identity=identity(), identity_manifest_sha256='2'*64, trace_sha256='3'*64)
    return dict(case='sc_pv' if sampled else 'bf16_dense', context=context, seed=0,
                config=dict(decode_tokens=1, sc_engines=8, samples=4096,
                            attention_v3=dict(trace_file='fixture.trace.json')),
                actual_shape=report.SHAPE, workload=workload, execution_source_commit=report.TLM_COMMIT,
                execution_manifest_sha256='4'*64, quality_reference_ppl=None,
                validation=dict(PPL_measured=False), bounds={}, actions=actions, traffic=traffic,
                energy_J=dict(external_weights=.001), time_ns=dict(FFN_gate_up=2e6),
                metrics=dict(mean_TPOT_ms=2., scenario_mJ_per_token=1., parameterized_area_mm2=40.,
                             area_budget_feasible=True, attention_ms_per_token=0.),
                memory_v5=dict(SRAM={'shared':dict(capacity_bytes=8*2**20, area_mm2=39.)},
                               work_peak_bytes=2**20), external_memory_model={},
                llama_attention=dict(budget_rows=[dict(samples_per_head=samples if sampled else 0,
                                                       context=context) for _ in range(32)],
                                     phase_ms_per_token={}),
                attention_v3=dict(trace=dict(sha256='3'*64)), configuration_sha256='5'*64,
                wall_seconds=.1, source_hashes={'fixture.py':'6'*64})


def baseline_fixture(project):
    ident = identity()
    identity_path = project/'model_identity.json'
    report.write_json(identity_path, ident)
    directory = project/'outputs/bf16_baseline'
    directory.mkdir(parents=True)
    protocol = dict(name='full_wikitext2_raw_sliding_window_ppl', windows=[2048,4096], stride=512,
                    seed=0, batch_size=1, add_special_tokens=False,
                    target_positions='1..N-1 exactly once', precision='BF16 model; FP32 CE; FP64 NLL sum',
                    raw_sha256=report.CORPUS_SHA256)
    tokenization = dict(tokens=5000, expected_scored_tokens=4999, token_ids_sha256='7'*64)
    results = []
    for length in (2048, 4096):
        logs, previous, count = [], 1, 0
        for begin in range(0, 5000, 512):
            end = min(begin + length, 5000)
            start = max(previous, begin + 1)
            count += end-start
            logs.append(dict(number=len(logs)+1, begin=begin, end=end, score_start=start,
                             count=end-start, logits_start=start-begin-1, scored_so_far=count,
                             nll=float(end-start)))
            previous = end
            if end == 5000:
                break
        record = dict(window=length, stride=512, windows=len(logs), corpus_tokens=5000,
                      scored_tokens=count, total_nll=float(count), mean_nll=1., ppl=math.e,
                      wall_seconds=1., peak_allocated_bytes=2**30, peak_reserved_bytes=2**30)
        report.write_json(directory/f'ppl_{length}.json', record)
        with (directory/f'windows_{length}.jsonl').open('x', encoding='utf-8', newline='\n') as handle:
            for item in logs:
                handle.write(json.dumps(item)+'\n')
        results.append(record)
    summary = dict(status='completed', model=report.REPOSITORY, revision=report.REVISION,
                   code_commit=report.BASELINE_COMMIT, data_sha256=report.CORPUS_SHA256,
                   tokenization=tokenization, ppl=results)
    normalized = dict(ident, files={name:{key:record[key] for key in ('sha256','bytes')}
                                   for name,record in ident['files'].items()},
                      manifest_sha256=report.digest(identity_path), use_safetensors=True)
    files = {'summary.json':summary, 'protocol.json':protocol, 'source.json':dict(commit=report.BASELINE_COMMIT),
             'identity.json':normalized, 'environment.json':dict(gpu='synthetic unit-test fixture'),
             'command.json':{}, 'tokenization.json':tokenization}
    for name, content in files.items():
        report.write_json(directory/name, content)
    manifest = {path.name:dict(bytes=path.stat().st_size, sha256=report.digest(path))
                for path in directory.iterdir()}
    report.write_json(directory/'ARTIFACT_MANIFEST.json', manifest)
    return ident, identity_path, directory


class ReportContracts(unittest.TestCase):
    def compact(self, data):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder)/'unit-fixture.json'
            report.write_json(path, data)
            trace = dict(sha256='3'*64, provenance=dict(context=512, model_identity=identity(),
                          identity_manifest_sha256='2'*64))
            with patch.object(report, 'trace_data', return_value=trace):
                return report.compact(path, 'link_Staggered', identity(), '2'*64)

    def test_exact_task_matrix_and_rejections(self):
        rows = [dict(backend=b,context=c,case=k,engines=e,seed=s)
                for b,c,k,e,s in report.expected_keys()]
        report.check_keys(rows)
        self.assertEqual(len(rows),116)
        for bad in (rows[:-1], rows+[rows[0]], rows+[dict(rows[0],context=8192)]):
            with self.assertRaises(ValueError):
                report.check_keys(bad)

    def test_dense_and_sampled_ledgers(self):
        dense = self.compact(raw_record())
        sparse = self.compact(raw_record(True))
        self.assertEqual(dense['K_physical_fraction'],1.)
        self.assertEqual(dense['V_physical_fraction'],1.)
        self.assertEqual(sparse['V_physical_fraction'],1/16)
        self.assertEqual(sparse['samples_per_head'],32)
        self.assertAlmostEqual(sum(sparse['energy_categories_mJ_per_token'].values()),1.)

    def test_old_or_synthetic_identity_rejected(self):
        mutations = [('workload', 'kind', 'REAL_LLAMA1_7B_POST_ROPE_QK_LOGITS'),
                     ('workload', 'kind', 'SYNTHETIC_LLAMA2_SHAPE'),
                     ('actual_shape', 'rms_norm_eps', 1e-6),
                     ('actual_shape', 'max_position_embeddings', 2048)]
        for group,key,value in mutations:
            data = copy.deepcopy(raw_record())
            data[group][key] = value
            with self.subTest(mutation=(group,key,value)), self.assertRaises(ValueError):
                self.compact(data)

    def test_samples_physical_reads_memory_and_energy_rejected(self):
        for kind in ('sample', 'unique', 'Vread', 'energy', 'negative', 'memory', 'PPL', 'source'):
            data = raw_record(True)
            if kind == 'sample': data['actions']['ATT_V_sample_events'] -= 1
            if kind == 'unique': data['actions']['ATT_V_group_union_rows'] -= 1
            if kind == 'Vread': data['traffic']['attention_V_gather_physical_bytes'] += 64
            if kind == 'energy': data['metrics']['scenario_mJ_per_token'] += 1
            if kind == 'negative': data['energy_J']['bad'] = -.001
            if kind == 'memory': data['memory_v5']['work_peak_bytes'] = 9*2**20
            if kind == 'PPL': data['quality_reference_ppl'] = 5.5
            if kind == 'source': data['execution_source_commit'] = '1'*40
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.compact(data)

    def test_baseline_identity_and_n_minus_one(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            project = Path(folder)
            ident, identity_path, directory = baseline_fixture(project)
            result = report.baseline_evidence(project, ident, identity_path)
            self.assertEqual(result['summary']['ppl'][0]['scored_tokens'],4999)
            with (directory/'ppl_2048.json').open('a', encoding='utf-8') as handle:
                handle.write(' ')
            with self.assertRaisesRegex(ValueError,'byte mismatch'):
                report.baseline_evidence(project,ident,identity_path)

    def test_reject_rehashed_incorrect_window_log(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            project = Path(folder)
            ident, identity_path, directory = baseline_fixture(project)
            path = directory/'windows_2048.jsonl'
            rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            rows[1]['score_start'] -= 1
            path.write_text('\n'.join(json.dumps(row) for row in rows)+'\n', encoding='utf-8', newline='\n')
            manifest_path = directory/'ARTIFACT_MANIFEST.json'
            manifest = report.read_json(manifest_path)
            manifest[path.name] = dict(bytes=path.stat().st_size,sha256=report.digest(path))
            manifest_path.write_text(json.dumps(manifest)+'\n', encoding='utf-8', newline='\n')
            with self.assertRaisesRegex(ValueError,'shifted-window'):
                report.baseline_evidence(project,ident,identity_path)

    def test_refuse_output_overwrite_before_read(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            with self.assertRaisesRegex(ValueError,'overwrite'):
                report.collect(SimpleNamespace(project=Path('nonexistent'),output=Path(folder)))

    def test_utf8_render_both_contexts_and_independent_quality(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            project = Path(folder)
            ident, identity_path, _ = baseline_fixture(project)
            evidence = report.baseline_evidence(project, ident, identity_path)
            rows = []
            for backend,context,case,engines,seed in report.expected_keys():
                row = {key:0 for key in report.SCALARS}
                row.update(backend=backend,context=context,case=case,engines=engines,seed=seed,
                           area_feasible=True,ms_per_token=1.,mJ_per_token=2.,
                           energy_categories_mJ_per_token={'DRAM':2.},
                           offline_retained_attention_mass=dict(mean=.75,minimum_head=.25))
                rows.append(row)
            directory = project/'report-fixture'
            directory.mkdir()
            report.write_json(directory/'summary.json',report.summaries(rows))
            report.write_json(directory/'cases.json',rows)
            report.write_json(directory/'BF16_BASELINE.json',evidence)
            report.write_json(directory/'ARTIFACT_INDEX.json',dict(results=116,missing_cases=[],
                completeness_by_backend=dict(link_Staggered=72,dramsys_Staggered=36,dramsys_NoPowerDown=8),
                model_identity=ident,code_commit=report.TLM_COMMIT,baseline_code_commit=report.BASELINE_COMMIT))
            renderer.render(directory)
            rendered = (directory/'RESULTS_ZH.md').read_text(encoding='utf-8')
            self.assertIn('2K 上下文',rendered)
            self.assertIn('4K 上下文',rendered)
            self.assertIn('完整 WikiText-2 滑窗 PPL',rendered)
            self.assertIn('本次没有替换全部 FFN/Attention 后的完整 WT2 PPL',rendered)
            self.assertNotIn('/82',rendered)
            with self.assertRaises(FileExistsError):
                renderer.render(directory)


if __name__ == '__main__':
    unittest.main()
