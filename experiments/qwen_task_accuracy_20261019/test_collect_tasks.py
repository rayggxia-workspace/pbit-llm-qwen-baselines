"""Meaningful stdlib-only collector contracts; all fixtures are synthetic."""
import copy
import hashlib
import json
from pathlib import Path
import statistics
import tempfile
import unittest

from . import collect_tasks as c


class CollectorTest(unittest.TestCase):
    def setUp(self):
        # Explicit personal workspace location, never shared host /tmp.
        self.temp = tempfile.TemporaryDirectory(prefix='collector-fixture-', dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.commit = 'a' * 40
        self.cfgs = c.expected_configurations()
        stats = {}
        identities = {}
        for task, (full, count, checksum) in c.TASKS.items():
            ids = c.document_ids(task)
            stats[task] = dict(documents=count, full_split_documents=full,
                selected_doc_ids_sha256=hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest())
            identities[task] = dict(documents=full,dataset_sha256=checksum)
        self.meta = dict(code_commit=self.commit, statistics=stats, tasks=identities,
            source_sha256={'run_tasks.py':'b'*64},harness_version='0.4.8',num_fewshot=0,
            chat_template=False,tokenized={})
        self.suite = dict(configurations=self.cfgs,tasks=list(c.TASKS),count=39,task_statistics=stats)
        self.write('identity.json',dict(synthetic=True))
        self.write('TASK_DATA.json',self.meta)
        self.write('suite.json',self.suite)
        self.ready = dict(code_commit=self.commit,source_sha256=self.meta['source_sha256'],
            baseline_gate_passed=True,bf16_task_bridge_passed=True,
            task_data_sha256=c.sha(self.root/'TASK_DATA.json'),suite_sha256=c.sha(self.root/'suite.json'),
            identity_sha256=c.sha(self.root/'identity.json'))
        self.write('READY.json',self.ready)
        (self.root/'full').mkdir()

    def write(self,relative,value):
        path=self.root/relative
        path.write_text(json.dumps(value,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')

    def rows(self, task='piqa', flips=()):
        choices=2 if task=='piqa' else 4
        return [dict(id=f'{task}:{i}',task=task,doc_id=i,
            choices=[dict(logprob=-float(k+1),tokens=1,is_greedy=False)for k in range(choices)],
            metrics=dict(acc=float((i%2==0) != (i in flips)),acc_norm=float(i%3==0)))
            for i in c.document_ids(task)]

    def jsonl(self,path,rows):
        path.write_text(''.join(json.dumps(r,separators=(',',':'))+'\n'for r in rows),encoding='utf-8',newline='\n')

    def case(self,name='bf16',task='piqa',flips=()):
        cfg=next(x for x in self.cfgs if x['name']==name)
        rows=self.rows(task,flips)
        stem=f'{task}_{name}'
        dp=self.root/'full'/f'{stem}.documents.jsonl'
        self.jsonl(dp,rows)
        result=dict(configuration=cfg,case=c.normalized_case(copy.deepcopy(cfg)),code_commit=self.commit,status='completed',
            task=task,n_documents=len(rows),
            metrics={m:statistics.mean(r['metrics'][m]for r in rows)for m in c.METRICS},
            configuration_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),
            task_data_sha256=c.sha(self.root/'TASK_DATA.json'),
            document_artifact=dict(path='/remote/frozen/full/'+dp.name,sha256=c.sha(dp),bytes=dp.stat().st_size),
            execution_audit=dict(every_scored_target_used_24_decode_layers=True,
                original_tokenized_requests=sum(x['tokens']for r in rows for x in r['choices'])),
            active_sampling_stats=None,elapsed_seconds=1.0)
        rp=self.root/'full'/f'{stem}.json'
        self.write(rp,result)
        return rp,dp,result

    def reseal(self,rp,dp,result):
        result['document_artifact'].update(sha256=c.sha(dp),bytes=dp.stat().st_size)
        self.write(rp,result)

    def test_pending_is_not_zero_and_no_full_task_claim(self):
        report=c.collect(self.root,self.commit)
        self.assertEqual(report['n_completed_cases'],0)
        self.assertEqual(report['n_pending_cases'],39)
        self.assertIsNone(report['groups'][0]['metrics'])
        self.assertIn('非完整HellaSwag',report['groups'][-1]['split'])
        self.assertIn('待完成',c.render_chinese(report))

    def test_three_seed_mean_std_and_doc_paired_transitions(self):
        self.case()
        self.case('joint_S64_s0',flips=(0,1))
        self.case('joint_S64_s1',flips=(0,))
        self.case('joint_S64_s2')
        report=c.collect(self.root,self.commit)
        group=next(x for x in report['groups']if x['task']=='piqa'and x['group']=='joint_S64')
        self.assertEqual(group['state'],'completed')
        self.assertEqual(group['completed_seeds'],[0,1,2])
        self.assertAlmostEqual(group['metrics']['acc']['mean'],.5-1/(1838*3))
        self.assertGreater(group['metrics']['acc']['std'],0)
        row=next(x for x in report['cases']if x['case']=='joint_S64_s0')
        self.assertEqual(row['paired_vs_bf16']['acc']['correct_to_wrong'],1)
        self.assertEqual(row['paired_vs_bf16']['acc']['wrong_to_correct'],1)
        self.assertEqual(row['delta_pp_vs_bf16']['acc'],0)

    def test_full_case_without_new_baseline_keeps_delta_pending(self):
        self.case('ffn_only_s0')
        report=c.collect(self.root)
        self.assertIsNone(report['cases'][0]['delta_pp_vs_bf16'])
        group=next(x for x in report['groups']if x['task']=='piqa'and x['group']=='ffn_only')
        self.assertEqual(group['state'],'partial_seeds')
        self.assertIsNone(group['delta_pp_vs_bf16'])

    def test_partial_is_separate_and_reports_denominator(self):
        path=self.root/'full/piqa_joint_S128_s0.progress.jsonl'
        self.jsonl(path,self.rows()[:7])
        report=c.collect(self.root)
        self.assertEqual(report['n_completed_cases'],0)
        self.assertEqual(report['partial_task_progress'][0]['n_documents'],7)
        self.assertEqual(report['partial_task_progress'][0]['n_expected_documents'],1838)
        self.assertNotIn('delta_pp_vs_bf16',report['partial_task_progress'][0])

    def test_bad_document_sha_rejected(self):
        _,dp,_=self.case()
        with dp.open('a',encoding='utf-8')as f:f.write(' \n')
        with self.assertRaisesRegex(ValueError,'SHA-256'):c.collect(self.root)

    def test_resealed_duplicate_id_still_rejected(self):
        rp,dp,result=self.case()
        rows=self.rows();rows[-1]=rows[0]
        self.jsonl(dp,rows);self.reseal(rp,dp,result)
        with self.assertRaisesRegex(ValueError,'Duplicate document'):c.collect(self.root)

    def test_resealed_truncated_task_still_rejected(self):
        rp,dp,result=self.case()
        self.jsonl(dp,self.rows()[:-1]);self.reseal(rp,dp,result)
        with self.assertRaisesRegex(ValueError,'Missing/truncated'):c.collect(self.root)

    def test_resealed_unterminated_jsonl_rejected(self):
        rp,dp,result=self.case()
        dp.write_bytes(dp.read_bytes().rstrip(b'\n'));self.reseal(rp,dp,result)
        with self.assertRaisesRegex(ValueError,'Truncated JSONL'):c.collect(self.root)

    def test_configuration_identity_rejected(self):
        rp,_,result=self.case()
        result['configuration']['samples']=64
        self.write(rp,result)
        with self.assertRaisesRegex(ValueError,'Configuration mismatch'):c.collect(self.root)

    def test_aggregate_not_trusted(self):
        rp,_,result=self.case()
        result['metrics']['acc']=.4
        self.write(rp,result)
        with self.assertRaisesRegex(ValueError,'Aggregate/document'):c.collect(self.root)

    def test_preparation_hash_and_expected_commit(self):
        with self.assertRaisesRegex(ValueError,'Unexpected frozen'):c.collect(self.root,'c'*40)
        self.meta['num_fewshot']=1
        self.write('TASK_DATA.json',self.meta)
        with self.assertRaisesRegex(ValueError,'Preparation SHA'):c.collect(self.root)

    def test_hellaswag_selection_is_not_arbitrary_1000(self):
        rp,dp,result=self.case(task='hellaswag')
        rows=self.rows('hellaswag')
        missing=next(i for i in range(10042)if i not in set(c.document_ids('hellaswag')))
        rows[0]['doc_id']=missing;rows[0]['id']=f'hellaswag:{missing}'
        self.jsonl(dp,rows);self.reseal(rp,dp,result)
        with self.assertRaisesRegex(ValueError,'Unexpected document ID'):c.collect(self.root)

    def test_completed_progress_disagreement_rejected(self):
        self.case()
        rows=self.rows()[:1];rows[0]['metrics']['acc']=0.
        self.jsonl(self.root/'full/piqa_bf16.progress.jsonl',rows)
        with self.assertRaisesRegex(ValueError,'Completed/progress'):c.collect(self.root)

    def test_false_real_decode_audit_rejected(self):
        rp,_,result=self.case()
        result['execution_audit']['every_scored_target_used_24_decode_layers']=False
        self.write(rp,result)
        with self.assertRaisesRegex(ValueError,'24-layer decode'):c.collect(self.root)

    def test_unrecognized_extra_result_is_not_silently_ignored(self):
        self.write('full/piqa_joint_S64_s00.json',{})
        with self.assertRaisesRegex(ValueError,'Unknown/duplicate case'):c.collect(self.root)


if __name__=='__main__':
    unittest.main()
