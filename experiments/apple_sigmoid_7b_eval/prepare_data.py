"""Pin and cache six task datasets on a CPU allocation before GPU evaluation."""
from pathlib import Path
import hashlib,json,os
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
ROOT=Path('/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019')
os.environ['HF_HOME']=str(ROOT/'cache/huggingface')
import datasets
from offline_data import install

TASKS=['boolq','piqa','hellaswag','winogrande','arc_easy','arc_challenge']
manifest=install(ROOT)
original=datasets.load_dataset

def pinned_load(path,*args,**kwargs):
    # A task's own requested revision takes priority; otherwise freeze live hub SHA.
    result=original(path,*args,**kwargs)
    key=path+'::'+str(args[0] if args else kwargs.get('name',''))
    revision=manifest[key]['revision']
    rows={k:{'rows':len(v),'fingerprint':v._fingerprint} for k,v in result.items()} if isinstance(result,datasets.DatasetDict) else {'rows':len(result),'fingerprint':result._fingerprint}
    parts=result.values() if isinstance(result,datasets.DatasetDict) else [result]
    files=[]
    for ds in parts:
        for row in ds.cache_files:
            f=Path(row['filename']).resolve()
            assert f.is_relative_to(ROOT.resolve()),f
            h=hashlib.sha256()
            with f.open('rb') as stream:
                for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
            files.append({'path':str(f),'bytes':f.stat().st_size,'sha256':h.hexdigest()})
    manifest[key]={'path':path,'name':args[0] if args else kwargs.get('name'), 'revision':revision,'splits':rows,'files':files}
    (ROOT/'reports/dataset_revisions.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return result

datasets.load_dataset=pinned_load
from lm_eval.tasks import TaskManager,get_task_dict
tasks=get_task_dict(TASKS,task_manager=TaskManager())
configs={k:v.dump_config() for k,v in tasks.items()}
(ROOT/'reports/task_configs.json').write_text(json.dumps(configs,indent=2,default=str)+'\n')
wt=pinned_load('Salesforce/wikitext','wikitext-2-raw-v1',split='test')
text=''.join(x if x else ' \n' for x in wt['text'])
raw=text.encode('utf-8');digest=hashlib.sha256(raw).hexdigest()
assert digest=='173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08',digest
dest=ROOT/'data/wiki.test.raw';dest.parent.mkdir(exist_ok=True,parents=True);dest.write_bytes(raw)
(ROOT/'reports/data_status.json').write_text(json.dumps({'state':'COMPLETED','tasks':TASKS,'wikitext_sha256':digest,'wikitext_bytes':len(raw),'job_id':os.environ.get('SLURM_JOB_ID')},indent=2)+'\n')
print('DATA_PREPARED',flush=True)
