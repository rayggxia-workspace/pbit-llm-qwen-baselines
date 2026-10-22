import copy,hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import collect_checkpoint as c


class CheckpointContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.environ['PBIT_TEST_TMPDIR'])
        self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)/'piqa_bf16.json'
        self.cfg=dict(name='bf16',mode='sdpa',ffn='none');self.meta=dict(task_data_sha256='data',identity_sha256='model')
        self.requests=[dict(id='piqa:'+str(i),choices_ids=[[1],[2]]) for i in range(2)]
        self.docs=[dict(id='piqa:'+str(i),doc_id=i,task='piqa',choices=[dict(tokens=1,is_greedy=False,logprob=-1.),dict(tokens=1,is_greedy=False,logprob=-2.)],metrics=dict(acc=float(i),acc_norm=float(i))) for i in range(2)]
        audit=dict(actual_decode_calls=1,actual_prefill_calls=1,every_scored_target_used_32_decode_layers=True,
            shared_first_query_rows=2,branch_query_rows=0,dummy_query_rows=0,actual_decode_query_rows=2,
            original_tokenized_requests=4,scored_choice_tokens=4,completed_documents=2)
        for key in ['attention_decode','ffn_decode','attention_prefill','ffn_prefill']:audit[key+'_calls_per_layer']=[1]*32
        self.result=dict(status='completed',task='piqa',configuration=self.cfg,code_commit='commit',
            configuration_sha256=hashlib.sha256(json.dumps(self.cfg,sort_keys=True).encode()).hexdigest(),
            n_documents=2,execution_audit=audit,metrics=dict(acc=.5,acc_norm=.5),elapsed_seconds=1.,slurm_job_id='test',**self.meta)
        self.save()

    def save(self):
        p=self.path.with_suffix('.documents.jsonl');p.write_text(''.join(json.dumps(d)+'\n' for d in self.docs),encoding='utf-8',newline='\n')
        self.result['document_artifact']=dict(path=str(p),bytes=p.stat().st_size,sha256=c.sha(p))
        self.path.write_text(json.dumps(self.result),encoding='utf-8')

    def check(self):
        with patch.dict(c.COUNTS,{'piqa':2},clear=True):return c.checked_result(self.path,'piqa',self.cfg,'commit',self.meta,self.requests)

    def test_valid_seal_and_aggregation(self):self.assertTrue(self.check()['metadata_and_32_layers_verified'])

    def test_modified_documents_rejected(self):
        with self.path.with_suffix('.documents.jsonl').open('a') as f:f.write('\n')
        with self.assertRaisesRegex(ValueError,'documents seal'):self.check()

    def test_duplicate_documents_rejected(self):
        self.docs[1]=copy.deepcopy(self.docs[0]);self.save()
        with self.assertRaisesRegex(ValueError,'missing/duplicate'):self.check()

    def test_24_layer_audit_rejected(self):
        self.result['execution_audit']['attention_decode_calls_per_layer']=[1]*24;self.save()
        with self.assertRaisesRegex(ValueError,'layer calls'):self.check()

    def test_partial_seed_does_not_become_completed(self):
        self.result['status']='running';self.save()
        with self.assertRaisesRegex(ValueError,'not sealed'):self.check()

    def test_stale_aggregate_rejected(self):
        self.result['metrics']['acc']=.75;self.save()
        with self.assertRaisesRegex(ValueError,'metric aggregation'):self.check()

    def test_duplicate_json_key_rejected(self):
        with self.assertRaisesRegex(ValueError,'duplicate JSON key'):c.loads('{"x":1,"x":2}')


if __name__=='__main__':unittest.main()
