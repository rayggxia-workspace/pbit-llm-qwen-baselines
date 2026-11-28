"""Normal-only E8 formats. Float64 is an exact-enough container, never the accumulator format."""
from fractions import Fraction
import math
import numpy as np

MIN_NORMAL=2.**-126

def pot(e):return Fraction(2)**int(e)

def fraction_q(value,p):
    value=Fraction(value)
    if not value:return Fraction(0),0,0
    sign=-1 if value<0 else 1;a=abs(value)
    if a<pot(-126):return Fraction(0),1,0
    e=a.numerator.bit_length()-a.denominator.bit_length()
    if pot(e)>a:e-=1
    step=pot(e-(p-1));v=a/step;q,r=divmod(v.numerator,v.denominator)
    q+=int(2*r>v.denominator or (2*r==v.denominator and q%2))
    v=q*step;limit=(2-pot(-(p-1)))*pot(127)
    if v>limit:return sign*limit,0,1
    return sign*v,0,0

def quantize(value,p):
    """RNE normal significand; exact nonzero magnitude <2^-126 flushes BEFORE RNE."""
    if p not in (8,16):raise ValueError('BF16 or E8/M15 only')
    v=np.asarray(value,dtype=np.float64)
    if not np.isfinite(v).all():raise ValueError('finite exact input required')
    a=np.ascontiguousarray(np.abs(v));bits=a.view(np.uint64);drop=53-p
    mask=np.uint64(((1<<64)-1)^((1<<drop)-1))
    rounded=((bits+np.uint64((1<<(drop-1))-1)+((bits>>np.uint64(drop))&np.uint64(1)))&mask).view(np.float64)
    under=(a>0)&(a<MIN_NORMAL);limit=math.ldexp(2.-2.**(-(p-1)),127)
    over=rounded>limit
    q=np.minimum(rounded,limit);q=np.where(v<0,-q,q)
    q=np.where(under|(a==0),0.,q)
    return q,int(under.sum()),int(over.sum())

def words(value,p):
    v=np.asarray(value,dtype=np.float64);a=np.abs(v)
    m,e=np.frexp(a);sig=np.ldexp(m,p).astype(np.uint64)
    sign=(v<0).astype(np.uint64)
    word=(sign<<np.uint64(p+7))|((e-1+127).astype(np.uint64)<<np.uint64(p-1))|(sig-np.uint64(1<<(p-1)))
    return np.where(a==0,0,word).astype(np.uint32)

def floating_chain(parts,tile_exponents,p):
    """Two roundings: Q(tile), then Q(previous+Q(tile)), in source K order."""
    parts=np.asarray(parts,dtype=np.int64);ex=np.asarray(tile_exponents,dtype=np.int64)
    state=np.zeros(parts.shape[1:],dtype=np.float64)
    counts=dict(tile_underflow=0,tile_overflow=0,add_underflow=0,add_overflow=0)
    for k in range(parts.shape[0]):
        tile=np.ldexp(parts[k].astype(np.float64),ex[k])
        tile,u,o=quantize(tile,p);counts['tile_underflow']+=u;counts['tile_overflow']+=o
        # Each add has two p-bit operands. Relevant exponent separations need
        # <=2p+2 bits; farther operands cannot cross an RNE boundary. p<=16.
        state,u,o=quantize(state+tile,p);counts['add_underflow']+=u;counts['add_overflow']+=o
    return state,counts

def integer_rne(value,shift):
    value=np.asarray(value,dtype=np.int64);shift=np.broadcast_to(np.asarray(shift,dtype=np.int64),value.shape)
    if np.any(np.abs(shift)>60):raise ValueError('integer shift outside audited range')
    a=np.abs(value);k=np.maximum(shift,1);q=a>>k;rem=a-(q<<k);half=np.ones_like(a)<<(k-1)
    q+=((rem>half)|((rem==half)&((q&1)!=0))).astype(np.int64)
    return np.where(shift>0,q*np.sign(value),value<<np.maximum(-shift,0))

def fixed_chain(raw_parts,base,width):
    state=np.zeros(raw_parts.shape[1:],dtype=np.int64)
    for part in raw_parts:
        state+=integer_rne(part,base)
        if np.any(state<-(1<<(width-1))) or np.any(state>(1<<(width-1))-1):raise OverflowError('fixed state overflow')
    return np.ldexp(state.astype(np.float64),np.broadcast_to(base,state.shape))

def encode_gu(value,cap):
    v=np.asarray(value,dtype=np.float32);a=np.abs(v).reshape(v.shape[0],-1,64)
    maximum=a.max(-1,keepdims=True);mant,e=np.frexp(maximum)
    base=np.where(maximum==0,-6,e-(mant==.5)).clip(-6,int(math.log2(cap))).astype(np.int64)
    base=np.broadcast_to(base,a.shape).reshape(v.shape)
    small=(np.abs(v)<=np.ldexp(np.ones_like(v),base-1))&(base>=-5)
    ex=base-small.astype(np.int64);scale=np.ldexp(np.ones_like(v),ex)
    q=np.rint(np.ldexp(np.abs(v),8-ex)).clip(0,255).astype(np.int64)
    q=np.where((np.abs(v)>=scale)&(v!=0),256,q)
    return dict(q=q,sign=np.sign(v).astype(np.int64),exponent=ex,
                field=np.rint(np.ldexp(q.astype(np.float64)*np.sign(v),ex-5)).clip(-128,127).astype(np.int64))
