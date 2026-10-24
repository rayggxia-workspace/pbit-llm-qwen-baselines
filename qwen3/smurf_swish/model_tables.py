"""Fixed-range signed-g FSM. Coefficients fit FINITE T occupancy, offline.

g has one fixed binary point, no online max and no per-value g bin selection.
Actual g = sign*G*q/256 appears INSIDE SiLU. Output units are separately Sf.
"""
import numpy as np
from scipy.special import expit
from scipy.optimize import lsq_linear
from .core import propagate

CASES=((8,4,.5),(8,8,.5),(16,8,.5),(8,8,8.),
       (1,4,1.),(2,4,.5),(4,4,.5),(4,8,4.))

def occupancy(q,states,cycles):
    p=np.asarray(q,dtype=float)/256
    v=np.zeros((p.size,states));v[:,0]=1
    total=np.zeros_like(v)
    for _ in range(cycles):
        v=propagate(v,p);total+=v
    return total/cycles

def build(G,states,Sneg,cycles):
    if cycles not in (64,128) or G not in (1,2,4,8,16) or states not in (4,8):
        raise ValueError('outside frozen pilot grid')
    q=np.arange(256);a=occupancy(q,states,cycles)
    lut=[];coeff=[];mean=[];errors=[]
    for sign,Sf in ((1,G),(-1,Sneg)):
        target=(G*q/256)*expit(sign*G*q/256)/Sf
        assert target.min()>=0 and target.max()<=1
        # theta[0]=0 and reset state=0 preserve exact zero through all clocks.
        fit=lsq_linear(a[:,1:],target,bounds=(0,1),tol=1e-12,max_iter=1000)
        if not fit.success:raise ValueError(fit.message)
        c=np.rint(np.r_[0,fit.x]*256).clip(0,256).astype(np.int16)
        m=a@c/256
        direct=np.rint(target*256).clip(0,256).astype(np.int16)
        coeff.append(c.tolist());lut.append(direct.tolist());mean.append(m.tolist())
        errors.append(dict(real_unit_mae=float(np.mean(np.abs(m-target))*Sf),
                           real_unit_max_error=float(np.max(np.abs(m-target))*Sf),
                           coefficient_codes=c.tolist()))
    return dict(G=G,states=states,Sneg=Sneg,cycles=cycles,init=0,theta=coeff,
                mean=mean,lut=lut,errors=errors,
                fit='uniform q=0..255, finite-T occupancy, theta0=0, bounded LS then P8 RNE')

def exact_count_moments(theta,q,qu,cycles):
    """Markov moments including an independent u comparator each clock."""
    q=np.asarray(q);pu=np.asarray(qu)/256
    v=np.zeros((q.size,len(theta)));v[:,0]=1;m=v*0;h=v*0
    t=np.asarray(theta)[None,:]/256*pu[:,None]
    for _ in range(cycles):
        v,m,h=(propagate(b,q/256) for b in (v,m,h))
        h+=2*t*m+t*v;m+=t*v
    mean=m.sum(1);var=np.maximum(0,h.sum(1)-mean**2)
    return mean,var
