"""Flat independent clock oracle, logical-source pairing, explicit energy windows."""
from pathlib import Path
from collections import Counter
import hashlib,json,random,argparse
from ..control_v2.oracle import WinnerOracle
from ..control_v2.validate import generate as old_stress
H=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
def query(spec,mode,seed=17,samples=128,burn=0,stall=False):
    n=128; full=(1<<n)-1;model=WinnerOracle(n,spec['prep'],spec['stream'],64,spec['early'])
    rng=random.Random(seed);fair=random.Random(seed+202);tape=[]
    for i in range(samples+burn):
        if mode=='all':bits=full
        elif mode=='empty':bits=0
        elif mode=='single':bits=1<<(i%n)
        elif mode=='three':bits=sum(1<<j for j in rng.sample(range(n),3))
        else:
            p={'sparse':1/32,'dense':.5}[mode]
            bits=sum((rng.random()<p)<<j for j in range(n))
        tape.append(bits)
    word=fair.getrandbits(7);cursor=0;fv=rv=0;stim=[];rows=[];frames=[];outputs=[];values=[];commits=[];cov=Counter();done_at=None
    for t in range(14000):
        if not fv:fv=int(not stall or t%5!=0)
        if not rv:rv=int(not stall or t%7 not in (0,1))
        x=[int(t>1),int(t==3),full,0,samples,burn,int(not stall or t>=11),fv if cursor<len(tape) else 0,tape[cursor] if cursor<len(tape) else 0,rv,word,int(not stall or t%11<8)]
        pre=model.ports(x);old=model.status()
        if x[0] and x[7] and pre[3]:frames.append(t);cursor+=1;fv=0
        if x[0] and x[9] and pre[4]:word=fair.getrandbits(7);rv=0
        if x[0] and pre[5] and x[-1]:outputs.append(t);values.append(pre[6])
        post=model.edge(x)
        if post[7]>old[7]:commits.append(t)
        for label,v in [('rank_retry',post[-1]>old[-1]),('hold',post[9]>old[9]),('switch',post[10]>old[10]),('output_stall',pre[5] and not x[-1]),('source_wait',pre[3] and not x[7]),('fair_wait',pre[4] and not x[9]),('cfg_wait',pre[2] and not x[6])]:cov[label]+=int(v)
        stim.append(x);rows+=['P '+str(t)+' '+' '.join(map(str,pre[:9])),'C '+str(t)+' '+' '.join(map(str,post[:5]))]
        if post[4]:raise AssertionError('unexpected failure')
        if post[3]:done_at=t
        if done_at is not None and t>=done_at+40:break
    assert done_at is not None and len(outputs)==samples and len(frames)==samples+burn
    if mode=='all' and not stall:
        assert all(b-a==(1 if spec['stream'] else spec['prep']+2) for a,b in zip(frames,frames[1:]))
    meta=dict(mode=mode,seed=seed,samples=samples,burn=burn,stall=stall,cycles=len(stim),outputs=len(outputs),frames=len(frames),first_frame=frames[0],first_output=outputs[0],last_output=outputs[-1],start_to_done_cycles=done_at-3+1,
      active_cycles=outputs[-1]-frames[0]+1,first_output_latency_cycles=outputs[0]-frames[0],output_gaps=dict(Counter(b-a for a,b in zip(outputs,outputs[1:]))),fair_words=model.fair_words,rank_retries=model.rank_retries,holds=model.holds,switches=model.switches,coverage=dict(cov),
      input_frames_sha256=sha(b''.join(x.to_bytes(16,'little') for x in tape)),output_addresses_sha256=sha(bytes(values)))
    # Vectors driven at falling edges 10*(t+1) ns; acceptance occurs +5 ns.
    # Whole-query window includes start/config/drain. Active window is separate.
    windows=[dict(name='query',start_ns=40,end_ns=(done_at+2)*10,outputs=samples,updates=samples+burn),
             dict(name='active',start_ns=(frames[0]+1)*10,end_ns=(outputs[-1]+2)*10,outputs=samples,updates=samples+burn)]
    if mode=='all':windows.append(dict(name='idle_clock_running',start_ns=(done_at+12)*10,end_ns=(done_at+32)*10,outputs=0,updates=0))
    return stim,rows,meta,windows
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    specs=json.loads((H/'CASES.json').read_bytes())['tops'];index={};pair={}
    for spec in specs:
        entries=[];top=spec['top']
        cases=[('sparse',s,128,0,False) for s in (17,503,1009)]+[(m,17,128,0,False) for m in ('all','empty','single','three','dense')]
        cases += [('sparse',17,s,0,False) for s in (64,256,512)]+[('sparse',17,128,32,False),('sparse',17,128,0,True),('all',17,1023,0,False)]
        for mode,seed,s,b,stall in cases:
            name=f'{mode}_s{seed}_S{s}_B{b}'+('_stall' if stall else '')
            stim,rows,meta,windows=query(spec,mode,seed,s,b,stall)
            key=(spec['early'] or not spec['stream'],mode,seed,s,b)
            equivalent=(meta['input_frames_sha256'],meta['output_addresses_sha256'])
            assert pair.setdefault(key,equivalent)==equivalent,'scheduling changes output sequence'
            # Initial PPA screen: 3 sparse seeds, all/dense and external-stall.
            # All functional S budgets retained; detailed S power after selection.
            do_power=(mode=='sparse' and s==128 and b==0) or (mode in ('all','dense') and s==128)
            active=[w for w in windows if w['name']!='active'] if do_power else []
            if do_power and stall:active=[w for w in windows if w['name']=='query']
            folder=a.output/top/name;folder.mkdir(parents=True)
            vb=('\n'.join(' '.join(format(v,'x') for v in x) for x in stim)+'\n').encode();gb=('\n'.join(rows)+'\n').encode()
            (folder/'vectors.txt').write_bytes(vb);(folder/'golden.log').write_bytes(gb)
            entries.append(dict(trace=name,cycles=len(stim),vectors_sha256=sha(vb),golden_sha256=sha(gb),windows=active,metrics=meta))
        for seed in (17,503,1009):
            stim,pre,post,cov,timing=old_stress(128,spec['prep'],spec['stream'],seed,'stress',cycles=2400,early=spec['early'],rankcap=64)
            name=f'stress_s{seed}';folder=a.output/top/name;folder.mkdir(parents=True)
            rows=[]
            for i,(before,after) in enumerate(zip(pre,post)):rows+=['P '+str(i)+' '+' '.join(map(str,before[:9])),'C '+str(i)+' '+' '.join(map(str,after[:5]))]
            vb=('\n'.join(' '.join(format(v,'x') for v in x) for x in stim)+'\n').encode();gb=('\n'.join(rows)+'\n').encode()
            (folder/'vectors.txt').write_bytes(vb);(folder/'golden.log').write_bytes(gb)
            entries.append(dict(trace=name,cycles=len(stim),vectors_sha256=sha(vb),golden_sha256=sha(gb),windows=[],coverage=cov))
        # Deliberately force rank retries through cap; failure is explicit, no biased fallback.
        stim,pre,post,cov,timing=old_stress(128,spec['prep'],spec['stream'],17,'cap',cycles=900,early=spec['early'],rankcap=64)
        assert cov['cap_failure']>0
        folder=a.output/top/'cap';folder.mkdir(parents=True);rows=[]
        for i,(before,after) in enumerate(zip(pre,post)):rows+=['P '+str(i)+' '+' '.join(map(str,before[:9])),'C '+str(i)+' '+' '.join(map(str,after[:5]))]
        vb=('\n'.join(' '.join(format(v,'x') for v in x) for x in stim)+'\n').encode();gb=('\n'.join(rows)+'\n').encode();(folder/'vectors.txt').write_bytes(vb);(folder/'golden.log').write_bytes(gb)
        entries.append(dict(trace='cap',cycles=len(stim),vectors_sha256=sha(vb),golden_sha256=sha(gb),windows=[],coverage=cov))
        for bad in ('zero_samples','invalid_initial','counter_overflow'):
            model=WinnerOracle(128,spec['prep'],spec['stream'],64,spec['early']);rows=[];stim=[]
            for t in range(12):
                maximum=(1<<spec['count_width'])-1
                x=[int(t>1),int(t==3),0 if bad=='invalid_initial' else (1<<128)-1,0,0 if bad=='zero_samples' else maximum if bad=='counter_overflow' else 1,int(bad=='counter_overflow'),1,0,0,1,0,1]
                pre=model.ports(x);post=model.edge(x)
                if t==3 and bad=='counter_overflow':
                    # Public finite-width interface contract, independent of RTL.
                    assert x[4]+x[5]>maximum
                    model.active=False;model.failed=model.done=True;post=model.status()
                if t==3:assert post[3] and post[4] and not post[0]
                rows+=['P '+str(t)+' '+' '.join(map(str,pre[:9])),'C '+str(t)+' '+' '.join(map(str,post[:5]))];stim.append(x)
            folder=a.output/top/bad;folder.mkdir(parents=True)
            vb=('\n'.join(' '.join(format(v,'x') for v in x) for x in stim)+'\n').encode();gb=('\n'.join(rows)+'\n').encode();(folder/'vectors.txt').write_bytes(vb);(folder/'golden.log').write_bytes(gb)
            entries.append(dict(trace=bad,cycles=len(stim),vectors_sha256=sha(vb),golden_sha256=sha(gb),windows=[]))
        index[top]=entries
    (a.output/'TRACES.json').write_bytes((json.dumps(index,indent=2)+'\n').encode())
    print(json.dumps(dict(tops=len(index),traces=sum(map(len,index.values())),power_windows=sum(len(t['windows']) for v in index.values() for t in v))))
if __name__=='__main__':main()
