"""Independent integer oracles and archived full-model window replay before using fast kernel."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,sys,time

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--original',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and not a.output.exists()
    settings=json.loads((a.original/'SETTINGS.json').read_bytes())
    assert hashlib.sha256((a.original/'SETTINGS.json').read_bytes()).hexdigest()==(a.original/'SETTINGS.sha256').read_text().strip()
    source=a.original/'source';manifest=json.loads((source/'EXECUTION_MANIFEST.json').read_bytes())
    assert manifest['git_commit']=='0d1e85176fd52205669148296c585a06c47bc369'
    for n,h in manifest['files'].items():assert hashlib.sha256((source/n).read_bytes()).hexdigest()==h,n
    sys.path.insert(0,settings['runtime'])
    sys.path.insert(0,str(source/'experiments/t64_dynamic_scale_20261125'))
    d=source/'experiments/t64_narrow_state_20261127';sys.path.insert(0,str(d))
    from score_reference import sealed,save,score
    import torch
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False
    assert torch.cuda.is_available() and torch.cuda.device_count()==1
    import core
    original=core.narrow
    spec=importlib.util.spec_from_file_location('fast_impl',Path(__file__).parent/'fast_narrow.py')
    fast=importlib.util.module_from_spec(spec);spec.loader.exec_module(fast)
    core.narrow=fast.narrow
    from gpu_oracle import run
    oracle=run()
    # Exact tensors AND metadata counters must match the frozen implementation.
    pairs=[]
    for role,T,G in [('GU',16,40),('Wd',32,152)]:
        gen=torch.Generator().manual_seed(101)
        c=torch.randint(T+1,(17,G*64),generator=gen,dtype=torch.int64)
        s=torch.randint(3,c.shape,generator=gen)-1
        h=(torch.randint(12,(17,G,1),generator=gen)+torch.randint(3,(17,G,64),generator=gen)).reshape_as(c)
        w=torch.randint(-127,128,(256,G*64),generator=gen,dtype=torch.int64)
        cf=torch.ones(4,G,dtype=torch.int64)<<torch.randint(8,(4,G),generator=gen)
        ex=torch.tensor([-12,3,4,-1],dtype=torch.int64)
        args=[x.cuda() for x in [c,s,h,w,cf]]
        for width in [24,32]:
            want,wi=original(*args,T,int(h.max()),width,role,ex.cuda())
            got,gi=fast.narrow(*args,T,int(h.max()),width,role,ex.cuda())
            assert torch.equal(want,got) and wi==gi,(role,width,wi,gi)
            pairs.append(dict(role=role,width=width,rows=17,columns=256,K_blocks=G,bitwise=True,metadata_equal=True))
    spec=importlib.util.spec_from_file_location('frozen_fast_gate',d/'runner.py')
    frozen=importlib.util.module_from_spec(spec);spec.loader.exec_module(frozen)
    oldgate=sealed(a.original/'outputs/GATE.json')
    from reference import prepare,load_model
    a.output.mkdir(parents=True)
    save(a.output/'INTEGER_GATE.json',dict(status='passed',oracle=oracle,pairs=pairs))
    (a.output/'prepared').mkdir()
    inputs,tokens,ledger,protocol=prepare(Path(settings['inputs']),Path(settings['runtime']),a.output/'prepared')
    assert protocol==oldgate['protocol']
    model,context,modules,identity=load_model(inputs);assert identity==oldgate['identity']
    import scale_patch
    scale_patch.ScaleOverride=frozen.Composite
    rows=[]
    for width in [32,24]:
        z=score(model,context,modules,tokens,ledger,[0],101,a.output/('pilot'+str(width)),frozen.case(width))
        actual=sealed(a.output/('pilot'+str(width)+'/WINDOWS.json'))
        expected=sealed(a.original/('outputs/pilot'+str(width)+'/WINDOWS.json'))
        assert actual==expected[:1], 'fast full-model window differs from original'
        rows.append(dict(width=width,result=z,archived_window_exact=True))
        save(a.output/'PROGRESS.json',dict(status='running',oracle=oracle,pairs=pairs,model_windows=rows))
    save(a.output/'RESULT.json',dict(status='completed',oracle=oracle,pairs=pairs,model_windows=rows,
         original_numerical_commit=manifest['git_commit'],fast_source_sha256=hashlib.sha256((Path(__file__).parent/'fast_narrow.py').read_bytes()).hexdigest(),
         job=os.environ['SLURM_JOB_ID'],same_math=True,no_training=True,no_PPA=True))

if __name__=='__main__':main()
