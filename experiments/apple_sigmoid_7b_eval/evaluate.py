"""Apple six-task zero-shot evaluation and complete once-per-token WT2 PPL."""
from pathlib import Path
import argparse,hashlib,json,math,os,time
import numpy as np
import torch
from model import Gala,Tokenizer
TASKS=['boolq','piqa','hellaswag','winogrande','arc_easy','arc_challenge']
def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n',encoding='utf-8')
def ppl(model,tok,text_path,out):
    raw=text_path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08'
    ids=np.asarray(tok.encode(raw.decode('utf-8')),dtype='<i8')
    total=0.;count=0;previous_end=1;trace=[];started=time.time()
    for begin in range(0,len(ids),1024):
        end=min(begin+2048,len(ids));start=max(previous_end,begin+1)
        inp=torch.as_tensor(ids[None,begin:end-1].copy(),device=model.device)
        logits=model(inp,last_positions=slice(start-begin-1,None))[0].float()
        targets=torch.as_tensor(ids[start:end].copy(),device=model.device)
        losses=torch.nn.functional.cross_entropy(logits,targets,reduction='none')
        assert torch.isfinite(losses).all()
        nll=losses.double().sum().item();n=end-start;total+=nll;count+=n
        trace.append({'begin':begin,'end':end,'target_start':start,'tokens':n,'nll':nll});previous_end=end
        write(out/'ppl_progress.json',{'scored_tokens':count,'corpus_tokens':len(ids),'ppl_so_far':math.exp(total/count),'elapsed_seconds':time.time()-started})
        if end==len(ids):break
    assert count==len(ids)-1 and trace[-1]['end']==len(ids)
    write(out/'ppl.json',{'complete':True,'text_sha256':hashlib.sha256(raw).hexdigest(),'token_ids_sha256':hashlib.sha256(ids.tobytes()).hexdigest(),'corpus_tokens':len(ids),'scored_tokens':count,'nll_sum':total,'mean_nll':total/count,'ppl':math.exp(total/count),'window':2048,'stride':1024,'elapsed_seconds':time.time()-started,'windows':trace})
def harness_model(model,tok):
    from lm_eval.api.model import TemplateLM
    class AppleLM(TemplateLM):
        def __init__(self):
            super().__init__();self.model=model;self.batch_size=4
        @property
        def eot_token_id(self):return tok.sp.eos_id()
        @property
        def tokenizer_name(self):return 'apple-bpe-32k-c4-newline-n'
        def tok_encode(self,string,**kwargs):return tok.encode(string)
        def _encode_pair(self,context,continuation):
            trailing=len(context)-len(context.rstrip())
            if trailing:continuation=context[-trailing:]+continuation;context=context[:-trailing]
            whole=tok.encode(context+continuation);c=tok.encode(context)
            assert whole[:len(c)]==c,('BPE boundary mismatch',context[-80:],continuation[:80])
            r=whole[len(c):];assert c and r
            return c,r
        def _loglikelihood_tokens(self,requests,**kwargs):
            prepared=[]
            for i,(key,context,cont) in enumerate(requests):
                assert 0<len(cont)<=4096
                seq=(context+cont)[-4097:-1];start=len(seq)-len(cont);assert start>=0
                prepared.append((i,seq,cont,start,key))
            prepared.sort(key=lambda x:-len(x[1]));answers=[None]*len(prepared);cursor=0
            while cursor<len(prepared):
                width=len(prepared[cursor][1]);bs=min(4,max(1,2048//width),len(prepared)-cursor)
                group=prepared[cursor:cursor+bs];left=min(x[3] for x in group)
                inp=torch.zeros((bs,width),dtype=torch.long,device=model.device)
                for j,(_,seq,_,_,_) in enumerate(group):inp[j,:len(seq)]=torch.tensor(seq,device=model.device)
                logits=model(inp,last_positions=slice(left,None)).float()
                for j,(idx,seq,cont,start,key) in enumerate(group):
                    z=logits[j,start-left:start-left+len(cont)];target=torch.tensor(cont,device=model.device)
                    ll=-torch.nn.functional.cross_entropy(z,target,reduction='sum').item();assert math.isfinite(ll)
                    answer=(ll,bool(z.argmax(-1).eq(target).all().item()));answers[idx]=answer
                    self.cache_hook.add_partial('loglikelihood',key,answer)
                cursor+=bs
                if cursor%100<bs:print('REQUESTS',cursor,len(prepared),flush=True)
            assert all(x is not None for x in answers)
            return answers
        def loglikelihood_rolling(self,requests,**kwargs):raise NotImplementedError('Use explicit WT2 scorer')
        def generate_until(self,requests,**kwargs):raise NotImplementedError('Six tasks use likelihood scoring')
    return AppleLM()

def run_tasks(model,tok,root,out,limit=None):
    from offline_data import install
    install(root)
    from lm_eval import evaluator
    from lm_eval.tasks import TaskManager
    lm=harness_model(model,tok);manager=TaskManager();scores={}
    for name in TASKS:
        started=time.time()
        result=evaluator.simple_evaluate(model=lm,tasks=[name],num_fewshot=0,batch_size=4,device='cuda',limit=limit,bootstrap_iters=1000,log_samples=True,task_manager=manager,random_seed=0,numpy_random_seed=0,torch_random_seed=0,fewshot_random_seed=0)
        samples=result.pop('samples',{})
        with (out/(name+'_samples.jsonl')).open('w',encoding='utf-8') as f:
            for record in samples.get(name,[]):f.write(json.dumps(record,ensure_ascii=False,default=str)+'\n')
        result['elapsed_seconds']=time.time()-started;write(out/(name+'.json'),result)
        scores[name]=result['results'][name];write(out/'tasks_progress.json',scores)
    if limit is None:
        write(out/'six_task_summary.json',{'complete':True,'tasks':scores,'mean_raw_acc':sum(v['acc,none'] for v in scores.values())/6,'num_fewshot':0,'harness_version':'0.4.8','seed':0})
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--kind',choices=['sigmoid','softmax'],required=True);p.add_argument('--phase',choices=['ppl','tasks','smoke'],required=True);p.add_argument('--dtype',choices=['float32','bfloat16'],default='bfloat16');p.add_argument('--converted-root',type=Path);args=p.parse_args()
    torch.set_grad_enabled(False);torch.manual_seed(0);torch.backends.cuda.matmul.allow_tf32=False
    root=args.root;out=root/'reports'/args.dtype/args.kind;out.mkdir(exist_ok=True,parents=True)
    model=Gala((args.converted_root or root/'converted-v2')/args.kind,args.kind,dtype=getattr(torch,args.dtype));tok=Tokenizer('/home/Weican_Chen/models/apple-sigmoid-attention-7b/tokenizer/bpe_32k_c4.model')
    if args.phase=='ppl':ppl(model,tok,root/'data/wiki.test.raw',out)
    elif args.phase=='tasks':run_tasks(model,tok,root,out)
    else:
        out=out/'smoke';out.mkdir(exist_ok=True);run_tasks(model,tok,root,out,limit=2)
    print('EVALUATION_PHASE_COMPLETE',args.kind,args.phase,flush=True)
if __name__=='__main__':main()
