"""Fixed score interfaces. Units always refer to scaled QK/sqrt(d)."""
import torch

def signed(x, bits, frac):
    step = 2. ** (-frac)
    raw = torch.round(x / step)
    lo, hi = -2**(bits-1), 2**(bits-1)-1
    return raw.clamp(lo, hi)*step, (raw < lo) | (raw > hi)

def gap(x, bits, frac):
    step = 2. ** (-frac)
    delta = x.amax(-1, keepdim=True)-x
    raw = torch.round(delta/step)
    return -raw.clamp(0, 2**bits-1)*step, raw > 2**bits-1

def designs(z, calibration):
    yield 'bf16', z.bfloat16().float(), torch.zeros_like(z, dtype=torch.bool)
    for bits in (8,10,12,16):
        for frac in ((1,2,3,4) if bits == 8 else (bits-6,bits-5)):
            q,clip=signed(z,bits,frac)
            yield f'i{bits}_f{frac}',q,clip
        step=2.**torch.ceil(torch.log2(calibration/(2**(bits-1)-1)))
        raw=torch.round(z/step);lo,hi=-2**(bits-1),2**(bits-1)-1
        yield f'i{bits}_train_pot',raw.clamp(lo,hi)*step,(raw<lo)|(raw>hi)
    for bits in (8,10,12):
        for spanlog in (3,4,5):
            frac=bits-spanlog
            q,clip=gap(z,bits,frac)
            yield f'gap_u{bits}_f{frac}',q,clip
    # Wider score register, narrower LUT address: integer max and subtraction.
    for bits,frac,abits in ((8,2,6),(10,4,8),(12,6,10),(16,10,14)):
        q,c1=signed(z,bits,frac);g,c2=gap(q,abits,frac)
        yield f'i{bits}_f{frac}_gap_u{abits}',g,c1|c2
    # Cascaded BF16 then fixed-point must not inherit direct conversion results.
    for bits,frac in ((8,2),(10,4),(12,6)):
        q,clip=signed(z.bfloat16().float(),bits,frac)
        yield f'bf16_i{bits}_f{frac}',q,clip
    # Follow-up after v2 exposed positive scores above +32. Wider integer
    # range fixes saturation independently of fractional precision/table size.
    for bits,frac in ((10,3),(11,4),(12,5),(12,4),(14,7)):
        q,clip=signed(z,bits,frac)
        yield f'i{bits}_f{frac}',q,clip
    for source in ('fp32','bf16'):
        x=z if source=='fp32' else z.bfloat16().float()
        q,c1=signed(x,11,4);g,c2=gap(q,8,4)
        yield f'{source}_i11_f4_gap_u8',g,c1|c2
        if source=='bf16':
            g,c=gap(x,8,4)
            yield 'bf16_gap_u8_f4',g,c

def thresholds(logits, bits):
    p=logits.double().sigmoid()
    # floor is deliberately NOT raised to one: report lost mass explicitly.
    raw=torch.round(p*2**bits)
    q=raw.clamp(0,2**bits-1)/2**bits
    odds=q/(1-q)
    denom=odds.sum(-1,keepdim=True);valid=denom.squeeze(-1)>0
    # All-zero odds has no unique stationary distribution: mark invalid,
    # do not invent a uniform/reference fallback.
    return q.float(),(odds/denom.clamp_min(1e-300)).float(),raw==0,raw>=2**bits,valid

def selftest():
    import itertools,math
    x=torch.tensor([[-40.,-32.,-.375,-.125,.125,.375,31.75,40.]])
    q,c=signed(x,8,2)
    assert q.tolist()==[[-32.,-32.,-.5,-0.,0.,.5,31.75,31.75]] and c.sum()==2
    g,c=gap(torch.tensor([[20.,19.,0.]]),8,4)
    assert g.tolist()==[[-0.,-1.,-15.9375]] and c.sum()==1
    # Verify stationary odds by exhaustive independent-bit transition matrix.
    p=torch.tensor([.5,.25,.125],dtype=torch.float64);P=torch.zeros((3,3),dtype=torch.float64)
    for bits in itertools.product((0,1),repeat=3):
        prob=math.prod(float(p[j] if bits[j] else 1-p[j]) for j in range(3))
        active=[j for j,b in enumerate(bits) if b]
        for i in range(3):
            if bits[i] or not active:P[i,i]+=prob
            else:
                for j in active:P[i,j]+=prob/len(active)
    pi=p/(1-p);pi/=pi.sum()
    assert torch.allclose(pi@P,pi,atol=1e-14,rtol=0)
    z=torch.tensor([[0.]+[-6.3]*127]);p,pi,zero,one,valid=thresholds(z,8)
    assert zero.sum()==127 and pi[0,0]==1 and not one.any() and valid.all()
    p,pi,zero,one,valid=thresholds(torch.full((1,128),-20.),8)
    assert not valid.any() and p.sum()==0 and pi.sum()==0
    for name,q,c in designs(torch.randn(3,128),torch.ones(3,1)*32):
        assert q.shape==c.shape==(3,128) and torch.isfinite(q).all(),name
    print('SELFTEST_PASS: rounding/saturation/gap/exhaustive stationary odds/zero tails/design shapes',flush=True)

if __name__=='__main__':selftest()
