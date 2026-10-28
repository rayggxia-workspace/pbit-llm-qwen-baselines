"""Generate PPA-top port goldens from independent, flat cycle references."""
import argparse
import json
from pathlib import Path
from ..validate import generate,sha
from ..rejection import generate as rejection_generate,RejectionOracle

def save(path,stim,rows,windows,coverage):
    path.mkdir(parents=True,exist_ok=False)
    (path/'vectors.txt').write_bytes(('\n'.join(' '.join(format(v,'x') for v in x) for x in stim)+'\n').encode())
    (path/'golden.log').write_bytes(('\n'.join(rows)+'\n').encode())
    return dict(trace=path.name,cycles=len(stim),windows=windows,coverage=coverage,
                vectors_sha256=sha(path/'vectors.txt'),golden_sha256=sha(path/'golden.log'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    specs=json.loads((Path(__file__).parents[1]/'evidence/ppa_bundle_final/CASES.json').read_text())['tops']
    result={}
    for spec in specs:
        top=spec['top'];base=a.output/top;base.mkdir();entries=[]
        configs=[('stress',s) for s in (17,503,1009)]
        if spec['kind']=='winner':configs += [(m,17) for m in ('all','empty','single','three','cap')]
        else:configs += [('mixed1',17),('mixed8',17)]
        for mode,seed in configs:
            name=mode+'_s'+str(seed)
            if spec['kind']=='winner':
                stim,pre,post,cov,timing=generate(512,spec['prep'],1,seed,mode,cycles=2400 if mode=='stress' else 900,early=spec['early'],rankcap=64)
                rows=[]
                for i,(b,c) in enumerate(zip(pre,post)):
                    rows += ['P '+str(i)+' '+' '.join(map(str,b[:9])),'C '+str(i)+' '+' '.join(map(str,c[:5]))]
                if mode=='stress':start,end=50,23990
                elif mode=='cap':start,end=70,800
                else:start=(timing['frame_edges'][0]+1)*10;end=(timing['output_edges'][-1]+2)*10
                windows=[dict(name=mode,start_ns=start,end_ns=end)]
                if mode=='all':windows.append(dict(name='idle_clock_running',start_ns=4000,end_ns=8900))
            else:
                delay=8 if mode=='mixed8' else 1;actual='mixed' if mode.startswith('mixed') else mode
                stim,post,cov,timing=rejection_generate(512,spec['prefetch'],seed,actual,delay)
                model=RejectionOracle(512,spec['prefetch']);rows=[]
                for i,x in enumerate(stim):
                    b=model.status(x);c=model.edge(i,x)
                    rows+=['P '+str(i)+' '+' '.join(str(b[j]) for j in [2,3,4,5,6,7,8,9,10,1]),
                           'C '+str(i)+' '+' '.join(str(c[j]) for j in [3,7,8,9,10,1])]
                if actual=='stress':start,end=50,44990
                else:start=(timing['first']+1)*10;end=(timing['done']+2)*10
                windows=[dict(name=mode,start_ns=start,end_ns=end)]
                if mode=='mixed1':windows.append(dict(name='idle_clock_running',start_ns=40000,end_ns=44900))
            entries.append(save(base/name,stim,rows,windows,cov))
        result[top]=entries
    (a.output/'TRACES.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(dict(tops=len(result),traces=sum(map(len,result.values()))))

if __name__=='__main__':main()
