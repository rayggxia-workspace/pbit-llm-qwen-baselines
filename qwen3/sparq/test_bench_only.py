"""Small provenance, freeze and boundary tests; no Torch/model/GPU required."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from . import bench_only as b


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False) + '\n', encoding='utf-8')


def benchmark():
    return dict(contexts=b.SCHEDULE['contexts'], decode_lengths=b.SCHEDULE['decode_lengths'],
        modes=b.SCHEDULE['modes'], measured_repeats=3, warmup_trials_per_case_mode=1,
        attention_config=b.CONFIG, original_ffn_guard_passed=True,
        trials=[dict(context_tokens=c, decode_steps=d, mode=m, repeat=r, batch=1,
                     last_decode_logits_finite=True)
                for c in b.SCHEDULE['contexts'] for d in b.SCHEDULE['decode_lengths']
                for m in b.SCHEDULE['modes'] for r in range(3)],
        source_files_sha256={'qwen3/sparq/'+name: '1'*64 for name in ('benchmark.py','core.py','adapter.py')})


def parent_fixture(root):
    parent = dict(model=b.MODEL, revision=b.REVISION, config=b.CONFIG, seed=0, original_ffn=True,
                  execution=dict(commit='a'*40, files={name:'1'*64 for name in b.REQUIRED}))
    path = root / 'results/parent'
    save(path / 'IDENTITY.json', parent)
    def result(name, value):
        save(path / (name+'.json'), dict(experiment=b.fingerprint(parent), result=value,
                                       result_sha256=b.fingerprint(value)))
    result('preflight', dict(passed=True))
    result('benchmark', benchmark())
    execution = dict(commit='b'*40, files=dict(parent['execution']['files']))
    execution['files']['qwen3/sparq/benchmark.py']='2'*64
    return parent, path, execution


def asset_fixture(root):
    rows=[]
    for name in sorted(b.MODEL_FILES):
        path=root/'model'/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(('tiny fixture '+name).encode())
        rows.append(dict(name=name,bytes=path.stat().st_size,sha256=b.sha(path)))
    corpus=root/'data/wikitext-2/wiki.test.raw'
    corpus.parent.mkdir(parents=True)
    corpus.write_bytes(b'fixed test text\n')
    ready=dict(model=b.MODEL,revision=b.REVISION,shape=b.SHAPE,files=rows,
               data=[dict(path=str(corpus),bytes=corpus.stat().st_size,sha256=b.sha(corpus))])
    save(root/'prepared/READY.json',ready)
    return ready,dict(ready_sha256=b.sha(root/'prepared/READY.json'))


class BenchSupplementTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_allocation_guard_before_torch_import(self):
        with patch.dict('os.environ',{},clear=True),patch('builtins.__import__') as imports:
            with self.assertRaisesRegex(RuntimeError,'allocation'): b.run(None)
            imports.assert_not_called()

    def test_parent_anchors_identity_and_all_three_artifacts(self):
        parent,path,execution=parent_fixture(self.root)
        got,old,receipt=b.validate_parent(self.root,path,b.sha(path/'IDENTITY.json'),execution)
        self.assertEqual(got,parent)
        self.assertEqual(len(old['trials']),54)
        self.assertEqual(receipt['quality_source_commit'],'a'*40)
        with self.assertRaisesRegex(ValueError,'IDENTITY'):
            b.validate_parent(self.root,path,'0'*64,execution)
        value=json.loads((path/'benchmark.json').read_text(encoding='utf-8'))
        value['result']['measured_repeats']=0
        save(path/'benchmark.json',value)
        with self.assertRaisesRegex(ValueError,'integrity'):
            b.validate_parent(self.root,path,b.sha(path/'IDENTITY.json'),execution)

    def test_changed_numerics_cannot_masquerade_as_measurement_fix(self):
        _,path,execution=parent_fixture(self.root)
        execution['files']['qwen3/sparq/core.py']='f'*64
        with self.assertRaisesRegex(ValueError,'numerical dependency'):
            b.validate_parent(self.root,path,b.sha(path/'IDENTITY.json'),execution)

    def test_missing_or_duplicate_trial_is_not_complete(self):
        good=benchmark();b.validate_benchmark(good)
        for rows in ([],good['trials'][:-1],good['trials'][:-1]+[good['trials'][0]]):
            bad=copy.deepcopy(good);bad['trials']=rows
            with self.assertRaises(ValueError): b.validate_benchmark(bad)
        bad=copy.deepcopy(good);bad['trials'][0]['batch']=2
        with self.assertRaises(ValueError): b.validate_benchmark(bad)

    def test_all_ten_model_files_and_corpus_verified(self):
        _,parent=asset_fixture(self.root)
        ready,path=b.verify_assets(self.root,parent)
        self.assertEqual(len(ready['files']),10)
        self.assertEqual(path.name,'wiki.test.raw')
        target=self.root/'model/model-00003-of-00003.safetensors'
        content=target.read_bytes();target.write_bytes(content[:-1]+b'x')
        with self.assertRaisesRegex(ValueError,'model/tokenizer bytes'): b.verify_assets(self.root,parent)

    def test_missing_model_or_duplicate_ready_entry_is_rejected(self):
        ready,parent=asset_fixture(self.root)
        ready['files'][-1]=ready['files'][0]
        save(self.root/'prepared/READY.json',ready)
        parent['ready_sha256']=b.sha(self.root/'prepared/READY.json')
        with self.assertRaisesRegex(ValueError,'10 pinned'): b.verify_assets(self.root,parent)

    def test_ready_and_raw_corpus_are_independently_bound(self):
        _,parent=asset_fixture(self.root)
        (self.root/'data/wikitext-2/wiki.test.raw').write_bytes(b'changed\n')
        with self.assertRaisesRegex(ValueError,'WikiText'): b.verify_assets(self.root,parent)
        parent['ready_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'READY'): b.verify_assets(self.root,parent)

    def test_token_hash_covers_entire_corpus_and_shape(self):
        from ..stochastic.vendor.scoring import ids_sha256
        class IDs:
            ndim=1
            def __init__(self,values): self.values=values
            def numel(self): return len(self.values)
            def tolist(self): return self.values
        values=list(range(2200));ids=IDs(values)
        parent=dict(tokens_sha256=ids_sha256(values))
        old=dict(token_ids_shape=[1,2200],token_ids_shape_and_le_int64_sha256=
                 hashlib.sha256(struct.pack('<QQ',1,2200)+b''.join(struct.pack('<q',v) for v in values)).hexdigest())
        b.validate_tokens(ids,parent,old)
        values[-1]=4
        with self.assertRaisesRegex(ValueError,'tokenization'): b.validate_tokens(ids,parent,old)

    def test_source_manifest_exact_set_and_bytes(self):
        files={}
        for name in b.BUNDLE_FILES:
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(name.encode())
            files[name]=b.sha(path)
        manifest=dict(purpose='benchmark_supplement',commit='a'*40,files=files)
        b.validate_manifest(self.root,manifest)
        bad=copy.deepcopy(manifest);bad['files'].pop('qwen3/sparq/bench_only.py')
        with self.assertRaisesRegex(ValueError,'dependencies'): b.validate_manifest(self.root,bad)
        (self.root/'qwen3/sparq/adapter.py').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'digest differs'): b.validate_manifest(self.root,manifest)

    def test_freeze_real_git_committed_bytes_and_no_overwrite(self):
        repo=self.root/'repo';repo.mkdir()
        def git(*args):
            return subprocess.run(['git','-C',str(repo),*args],capture_output=True,check=True)
        git('init','--quiet')
        for name in b.BUNDLE_FILES:
            path=repo/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'public source\n')
        git('add','--all')
        git('-c','user.name=fixture','-c','user.email=fixture@example.invalid','commit','--quiet','-m','fixture')
        out=self.root/'bundle'
        result=b.freeze(repo,out)
        self.assertEqual(len(result['files']),13)
        self.assertEqual((out/'qwen3/sparq/core.py').read_bytes(),b'public source\n')
        with self.assertRaisesRegex(ValueError,'already exists'): b.freeze(repo,out)
        (repo/'qwen3/sparq/core.py').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'commit'): b.freeze(repo,self.root/'dirty')
        self.assertFalse((self.root/'dirty').exists())

    def test_output_never_uses_quality_directory(self):
        parent,path,execution=parent_fixture(self.root)
        output=b.output_path(self.root,execution,parent,'999')
        self.assertTrue(output.is_relative_to(self.root/'benchmark_supplements'))
        self.assertFalse(output.is_relative_to(path))
        with self.assertRaises(ValueError): b.output_path(self.root,execution,parent,'../results')
        with self.assertRaises(ValueError): b.inside(self.root.parent,self.root)

    def test_report_transfer_hashes_and_repeatable_repair(self):
        parent,path,execution=parent_fixture(self.root)
        identity=dict(parent={'quality_source_commit':'a'*40},model=b.MODEL,revision=b.REVISION,
            measuring_execution=execution,job='999',gpu_uuid='bare-uuid',gpu_name='mock',environment={},
            ready_sha256='c'*64,verified_corpus_sha256='d'*64,
            verified_model_files=[],tokens_sha256='f'*64)
        result=benchmark();result.update(timing_protocol='mock',scope='mock',nvml_gpu_uuid=None,
            nvml_unavailable_reason='not measured',summaries=[])
        completed=dict(benchmark=result,power_status='unavailable',power_windows_available=0)
        save(path/'benchmark_supplement.json',completed)
        report=b.write_report(path,identity,completed,save)
        self.assertFalse(report['quality_evaluation_complete'])
        self.assertIsNone(report['physical_asic_ppa'])
        self.assertEqual(report['ready_sha256'],'c'*64)
        self.assertEqual(report['verified_corpus_sha256'],'d'*64)
        self.assertEqual(report['transfer_artifacts']['benchmark_supplement.json']['sha256'],b.sha(path/'benchmark_supplement.json'))
        before=(path/'report.json').read_bytes()
        b.write_report(path,identity,completed,save)
        self.assertEqual((path/'report.json').read_bytes(),before)
        self.assertEqual(b.read_json(path/'report.sha256.json')['sha256'],b.sha(path/'report.json'))


if __name__=='__main__':
    unittest.main()
