"""Observe the frozen cached scorer; no numerical/sampling changes."""
from pathlib import Path
import hashlib,json,sys,time

def write(path,value):
    temporary=path.with_suffix('.pending')
    temporary.write_bytes((json.dumps(value,indent=2)+'\n').encode())
    temporary.replace(path)

def main():
    manifest=Path(__file__).with_name('MANIFEST.json')
    metadata=json.loads(manifest.read_bytes())
    source=Path(metadata['frozen_source'])
    for name,digest in metadata['frozen_files'].items():
        assert hashlib.sha256((source/name).read_bytes()).hexdigest()==digest,name
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==metadata['driver_sha256']
    sys.path.insert(0,str(source))
    from experiments.sparq_ising_20261028.vendor.plans import full_window_plan,plan_batches,plan_metadata
    plan=full_window_plan(299078,2048,1024)
    batches=list(plan_batches(plan,8))
    query_calls=sum(group[0]['scored_tokens'] for group in batches)
    assert len(plan)==292 and sum(x['scored_tokens'] for x in plan)==299077
    runroot=manifest.parent
    write(runroot/'PLAN_CHECK.json',dict(status='PASS',windows=292,targets=299077,
        batched_single_token_calls=query_calls,batches=len(batches),batch=8,
        plan=plan_metadata(plan,299078,'full')))
    import torch
    from joint_attention import AttentionPatch
    from experiments.sparq_ising_20261028.vendor import kernels
    # Full WT2 starts with a one-token cache; the suffix gate started at2K.
    with AttentionPatch(True):
        z=torch.zeros((2,1),device='cuda')
        indices,stats=kernels.sample(z,64,'winner',burn=0,seed=101)
        assert bool((indices==0).all()) and bool((stats[:,1]==64).all())
        write(runroot/'ONE_TOKEN_GATE.json',dict(status='PASS',rows=2,candidates=1,samples=64,
            address_zero_only=True,consumes_FFN_RNG=False))
    import run
    original_score=run.score
    def observed_score(*args,**kwargs):
        model=args[0]
        started=time.monotonic()
        activity=dict(model_calls=0,decode_calls=0,decode_targets=0,prefill_calls=0,prefill_tokens=0)
        def observer(module,inputs,output):
            b,n=inputs[0].shape
            activity['model_calls']+=1
            if n==1:
                activity['decode_calls']+=1;activity['decode_targets']+=b
            else:
                activity['prefill_calls']+=1;activity['prefill_tokens']+=b*n
            if activity['model_calls']%128==0:
                elapsed=time.monotonic()-started
                remaining=max(0,query_calls-activity['decode_calls'])
                estimate=elapsed*remaining/activity['decode_calls'] if activity['decode_calls'] else None
                write(runroot/'ACTIVITY_PROGRESS.json',dict(activity,elapsed_seconds=elapsed,
                    total_decode_calls=query_calls,total_targets=299077,
                    estimated_remaining_seconds=estimate,scoring_completed=False,
                    timing_scope='host wall time,includes prefill;not ASIC timing'))
        handle=model.register_forward_hook(observer)
        try:
            result=original_score(*args,**kwargs)
            assert result['targets']==299077 and result['plan']['every_full_corpus_target_once']
            assert result['scored_tokens_per_layer']==[299077]*36
            assert activity['decode_targets']==299077 and activity['decode_calls']==query_calls
            write(runroot/'ACTIVITY_FINAL.json',dict(activity,elapsed_seconds=time.monotonic()-started,
                scorer_returned=True,seal_required='results/COMPLETE.json'))
            return result
        finally:handle.remove()
    run.score=observed_score
    run.main()

if __name__=='__main__':main()
