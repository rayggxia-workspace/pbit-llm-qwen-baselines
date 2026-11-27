"""Audit all stored FP24 prefixes and integer-only probability encoders."""
import math
import numpy as np

def qformat(v,p=16,bits=8):
    bias=(1<<(bits-1))-1;emin=1-bias;emax=(1<<bits)-2-bias
    v=np.asarray(v,dtype=np.float64);a=np.ascontiguousarray(np.abs(v));raw=a.view(np.uint64)
    drop=53-p;mask=np.uint64(((1<<64)-1)^((1<<drop)-1))
    y=((raw+np.uint64((1<<(drop-1))-1)+((raw>>np.uint64(drop))&np.uint64(1)))&mask).view(np.float64)
    tiny=(a>0)&(a<2.**emin);maximum=math.ldexp(2.-2.**(-(p-1)),emax);large=y>maximum
    y=np.minimum(y,maximum);y=np.where(v<0,-y,y);y=np.where(tiny|(a==0),0.,y)
    return y,int(tiny.sum()),int(large.sum())

def histogram(v):
    v=np.asarray(v,dtype=np.float64);a=np.abs(v);nonzero=a[a>0]
    ex=np.frexp(nonzero)[1]-1
    keys,counts=np.unique(ex,return_counts=True)
    return dict(zero=int(v.size-nonzero.size),nonzero=int(nonzero.size),
                bins={str(int(k)):int(n) for k,n in zip(keys,counts)})

def add_hist(a,b):
    a['zero']+=b['zero'];a['nonzero']+=b['nonzero']
    for e,n in b['bins'].items():a['bins'][e]=a['bins'].get(e,0)+n

def hist_summary(h):
    keys=sorted(map(int,h['bins']));total=h['nonzero'];q={}
    for p in [.001,.01,.5,.99,.999]:
        target=max(1,math.ceil(p*total));s=0
        for e in keys:
            s+=h['bins'][str(e)]
            if s>=target:q[str(p)]=e;break
    return dict(**h,minimum=min(keys) if keys else None,maximum=max(keys) if keys else None,quantiles=q)

def unsigned_rne(a,k):
    a=np.asarray(a,dtype=np.int64);k=np.broadcast_to(k,a.shape).astype(np.int64)
    right=k.clip(1,60);q=a>>right;r=a-(q<<right);half=np.ones_like(a)<<(right-1)
    q+=((r>half)|((r==half)&((q&1)!=0))).astype(np.int64)
    return np.where(k>=61,0,np.where(k>0,q,a<<(-k).clip(0,30)))

def integer_codec(value,cap):
    """FP24 sign/exponent/significand -> S/S2 P8 and two S8/F3 addresses."""
    from formats import words
    v=np.asarray(value,dtype=np.float64);w=words(v,16).astype(np.int64)
    encoded_exp=(w>>15)&255;ex=encoded_exp-127
    sig=np.where(encoded_exp==0,0,32768+(w&32767));sign=np.where(sig==0,0,np.where((w>>23)!=0,-1,1))
    magnitude=w&((1<<23)-1);mx=magnitude.reshape(v.shape[0],-1,64).max(-1,keepdims=True)
    me=((mx>>15)&255)-127;ms=np.where(mx==0,0,32768+(mx&32767))
    top=np.where(mx==0,-6,me+(ms!=32768)).clip(-6,int(math.log2(cap)))
    top=np.broadcast_to(top,magnitude.reshape(v.shape[0],-1,64).shape).reshape(v.shape)
    small=(top>=-5)&((ex<top-1)|((ex==top-1)&(sig==32768))|(sig==0))
    chosen=top-small.astype(np.int64)
    code=unsigned_rne(sig,chosen+7-ex).clip(0,255)
    code=np.where((sig!=0)&(ex>=chosen),256,code)
    raw_mag=unsigned_rne(sig,12-ex)
    raw_mag=np.where(ex>=4,128,np.where(ex<=-5,0,raw_mag))
    raw_field=(sign*raw_mag).clip(-128,127)
    reconstructed=(sign*unsigned_rne(code,5-chosen)).clip(-128,127)
    return dict(q=code,sign=sign,exponent=chosen,raw_field=raw_field,field=reconstructed)

