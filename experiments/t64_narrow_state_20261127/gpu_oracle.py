import numpy as np
import torch
from core import narrow
from oracle import rne

def expected(c,s,h,w,cf,T,R,width,role):
    c,s,h,w,cf=[x.cpu().numpy().astype(np.int64) for x in [c,s,h,w,cf]]
    M,K=c.shape;N=w.shape[0];G=K//64;NB=N//64;out=np.zeros((M,N),dtype=np.int64)
    for m in range(M):
        mn=h[m].reshape(G,64).min(-1);mx=h[m].reshape(G,64).max(-1)
        bounds=[sum((64*T*127*int(cf[b,g]))<<(R-int(mn[g])) for g in range(G)) for b in range(NB)]
        if role=='GU':bounds=[max(bounds[b%(NB//2)],bounds[b%(NB//2)+NB//2]) for b in range(NB)]
        else:bounds=[max(bounds[b//2*2:b//2*2+2]) for b in range(NB)]
        base=[(x-1).bit_length()-(width-2) for x in bounds];state=[0]*N
        for g in range(G):
            local=(c[m,g*64:(g+1)*64]<<(mx[g]-h[m,g*64:(g+1)*64]))*s[m,g*64:(g+1)*64]
            partial=w[:,g*64:(g+1)*64]@local
            for j in range(N):
                e=R-int(mx[g])+int(cf[j//64,g]).bit_length()-1
                state[j]+=rne(int(partial[j]),e-base[j//64])
                assert -(1<<(width-1))<=state[j]<(1<<(width-1))
        for j in range(N):
            e=base[j//64];out[m,j]=state[j]<<e if e>=0 else state[j]>>(-e)
    return torch.from_numpy(out)

def run():
    rows=[]
    for seed in [17,503,1009]:
        for role,T,G in [('GU',16,2),('Wd',32,3)]:
            gen=torch.Generator().manual_seed(seed)
            c=torch.randint(T+1,(3,G*64),generator=gen,dtype=torch.int64)
            s=torch.randint(3,c.shape,generator=gen)-1
            base=torch.randint(0,19,(3,G,1),generator=gen)
            h=(base+torch.randint(3,(3,G,64),generator=gen)).reshape_as(c)
            w=torch.randint(-127,128,(128,G*64),generator=gen,dtype=torch.int64)
            cf=torch.ones(2,G,dtype=torch.int64)<<torch.randint(12,(2,G),generator=gen)
            R=int(h.max())
            for width in [24,32]:
                want=expected(c,s,h,w,cf,T,R,width,role)
                got,info=narrow(*[x.cuda() for x in [c,s,h,w,cf]],T,R,width,role)
                assert torch.equal(want,got.cpu())
                rows.append(dict(seed=seed,role=role,width=width,K_blocks=G))
    for role,T,G in [('GU',16,40),('Wd',32,152)]:
        gen=torch.Generator().manual_seed(225)
        c=torch.randint(T+1,(1,G*64),generator=gen,dtype=torch.int64);s=torch.randint(3,c.shape,generator=gen)-1
        h=(torch.randint(0,19,(1,G,1),generator=gen)+torch.randint(3,(1,G,64),generator=gen)).reshape_as(c)
        w=torch.randint(-127,128,(128,G*64),generator=gen,dtype=torch.int64)
        cf=torch.ones(2,G,dtype=torch.int64)<<torch.randint(12,(2,G),generator=gen);R=int(h.max())
        for width in [24,32]:
            want=expected(c,s,h,w,cf,T,R,width,role)
            got,info=narrow(*[x.cuda() for x in [c,s,h,w,cf]],T,R,width,role)
            assert torch.equal(want,got.cpu())
            rows.append(dict(seed=225,role=role,width=width,K_blocks=G))
    return dict(status='passed',cases=len(rows),rows=rows,oracle='independent NumPy/Python integer tile updates')
