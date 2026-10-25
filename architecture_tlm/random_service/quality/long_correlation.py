"""Physical ideal-readout -> timed seed transport -> continuous full-lane diagnostics."""
import argparse
import csv
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
from ..backends import PROFILES, ROWS, generate
from .ideal_readout import read_inputs, conditioned, packets, simulate, digest, dump, metrics

TLAGS = list(range(1,129))+[256,512,1024]
SLAGS = [0,1,2,4,8,16,32,64,128]
QS = [4,13,64,128,192]


def state_words(s):return [(s>>(32*k))&0xffffffff for k in range(6)]
def decode_state(w):return sum(int(v)<<(32*k) for k,v in enumerate(w))
def binary_metrics(x):
    r=metrics(x)
    r['rho']={str(k):pearson(x[:-k],x[k:]) for k in TLAGS if k<len(x)}
    return r
def pearson(a,b):
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
    a=a-a.mean();b=b-b.mean();v=float(np.sqrt((a@a)*(b@b)))
    return float(a@b/v) if v else None


def native_gen(exe,kind,seeds,n,directory):
    if len(seeds)!=2 or any(not 0<s<(1<<PROFILES[kind]['state_bits']) for s in seeds):
        raise ValueError('two nonzero width-correct states required')
    path=directory/'words.bin'
    np.asarray([state_words(s) for s in seeds],dtype='<u4').tofile(directory/'seeds.u32')
    np.asarray(ROWS,dtype='<u4').tofile(directory/'mapping.u32')
    subprocess.run([str(exe),'gen',str(list(PROFILES).index(kind)),str(n),str(directory/'seeds.u32'),
                    str(directory/'mapping.u32'),str(path)],check=True)
    words=np.fromfile(path,dtype=np.uint8).reshape(n,2*PROFILES[kind]['lanes'])
    states=np.fromfile(str(path)+'.states',dtype='<u4').reshape(2,3,6)
    return words,states


def native_corr(exe,words,feature,directory,slags=SLAGS,tlags=TLAGS):
    path=directory/'words.bin'
    np.asarray(slags,dtype='<u4').tofile(directory/'slags.u32')
    np.asarray(tlags,dtype='<u4').tofile(directory/'tlags.u32')
    prefix=directory/('feature_'+str(feature))
    subprocess.run([str(exe),'corr',str(path),str(len(words)),str(words.shape[1]),str(feature),
        str(directory/'slags.u32'),str(len(slags)),str(directory/'tlags.u32'),str(len(tlags)),str(prefix)],check=True)
    l=words.shape[1]
    s=np.fromfile(str(prefix)+'.spatial',dtype='<f8').reshape(len(slags),l,l)
    t=np.fromfile(str(prefix)+'.temporal',dtype='<f8').reshape(len(tlags),l)
    return t,s


def numeric_corr(words,slags=SLAGS,tlags=TLAGS):
    x=words.astype(np.float64);n,l=x.shape
    f=np.fft.rfft(x,n=2*n,axis=0)
    product=np.fft.irfft(f*f.conj(),n=2*n,axis=0).real[:max(tlags)+1]
    p=np.vstack([np.zeros(l),np.cumsum(x,axis=0)])
    p2=np.vstack([np.zeros(l),np.cumsum(x*x,axis=0)])
    out=[]
    for k in tlags:
        m=n-k;sa=p[m];sb=p[n]-p[k];va=m*p2[m]-sa*sa;vb=m*(p2[n]-p2[k])-sb*sb
        out.append((m*product[k]-sa*sb)/np.sqrt(va*vb))
    spatial=[]
    for k in slags:
        a=x[:n-k];b=x[k:];a=a-a.mean(0);b=b-b.mean(0)
        spatial.append((a.T@b)/np.sqrt(np.sum(a*a,0)[:,None]*np.sum(b*b,0)[None,:]))
    return np.asarray(out),np.asarray(spatial)


def peak(array,coords):
    a=np.asarray(array);valid=np.isfinite(a)
    if not valid.any():return None
    index=np.unravel_index(np.nanargmax(np.abs(a)),a.shape)
    flat=np.abs(a[valid])
    return dict(rho=float(a[index]),abs=float(abs(a[index])),location={name:int(values[i]) for (name,values),i in zip(coords,index)},
                tests=int(valid.sum()),rms=float(np.sqrt(np.mean(flat*flat))),p99=float(np.quantile(flat,.99)))


