"""Independent exact-integer/dyadic reference; never uses host FP arithmetic."""
def signed(x,w):return x-(1<<w) if x&(1<<(w-1)) else x

def rounded(n,shift):
    assert n>=0
    if shift>=0:return n<<shift,False
    k=-shift;q=n>>k;r=n-(q<<k)
    half=1<<(k-1)
    return q+int(r>half or (r==half and q&1)),r!=0

def clamp_scaled(n,shift,limit):
    if n and shift>=0 and n.bit_length()+shift>limit.bit_length():return limit,True,True
    q,ix=rounded(n,shift);sat=q>limit
    return min(q,limit),sat,ix or sat

def decode(bits,f):
    sign=bits>>(f+8);e=(bits>>f)&255;frac=bits&((1<<f)-1)
    if e==255:return ('nan' if frac else 'inf'),sign,0,0
    n=((1<<f) if e else 0)+frac
    return 'finite',sign,n,(e if e else 1)-127-f

def pack(n,lsb,f):
    if not n:return 0,0
    sign=int(n<0);n=abs(n);lead=n.bit_length()-1;e=lead+lsb
    tiny=0;ov=0
    if e>=-126:
        m,ix=rounded(n,f-lead)
        if m>=(1<<(f+1)):m>>=1;e+=1
        if e>127:return (sign<<(f+8))|(255<<f),3
        bits=(sign<<(f+8))|((e+127)<<f)|(m&((1<<f)-1))
    else:
        m,ix=rounded(n,lsb+126+f)
        if m>=(1<<f):bits=(sign<<(f+8))|(1<<f)
        else:bits=(sign<<(f+8))|m;tiny=1
    return bits,(tiny<<3)|(ov<<1)|int(ix)

def quant(bits,f,q,lsb,sym=False):
    typ,neg,n,exp=decode(bits,f);limit=(1<<(q-1))-1 if sym else (1<<q)-1
    if typ=='nan':return 0,4
    if typ=='inf':mag,sat,ix=limit,True,True
    else:mag,sat,ix=clamp_scaled(n,exp-lsb,limit)
    if sym:value=(-mag if neg else mag)&((1<<q)-1)
    else:value=mag|((neg and mag!=0)<<q)
    return value,(int(sat)<<1)|int(ix)

def add(a,b,f=23):
    ta,sa,na,pa=decode(a,f);tb,sb,nb,pb=decode(b,f)
    if ta=='nan' or tb=='nan' or (ta==tb=='inf' and sa!=sb):return (255<<f)|(1<<(f-1)),4
    if ta=='inf':return a,0
    if tb=='inf':return b,0
    if not na and not nb:return (sa&sb)<<(f+8),0
    p=min(pa,pb);n=((-na if sa else na)<<(pa-p))+((-nb if sb else nb)<<(pb-p))
    result,flags=pack(n,p,f)
    return result,flags&7 # Adder has no tiny output.

def align(n,shift,w=64):
    lim=(1<<(w-1)) if n<0 else (1<<(w-1))-1
    mag,sat,ix=clamp_scaled(abs(n),shift,lim)
    return ((-mag if n<0 else mag)&((1<<w)-1)),(int(sat)<<1)|int(ix)

def evaluate(k,data,aux,coef,ea,eb):
    if k in (0,1,2,3):
        return quant(data&((1<<(16 if k in (0,2) else 32))-1),
            7 if k in (0,2) else 23,16 if k==3 else 8,ea,k in (2,3))
    if k in (4,5,13,14):
        w=32 if k in (4,14) else 64
        return pack(signed(data&((1<<w)-1),w),ea,7 if k in (4,13) else 23)
    if k==6:
        x=data&0xffffffff;nan=((x>>23)&255)==255 and x&0x7fffff
        if nan:return (x>>16)|0x40,4
        out=((x>>16)+int((x&65535)>32768 or ((x&65535)==32768 and (x>>16)&1)))&65535
        ov=((x>>23)&255)!=255 and ((out>>7)&255)==255
        return out,(int(ov)<<1)|int(bool(x&65535))
    if k==7:return (data&65535)<<16,0
    if k==8:return align(signed(data&0xffffffff,32)*coef,ea-eb)
    if k in (9,12):return pack(signed(data&0xffffffff,32)*coef,ea,23 if k==9 else 7)
    if k==10:return align(signed(data,64),ea)
    if k==11:return add(data&0xffffffff,aux)
    if k in (15,16):
        typ,sg,n,p=decode(data&0xffffffff,23);f=23 if k==15 else 7
        if typ=='nan':return (255<<f)|(1<<(f-1)),4
        if typ=='inf':return (sg<<(f+8))|(255<<f),0
        if not n:return sg<<(f+8),0
        return pack(-n if sg else n,p+ea,f)
    if k==17:
        typ,sg,n,p=decode(data&0xffffffff,23)
        if typ=='nan':return 0,4
        if sg and (typ=='inf' or n):return 0,3
        if typ=='inf':return 1<<32,3
        mag,sat,ix=clamp_scaled(n,p-ea,1<<32)
        return mag,(int(sat)<<1)|int(ix)
    raise ValueError(k)

def accumulate(terms,common,width=None):
    if width is None:
        a=0;flags=0
        for n,m,e in terms:
            t,tf=pack(n*m,e,23);a,af=add(a,t)
            flags|=(tf&3)|af
        return a,flags
    a=0;flags=0
    for n,m,e in terms:
        bits,f=align(n*m,e-common,width);value=signed(bits,width)
        nxt=a+value;bounded=max(-(1<<(width-1)),min((1<<(width-1))-1,nxt))
        if nxt!=bounded:f|=3
        a=bounded;flags|=f
    result,pf=pack(a,common,23)
    return result,flags|(pf&3)
