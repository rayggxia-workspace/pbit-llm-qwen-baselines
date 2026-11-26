"""Official pinned lm-eval task loading and full-sequence FFN coverage audit."""
from pathlib import Path
import hashlib
import importlib.metadata
import inspect
import json
from types import SimpleNamespace,MethodType
import torch
from lm_eval.models.huggingface import HFLM


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_tasks(data_root,plan):
    from lm_eval.tasks import TaskManager
    assert importlib.metadata.version('lm_eval')=='0.4.8'
    manager=TaskManager();tasks={};identity={}
    for name,config in plan['tasks'].items():
        path=data_root/name/'0000.parquet'
        assert digest(path)==config['sha256'],name
        split=config['split']
        override=dict(task=name,dataset_path='parquet',dataset_name=None,
            training_split=None,validation_split=split if split=='validation' else None,
            test_split=split if split=='test' else None,num_fewshot=0,fewshot_split=split,
            dataset_kwargs={'data_files':{split:str(path)}})
        task=manager.load_task_or_group([override])[name]
        task.set_fewshot_seed(plan['seed'])
        assert len(task.eval_docs)==config['count']
        tasks[name]=task
        identity[name]={'dataset_sha256':digest(path),'split':split,'documents':len(task.eval_docs),
            'official_yaml_sha256':digest(Path(manager.task_index[name]['yaml_path'])),
            'num_fewshot':0}
    paths={Path(inspect.getfile(HFLM)),Path(inspect.getfile(type(next(iter(tasks.values())))))}
    return tasks,identity,{p.name:digest(p) for p in paths}


def audit_requests(task,name,tokenizer):
    encoder=SimpleNamespace(tokenizer=tokenizer,backend='causal',add_bos_token=False)
    encoder.tok_encode=MethodType(HFLM.tok_encode,encoder)
    h=hashlib.sha256();documents=0;requests=0;maximum=0
    for index,doc in task.doc_iterator():
        context=task.fewshot_context(doc,num_fewshot=0)
        for request in task.construct_requests(doc,context,metadata=(name,index,1)):
            assert request.request_type=='loglikelihood'
            ctx,answer=request.args
            if ctx:c,a=HFLM._encode_pair(encoder,ctx,answer)
            else:c,a=[tokenizer.eos_token_id],encoder.tok_encode(answer)
            assert c and a and len(c)+len(a)<=2049,'no implicit context truncation allowed'
            h.update((json.dumps([name,index,c,a],separators=(',',':'))+'\n').encode())
            requests+=1;maximum=max(maximum,len(c)+len(a)-1)
        documents+=1
    return {'documents':documents,'requests':requests,'max_forward_tokens':maximum,
            'tokenized_official_requests_sha256':h.hexdigest(),'truncation':False}


class AuditedHFLM(HFLM):
    def __init__(self,model,tokenizer,context,seed,task_name,progress=None):
        self.context=context;self.seed=seed;self.domain='pruning-task-'+task_name
        self.calls=0;self.tokens=0;self.ledger=[];self.progress=progress
        super().__init__(pretrained=model,tokenizer=tokenizer,backend='causal',batch_size=1,
            max_length=2048,add_bos_token=False,logits_cache=False,truncation=False)

    def _model_call(self,inps,attn_mask=None,labels=None):
        assert labels is None and attn_mask is None and inps.shape[0]==1
        index=self.calls
        self.context.seed=self.seed
        self.context.begin(0,index,domain=self.domain)
        logits=super()._model_call(inps,attn_mask=attn_mask,labels=labels)
        coverage=self.context.coverage
        count=inps.numel()
        assert len(coverage)==36 and all(v['calls']==1 and v['tokens']==count for v in coverage.values())
        self.calls+=1;self.tokens+=count
        self.ledger.append({'call':index,'shape':list(inps.shape),
            'input_ids_sha256':hashlib.sha256(inps.detach().cpu().numpy().astype('<i8').tobytes()).hexdigest()})
        if self.progress and self.calls%100==0:self.progress(self)
        return logits

    def audit(self):
        data=(json.dumps(self.ledger,separators=(',',':'))+'\n').encode()
        return {'model_calls':self.calls,'input_tokens_per_layer':self.tokens,'layers':36,
                'all_prompt_and_answer_positions_covered':True,'prefix_exception':False,
                'input_batch_ledger_sha256':hashlib.sha256(data).hexdigest(),'input_batch_ledger':self.ledger,
                'RNG_key':'seed101 + task_name + official model-call index; identical call ordering across paired cases'}


def evaluate(lm,task,name,limit=None):
    from lm_eval import evaluator
    return evaluator.evaluate(lm=lm,task_dict={name:task},limit=limit,bootstrap_iters=0,
        cache_requests=False,rewrite_requests_cache=False,write_out=True,log_samples=True,
        apply_chat_template=False,fewshot_as_multiturn=False)


def metrics(value,name):
    return {k:float(v) for k,v in value['results'][name].items()
            if k in ['acc,none','acc_norm,none']}