def describe(t,s,slags,tlags,lanes):
    total=2*lanes
    mask=np.ones((total,total),dtype=bool);np.fill_diagonal(mask,False)
    same=np.zeros_like(mask);same[:lanes,:lanes]=True;same[lanes:,lanes:]=True;same&=mask
    cross=mask&~same
    result=dict(temporal=peak(t,[('lag',tlags),('lane',range(total))]),
                temporal_lag1=peak(t[:1],[('lag',[1]),('lane',range(total))]), spatial={})
    for name,m in [('within_instance',same),('between_instances',cross)]:
        a=s.copy();a[:,~m]=np.nan
        # lag0 is symmetric: retain each distinct pair only once.
        a[0,np.tril_indices(total)[0],np.tril_indices(total)[1]]=np.nan
        result['spatial'][name]=dict(same_cycle=peak(a[:1],[('lag',[0]),('lane_i',range(total)),('lane_j',range(total))]),
            lagged=peak(a[1:],[('lag',slags[1:]),('lane_i',range(total)),('lane_j',range(total))]))
    return result


def validate_matrices(x,t,s,slags,tlags):
    count=0
    def check(actual,a,b):
        nonlocal count
        expect=pearson(a,b)
        assert (expect is None and not np.isfinite(actual)) or abs(actual-expect)<1e-10,(actual,expect)
        count+=1
    for idx in [0,len(tlags)-1]:
        k=tlags[idx]
        for i in sorted({0,x.shape[1]-1}):check(t[idx,i],x[:-k,i],x[k:,i])
    for ki in [0,len(slags)-1]:
        k=slags[ki];check(s[ki,0,-1],x[:len(x)-k,0],x[k:,-1])
    ti=np.unravel_index(np.nanargmax(abs(t)),t.shape);k=tlags[ti[0]]
    check(t[ti],x[:-k,ti[1]],x[k:,ti[1]])
    z=s.copy();z[0,np.arange(x.shape[1]),np.arange(x.shape[1])]=np.nan
    si=np.unravel_index(np.nanargmax(abs(z)),z.shape);k=slags[si[0]]
    check(s[si],x[:len(x)-k,si[1]],x[k:,si[2]])
    return count


