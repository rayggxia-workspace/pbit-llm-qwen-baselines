"""Replay real tile traces; each output contains every K block in original order."""
from fractions import Fraction
import math
import numpy as np
from formats import floating_chain,fixed_chain,quantize,words,encode_gu,fraction_q,pot

def evaluate(z):
    parts=z['parts'];hi=z['hi'];cf=z['coeff'];ex=z['ex'];ref=z['reference']
    T=int(z['samples']);R=int(z['R']);role=str(z['role']);ng,m,n=parts.shape;nb=n//64
    assert (cf.shape,hi.shape,ex.shape)==((nb,ng),(m,ng),(nb,))
    assert ng*64*T*127*int(cf.max())*(1<<R)<1<<63
    ce=np.frexp(cf.astype(np.float64))[1].astype(np.int64)-1
    assert np.array_equal(cf,np.ones_like(cf)<<ce)
    delta=R-hi.T[:,:,None]+ce.T[:,None,:]
    delta=np.repeat(delta,64,-1);assert delta.min()>=0 and delta.max()<=60
    raw=parts<<delta;exact=raw.sum(0);assert np.array_equal(exact,ref),'CPU tile replay differs from exact GPU reference'
    assert np.abs(ref).max()<1<<53,'double reference conversion not exact'
    power=np.repeat(ex-16-int(math.log2(T))-R,64)
    tile_exponents=delta+power[None,None,:]
    physical=np.ldexp(ref.astype(np.float64),power)
    if role=='GU':assert np.array_equal(physical.astype(np.float32),z['reference_fp32'])
    else:
        q,_,o=quantize(physical,8);assert o==0 and np.array_equal(words(q,8).astype(np.uint16),z['reference_bf16'])
    results={};vectors={}
    for name,p in [('FP24',16),('BF16',8)]:
        v,events=floating_chain(parts,tile_exponents,p);vectors[name]=v
        # Independent exact rational replay of two real complete chains.
        checks=0
        for j in [0,n//2]:
            a=Fraction(0)
            for k in range(ng):
                t,_,_=fraction_q(int(parts[k,0,j])*pot(tile_exponents[k,0,j]),p)
                a,_,_=fraction_q(a+t,p)
            assert Fraction(float(v[0,j]))==a,'float64 container differs from independent Fraction chain'
            checks+=1
        results[name]=dict(events=events,rational_chains_checked=checks)
    lo=z['minimum_shift']
    bounds=((64*T*127)<<(R-lo))[:,None,:]*cf[None,:,:];bounds=bounds.sum(-1)
    level=np.array([[(int(x)-1).bit_length() for x in row] for row in bounds],dtype=np.int64)+ex[None,:]
    if role=='GU':
        h=nb//2;common=np.maximum(level[:,:h],level[:,h:]);level=np.concatenate((common,common),-1)
    else:level=np.repeat(level.reshape(m,nb//2,2).max(-1),2,-1)
    for width in [24,32]:
        base=np.repeat(level-(width-2)-ex[None,:],64,-1)
        normalized=fixed_chain(raw,base,width);v=np.ldexp(normalized,power)
        name='Fixed'+str(width);vectors[name]=v;results[name]=dict(events={})
    for name,v in vectors.items():
        err=v-physical;refsum=float(np.square(physical).sum());errorsum=float(np.square(err).sum())
        a=results[name];a.update(values=int(v.size),max_abs_error=float(np.abs(err).max()),
            mean_abs_error=float(np.abs(err).mean()),squared_error_sum=errorsum,reference_squared_sum=refsum,
            relative_rms=math.sqrt(errorsum/refsum) if refsum else 0.,nonzero_error_values=int(np.count_nonzero(err)))
        if role=='GU':
            half=n//2;caps=[float(z['g_cap']),float(z['u_cap'])];changed=np.zeros((m,half),dtype=bool)
            for offset,cap,label in [(0,caps[0],'g'),(half,caps[1],'u')]:
                old=encode_gu(physical[:,offset:offset+half],cap);new=encode_gu(v[:,offset:offset+half],cap)
                local=np.zeros((m,half),dtype=bool)
                for key in ['q','sign','exponent']:
                    d=old[key]!=new[key];a[label+'_'+key+'_changed']=int(d.sum());local|=d
                if label=='g':a['sigmoid_field_changed']=int((old['field']!=new['field']).sum())
                changed|=local
            a.update(gu_pairs=int(changed.size),gu_code_pair_changed=int(changed.sum()))
        else:
            q,_,over=quantize(v,8);assert over==0
            a['final_BF16_changed']=int(np.count_nonzero(words(q,8).astype(np.uint16)!=z['reference_bf16']))
    return dict(role=role,samples=T,K_blocks=ng,rows=m,columns=n,formats=results,
                original_K64_integer_replay_exact=True)

def summarize(rows):
    out={}
    for row in rows:
        group=out.setdefault(row['role'],{})
        for name,a in row['formats'].items():
            b=group.setdefault(name,dict(values=0,max_abs_error=0.,squared_error_sum=0.,reference_squared_sum=0.,events={}))
            for k,v in a.items():
                if k=='events':
                    for ev,n in v.items():b['events'][ev]=b['events'].get(ev,0)+n
                elif k=='max_abs_error':b[k]=max(b[k],v)
                elif k not in ['relative_rms','mean_abs_error']:b[k]=b.get(k,0)+v
    for group in out.values():
        for b in group.values():
            b['relative_rms']=math.sqrt(b['squared_error_sum']/b['reference_squared_sum']) if b['reference_squared_sum'] else 0.
            if 'gu_pairs' in b:b['gu_code_pair_changed_fraction']=b['gu_code_pair_changed']/b['gu_pairs']
            if 'final_BF16_changed' in b:b['final_BF16_changed_fraction']=b['final_BF16_changed']/b['values']
            b['no_overflow']=not any(n for k,n in b['events'].items() if 'overflow' in k)
    return out
