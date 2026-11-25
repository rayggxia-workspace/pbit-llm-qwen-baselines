"""GF(2) jump reference derived from RTL; not a hardware cost/latency model."""
import hashlib
import re

def rows_from_rtl(path):
    raw=path.read_bytes(); names={'state[%d]'%i:1<<i for i in range(32)}
    for lhs,rhs in re.findall(r'assign\s+([\w\[\]]+)\s*=\s*([^;]+);',raw.decode()):
        terms=rhs.split('^'); value=0
        for term in terms: value ^= names[term.strip()]
        names[lhs]=value
    return [names['next_state[%d]'%i] for i in range(32)],hashlib.sha256(raw).hexdigest()


class Jump:
    def __init__(self,rows):
        assert len(rows)==32
        self.rows=rows
        columns=[sum(((rows[i]>>j)&1)<<i for i in range(32)) for j in range(32)]
        self.powers=[columns]
    def step(self,state):
        return sum((bin(row&state).count('1')&1)<<i for i,row in enumerate(self.rows))
    @staticmethod
    def apply(columns,state):
        value=0; bit=0
        while state:
            if state&1: value ^= columns[bit]
            bit+=1;state>>=1
        return value
    def jump(self,state,steps):
        assert steps>=0 and 0<=state<2**32
        bit=0
        while steps:
            if bit==len(self.powers):
                old=self.powers[-1];self.powers.append([self.apply(old,x) for x in old])
            if steps&1:state=self.apply(self.powers[bit],state)
            bit+=1;steps>>=1
        return state
    def tile(self,seeds,mode,out,k,kblocks,samples):
        steps=(out*kblocks+k)*samples
        chosen=seeds[:1] if mode=='GU' else seeds[1:]
        return tuple(self.jump(s,steps) for s in chosen)
