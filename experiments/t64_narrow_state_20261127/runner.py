from pathlib import Path
from contextlib import ExitStack,AbstractContextManager
import argparse,gc,hashlib,importlib.util,json,os,sys,unittest
OWN=Path(__file__).resolve().parent;SOURCE=OWN.parents[1]
PARENT=OWN.parent/'t64_x_onebit_20261127'
spec=importlib.util.spec_from_file_location('x_parent',PARENT/'runner.py')
parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
sys.path.insert(0,str(OWN))
from core import NarrowOverride
from x_onebit import XOnebitOverride

class Composite(AbstractContextManager):
    def __init__(self,width):self.width=int(width)
    def __enter__(self):
        self.stack=ExitStack()
        try:
            self.n=self.stack.enter_context(NarrowOverride(self.width))
            self.x=self.stack.enter_context(XOnebitOverride(True))
            return self
        except BaseException:
            self.stack.close();raise
    def __exit__(self,*exc):return self.stack.__exit__(*exc)
    def report(self):return dict(state=self.n.report(),scales=self.x.report())

def case(width):
    return dict(id='state'+str(width)+'_xguS2_16_32',scale_policy=str(width),T_x=16,T_and=32,
                input_law='stratified_T',and_law='joint_grid',grid_g_sig_u=[4,2,4])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--settings',type=Path,required=True)
    ap.add_argument('--phase',choices=['cpu','gpu'],required=True);a=ap.parse_args();assert os.environ.get('SLURM_JOB_ID')
    raw=a.settings.read_bytes();assert hashlib.sha256(raw).hexdigest()==a.settings.with_suffix('.sha256').read_text().strip()
    settings=json.loads(raw);root=a.settings.parent
    manifest=json.loads((SOURCE/'EXECUTION_MANIFEST.json').read_bytes())
    for n,d in manifest['files'].items():assert hashlib.sha256((SOURCE/n).read_bytes()).hexdigest()==d,n
    sys.path.insert(0,settings['runtime'])
    import torch
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False
    from score_reference import sealed,save,score
    if a.phase=='cpu':
        suite=unittest.TestSuite()
        for folder,pattern in [(parent.ONEBIT,'test_onebit.py'),(parent.HALF,'test_half.py'),(parent.PARENT,'test_dynamic.py'),(PARENT,'test_x.py'),(OWN,'test_state.py')]:
            suite.addTests(unittest.TestLoader().discover(str(folder),pattern=pattern))
        z=unittest.TextTestRunner(verbosity=2).run(suite);assert z.wasSuccessful() and z.testsRun==25
        save(root/'CPU_PREFLIGHT.json',dict(status='completed',tests=25));return
    assert sealed(root/'CPU_PREFLIGHT.json')['tests']==25
    assert torch.cuda.is_available() and torch.cuda.device_count()==1
    from reference import prepare,load_model
    from gpu_oracle import run
    from driver import kernel_gate
    out=root/'outputs';out.mkdir(exist_ok=False)
    oracle=run();integer=kernel_gate()
    inputs,tokens,ledger,protocol=prepare(Path(settings['inputs']),Path(settings['runtime']),out)
    oldroot=Path(settings['reference_root']);oldgate=sealed(oldroot/'gate/RESULT.json')
    assert protocol==oldgate['provenance']['protocol']
    model,context,modules,native=load_model(inputs,native=True)
    bf=score(model,context,modules,tokens,ledger,list(range(292)),101,out/'BF16_full')
    assert native==oldgate['native_identity'] and abs(bf['ppl']-oldgate['BF16_full']['ppl'])<.000001
    del model,context,modules;gc.collect();torch.cuda.empty_cache()
    model,context,modules,identity=load_model(inputs);assert identity==oldgate['identity']
    from adapter import SamplingOverride
    c=case(64);p=SamplingOverride(c);p.configure(modules)
    ids=torch.as_tensor(tokens[:128].astype('int64'),device='cuda')[None]
    def probe(extra):
        context.seed=101;context.begin(0,0,domain='narrow64-noop')
        with p,extra,torch.no_grad():return model(ids,use_cache=False).logits.detach().clone()
    assert torch.equal(probe(XOnebitOverride(True)),probe(Composite(64)))
    assert torch.equal(probe(Composite(32)),probe(Composite(32)))
    del ids
    save(out/'GATE.json',dict(status='completed',oracle=oracle,integer_kernel_oracle=integer,
         source=manifest,identity=identity,protocol=protocol,BF16_full=bf,state64_noop_logits_bitwise=True,
         sigmoid_contract='unchanged existing P8-reconstructed g; not RTL raw-g sigmoid'))
    import scale_patch
    original=scale_patch.ScaleOverride;scale_patch.ScaleOverride=Composite
    rows=[];full=[]
    try:
        for width in [64,32,24]:
            c=case(width)
            z=score(model,context,modules,tokens,ledger,[0,41,83,125,166,208,250,290],101,out/('pilot'+str(width)),c)
            if width==64:
                previous=sealed(oldroot/'ppl/PROGRESS.json')
                ref=next(x['result'] for x in previous['pilot'] if x['case']['policy']=='x64s2_gu64s2')
                assert ref['records_sha256']==z['records_sha256'],'64-bit baseline differs from frozen original pilot'
            rows.append(dict(width=width,case=c,result=z));save(out/'PROGRESS.json',dict(status='running',pilot=rows))
        # Explicit resource gate, not a declaration of accuracy equivalence.
        accepted=[x['width'] for x in rows if x['width']!=64 and x['result']['ppl']<=rows[0]['result']['ppl']*1.01]
        save(out/'FULL_SELECTION.json',dict(status='completed',selected=accepted,trigger='pilot <=1.01x state64; resource gate only'))
        for width in accepted:
            c=case(width);z=score(model,context,modules,tokens,ledger,list(range(292)),101,out/('full'+str(width)),c)
            full.append(dict(width=width,case=c,result=z));save(out/'PROGRESS.json',dict(status='running',pilot=rows,full=full))
        save(out/'RESULT.json',dict(status='completed',pilot=rows,full=full,selected=accepted,
             source=manifest,identity=identity,protocol=protocol,BF16_full=bf,seed=101,
             sigmoid_unchanged=True,no_training=True,no_PPA=True,reference_full_root=str(oldroot),job=os.environ['SLURM_JOB_ID']))
    finally:scale_patch.ScaleOverride=original

if __name__=='__main__':main()