def analyse(exe,words,kind,directory):
    n,total=words.shape;lanes=PROFILES[kind]['lanes'];arrays={};summary={};audit=0
    for name,feature in [('word',None)]+[('q'+str(q),q) for q in QS]+[('bit'+str(b),-b-1) for b in range(8)]:
        slags=SLAGS if feature is None or feature>0 else [0]
        if feature is None:t,s=numeric_corr(words,slags);x=words
        else:
            t,s=native_corr(exe,words,feature,directory,slags)
            x=words<feature if feature>0 else (words>>(-feature-1))&1
        audit+=validate_matrices(x,t,s,slags,TLAGS)
        arrays[name+'_acf']=t;arrays[name+'_cross']=s;arrays[name+'_mean']=x.mean(0)
        item=describe(t,s,slags,TLAGS,lanes)
        item['mean_min']=float(x.mean(0).min());item['mean_max']=float(x.mean(0).max())
        item['blocks']={}
        if feature is not None:
            p=x.mean(0)
            for length in [8,16,32,64,128]:
                y=x[:n//length*length].reshape(-1,length,total).mean(1)
                ratio=y.var(0,ddof=1)/(p*(1-p)/length)
                target=feature/256 if feature>0 else .5
                arrays[name+'_varratio_'+str(length)]=ratio
                arrays[name+'_mse_'+str(length)]=np.mean((y-target)**2,axis=0)
                item['blocks'][str(length)]=dict(ratio_min=float(ratio.min()),ratio_max=float(ratio.max()),ratio_mean=float(ratio.mean()))
        summary[name]=item
    # All integer thresholds, per lane: exact empirical CDF discrepancy.
    hist=np.stack([np.bincount(words[:,i],minlength=256) for i in range(total)])
    cdf=hist.cumsum(1)/n-np.arange(1,257)/256
    arrays['cdf_error']=cdf
    joint=[]
    for port in range(2):
        w=words[:,port*lanes:(port+1)*lanes]
        q=max(1,round(256/lanes));k=(w<q).sum(1)
        record=dict(port='ab'[port],q=q,one_hit=float((k==1).mean()),all_zero=float((k==0).mean()),
            iid_one_hit=lanes*(q/256)*(1-q/256)**(lanes-1),mean_hits=float(k.mean()))
        arrays['port'+str(port)+'_hit_hist']=np.bincount(k.astype(int),minlength=lanes+1)
        if lanes>=4:
            patterns=((w[:,:4]<128)*(1<<np.arange(4))).sum(1).astype(int)
            arrays['port'+str(port)+'_patterns']=np.bincount(patterns,minlength=16)
            record['xor1']=float(np.logical_xor.reduce(w[:,:4]<128,axis=1).mean())
        joint.append(record)
    summary['joint']=joint;summary['cdf_worst']=peak(cdf,[('lane',range(total)),('q',range(1,257))])
    np.savez_compressed(directory/'matrices.npz',**arrays)
    return summary,audit


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--archive',type=Path,required=True);p.add_argument('--exe',type=Path,required=True);p.add_argument('--frames',type=int,default=131072)
    a=p.parse_args();assert a.frames>=1024 and a.frames%128==0
    if a.out.exists() or (a.archive/'cases').exists():raise FileExistsError('fresh result directory required')
    a.out.mkdir(parents=True);(a.archive/'cases').mkdir(parents=True)
    inputs,evidence=read_inputs(a.input);root=Path(__file__).resolve().parents[3]
    sourcefiles=[Path(__file__),Path(__file__).with_name('correlation_native.cpp'),Path(__file__).with_name('ideal_readout.py'),Path(__file__).with_name('metrics.py')]
    sourcefiles += [root/'architecture_tlm/random_service'/f for f in ['model.py','backends.py','shared64_mapping.json']]
    dump(a.out/'SOURCE_MANIFEST.json',{f.relative_to(root).as_posix():digest(f) for f in sourcefiles})
    dump(a.out/'INPUT_MANIFEST.json',evidence)
    config=dict(frames=a.frames,physical_seeds=[32003,32009,32027],modes=['raw','vn'],backends=list(PROFILES),
        clock_ns=10,physical_interval_ns=1000,temporal_lags=TLAGS,spatial_lags=SLAGS,thresholds=QS,
        bitplane_spatial_lags=[0],ports=2,reseed_cycles=100000000,periodic_reseed_observed=False,
        input_scope='single physical source per noise realization, not simultaneous spatial array; all20k input metrics, only demanded prefix is loaded',
        run_scope='continuous no-stall output after physical initial seed delivery; one boot per physical seed, no concatenated resets',
        controls='same shape PCG64 synthetic output controls; not passed through PRNG and not physical entropy',
        native_executable=dict(path=str(a.exe),sha256=digest(a.exe)),
        environment=dict(python=sys.version,numpy=np.__version__,platform=platform.platform()))
    dump(a.out/'CONFIG.json',config)
    cases=[];layers=[];checks=0;start_time=time.monotonic()
    for label,seed,bits,timestamps in inputs:
        if label!='ideal':continue
        with (a.input/f'seed{seed}_samples.csv').open(encoding='utf8',newline='') as f:
            voltage=np.array([float(row['core_V']) for row in csv.DictReader(f)])
        core=dict(n=len(voltage),mean_V=float(voltage.mean()),std_V=float(voltage.std(ddof=1)),
                  rho={str(k):pearson(voltage[:-k],voltage[k:]) for k in TLAGS})
        for mode in ['raw','vn']:
            cond,idx=conditioned(bits,np.arange(len(bits)),mode);entries=packets(cond,idx)
            serial=np.array([(w['word']>>j)&1 for w in entries for j in range(32)],dtype=np.uint8)
            assert np.array_equal(serial,cond[:len(serial)]);checks+=1
            layers.append(dict(seed=seed,mode=mode,core_voltage=core,raw=binary_metrics(bits),conditioned=binary_metrics(cond),packed_serial=binary_metrics(serial),
                retained=len(cond)/len(bits),discarded_tail=len(cond)%32,physical_raw_samples=len(bits),available_seed_words=len(entries),
                mean_retained_gap_us=float(np.diff(idx).mean()),physical_spatial_correlation=None,
                spatial_unavailable_reason='one measured source, no simultaneous physical channels'))
            for kind in PROFILES:
                case=f'ideal-{seed}-{mode}-{kind}';d=a.archive/'cases'/case;d.mkdir()
                reference,x,y,cycles=simulate(kind,entries,256,provenance=case+' real timestamped ideal-readout prefix')
                assert reference['status']=='complete'
                events=reference['network']['seed_events'];assert len(events)==2
                seeds=[int(e['seed_hex'],16) for e in events]
                words,states=native_gen(a.exe,kind,seeds,a.frames,d);lanes=PROFILES[kind]['lanes']
                assert np.array_equal(words[:256],np.concatenate([x,y],axis=1));checks+=1
                # Fresh-state Python replay at middle and tail checkpoints; prefixes already verified end-to-end.
                for port in range(2):
                    for j,t in enumerate([a.frames//2,a.frames-256]):
                        state=decode_state(states[port,j])
                        for k in range(256):
                            w,state=generate(kind,state);assert list(w)==words[t+k,port*lanes:(port+1)*lanes].tolist();checks+=1
                        if j==1:assert state==decode_state(states[port,2]);checks+=1
                first=int(cycles[0]);end=first+a.frames+1
                assert end < 20000*100 and end-events[0]['cycle']<100000000
                busbits=np.array([(e['word']>>j)&1 for e in reference['network']['seed_word_transcript'] for j in range(32)],dtype=np.uint8)
                statebits=np.array([(s>>j)&1 for s in seeds for j in range(PROFILES[kind]['state_bits'])],dtype=np.uint8)
                ref=reference['network']
                # No requests/stalls/reseed inside this continuous epoch; scale only the exact active edge actions.
                extra=a.frames-256;ref['cycles']+=extra;ref['elapsed_ns']+=extra*10
                for port in ref['ports'].values():
                    port['cycles']+=extra;c=port['counts'];pr=port['profile']
                    for key,mult in {'clock_edges':1,'frames_generated':1,'responses_consumed':1,'prng_updates':1,
                        'recurrence_steps':pr['steps'],'random_word_bits_generated':8*lanes,'threshold_comparisons':lanes,
                        'output_register_bits_written':9*lanes,'shared_mapping_evaluations':int(kind=='lfsr32_shared64')}.items():c[key]=c.get(key,0)+extra*mult
                dump(d/'TRANSPORT.json',dict(network=ref,first_request_cycle=first,last_request_cycle=first+a.frames-1,
                    counters='bulk exact no-stall action counts anchored by256 original cycle-model frames; not full RTL/EDA',
                    loaded_bus_bits=binary_metrics(busbits),loaded_state_bits=binary_metrics(statebits)))
                for source in ['physical','iid_control']:
                    target=d
                    if source=='iid_control':
                        target=a.archive/'cases'/('iid-'+case);target.mkdir()
                        words=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,int(mode=='vn'),list(PROFILES).index(kind),982451653]))).integers(0,256,size=(a.frames,2*lanes),dtype=np.uint8)
                        words.tofile(target/'words.bin')
                    stats,nchecks=analyse(a.exe,words,kind,target);checks+=nchecks
                    dump(target/'DETAIL.json',stats)
                    cases.append(dict(case_id=target.name,source=source,physical_seed=seed,mode=mode,backend=kind,frames=a.frames,lanes_per_instance=lanes,
                        first_request_us=first/100 if source=='physical' else None,stats=stats,
                        artifacts=[dict(path=str(f),bytes=f.stat().st_size,sha256=digest(f)) for f in target.iterdir() if f.name in ['words.bin','words.bin.states','matrices.npz','TRANSPORT.json','DETAIL.json']]))
                    print(json.dumps(dict(case=target.name,seconds=round(time.monotonic()-start_time,2))),flush=True)
    dump(a.out/'LAYERS.json',layers);dump(a.out/'SUMMARY.json',dict(cases=cases))
    dump(a.out/'AUDIT.json',dict(status='PASS',checks=checks,cases=len(cases),physical_cases=18,synthetic_controls=18,
        seconds=time.monotonic()-start_time,executable_sha256=digest(a.exe),
        caveat='Pearson recomputed for selected and worst entries, full matrices have exact packed counts; no IID/entropy certification'))
    print(json.dumps(dict(status='PASS',cases=len(cases),checks=checks,seconds=time.monotonic()-start_time)))


if __name__=='__main__':main()