def analyze(z):
    from formats import encode_gu
    parts=z['parts'];G,m,n=parts.shape;T=int(z['samples']);R=int(z['R']);role=str(z['role'])
    cf=z['coeff'];ex=z['ex'];ce=np.frexp(cf.astype(np.float64))[1]-1
    power=np.repeat(ex-16-int(math.log2(T))-R,64)
    delta=np.repeat(R-z['hi'].T[:,:,None]+ce.T[:,None,:],64,-1)
    raw=parts<<delta;assert np.array_equal(raw.sum(0),z['reference'])
    reference=np.ldexp(z['reference'].astype(np.float64),power)
    hist={k:dict(zero=0,nonzero=0,bins={}) for k in ['tile','state','final']}
    formats={'E8M15':(8,16),'E6M15_storage':(6,16),'E5M15_storage':(5,16),'E6M17_storage':(6,18)}
    state={k:np.zeros((m,n),dtype=np.float64) for k in formats}
    events={k:dict(tile_underflow=0,tile_overflow=0,state_underflow=0,state_overflow=0) for k in formats}
    for g in range(G):
        exact_tile=np.ldexp(parts[g].astype(np.float64),delta[g]+power)
        for name,(eb,p) in formats.items():
            # Tile is a temporary E8 value; only the saved state has narrowed E.
            tile,u,o=qformat(exact_tile,p,8);events[name]['tile_underflow']+=u;events[name]['tile_overflow']+=o
            saved,u,o=qformat(state[name]+tile,p,eb)
            events[name]['state_underflow']+=u;events[name]['state_overflow']+=o;state[name]=saved
            if name=='E8M15':add_hist(hist['tile'],histogram(tile));add_hist(hist['state'],histogram(saved))
    add_hist(hist['final'],histogram(state['E8M15']))
    result={}
    for name,v in state.items():
        err=v-reference
        result[name]=dict(events=events[name],values=int(v.size),changed_vs_E8M15=int(np.count_nonzero(v!=state['E8M15'])),
                          squared_error=float(np.square(err).sum()),reference_squared=float(np.square(reference).sum()))
    codec={}
    if role=='GU':
        h=n//2
        for label,start,cap in [('g',0,float(z['g_cap'])),('u',h,float(z['u_cap']))]:
            value=state['E8M15'][:,start:start+h];actual=integer_codec(value,cap);expected=encode_gu(value,cap)
            for k in ['q','sign','exponent','field']:assert np.array_equal(actual[k],expected[k]),k
            direct=np.rint(value*8).clip(-128,127).astype(np.int64)
            assert np.array_equal(actual['raw_field'],direct),'raw sigmoid integer codec differs'
            codec[label]=dict(values=int(value.size),amplitude_codec_exact=True,raw_field_codec_exact=True,
                              raw_vs_reconstructed_field_changed=int(np.count_nonzero(direct!=expected['field'])))
    return dict(role=role,K_blocks=G,histograms=hist,formats=result,codec=codec)

def summarize(rows):
    out={}
    for r in rows:
        group=out.setdefault(r['role'],dict(cases=0,histograms={},formats={},codec={}))
        group['cases']+=1
        for stage,h in r['histograms'].items():add_hist(group['histograms'].setdefault(stage,dict(zero=0,nonzero=0,bins={})),h)
        for name,x in r['formats'].items():
            s=group['formats'].setdefault(name,dict(values=0,changed_vs_E8M15=0,squared_error=0.,reference_squared=0.,events={}))
            for k in ['values','changed_vs_E8M15','squared_error','reference_squared']:s[k]+=x[k]
            for k,v in x['events'].items():s['events'][k]=s['events'].get(k,0)+v
        for name,x in r['codec'].items():
            s=group['codec'].setdefault(name,dict(values=0,raw_vs_reconstructed_field_changed=0))
            for k in s:s[k]+=x[k]
    for r in out.values():
        r['histograms']={k:hist_summary(v) for k,v in r['histograms'].items()}
        for x in r['formats'].values():x['relative_rms']=math.sqrt(x['squared_error']/x['reference_squared']) if x['reference_squared'] else 0.
    return out
