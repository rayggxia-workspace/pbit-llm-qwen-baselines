"""Bit-exact Bivium-B recurrence and functional FFN random-stream contract.

Independent Python reference of the public Bivium recurrence (177-bit state).
Tap numbering agrees with OpenTitan prim_trivium_pkg.sv, zero based, first
generated bit in bit 0. This is NOT a port of OpenTitan control/seed RTL.
SHAKE domain separation below is a deterministic simulation seed expander,
not a claim of SP800-90A/C compliance or a physical entropy implementation.
"""
import hashlib
import json
from collections import deque


class Bivium:
    STATE_BITS = 177

    def __init__(self, state, warmup_bits=800):
        if not isinstance(state,int) or not 0 < state < 1 << 177:
            raise ValueError('Bivium state must be nonzero and fit 177 bits')
        if not isinstance(warmup_bits,int) or warmup_bits<0:
            raise ValueError('invalid warmup')
        self.a = state & ((1<<93)-1)
        self.b = state >> 93
        self.generated = 0
        self.read_word(warmup_bits)
        self.generated = 0

    @property
    def state(self):
        return self.a | (self.b<<93)

    def read_word(self, width):
        if not isinstance(width,int) or width<0:
            raise ValueError('invalid output width')
        a,b=self.a,self.b
        word=0
        for i in range(width):
            t1=((a>>65)^(a>>92))&1
            t2=((b>>68)^(b>>83))&1
            word |= (t1^t2)<<i
            fa=t2^(((b>>81)&(b>>82))&1)^((a>>68)&1)
            fb=t1^(((a>>90)&(a>>91))&1)^((b>>77)&1)
            a=((a<<1)|fa)&((1<<93)-1)
            b=((b<<1)|fb)&((1<<84)-1)
        self.a,self.b=a,b
        self.generated+=width
        return word


def derive_state(material, epoch, domain, identity):
    if not isinstance(material,bytes) or len(material)<32:
        raise ValueError('provide at least 32 bytes of simulated or conditioned seed material')
    if not isinstance(epoch,int) or epoch<0:
        raise ValueError('invalid epoch')
    tag=json.dumps(['ffn-rng-v1',epoch,domain,list(identity)],separators=(',',':')).encode()
    state=int.from_bytes(hashlib.shake_256(len(material).to_bytes(8,'little')+material+tag).digest(23),'little')&((1<<177)-1)
    if state==0:
        # Domain-separated retry avoids silently sending the all-zero lockup state.
        return derive_state(hashlib.sha256(material+b'nonzero').digest(),epoch,domain,identity)
    return state


class FunctionalRng:
    """Local stream identity=(engine,column,core); separate shared-input domain.

    Persistent state is reused across weight/probability changes. Input streams
    may be cached explicitly by replay_key and broadcast across output columns.
    No cached/replayed weight randomness. Reseed only at an idle tile boundary.
    """
    def __init__(self, material, cores_per_column=4, output_bits=160,
                 shared_cores=8, warmup_cycles=5, epoch=0):
        if any(not isinstance(x,int) or x<1 for x in
               (cores_per_column,output_bits,shared_cores,warmup_cycles)):
            raise ValueError('positive integer dimensions required')
        if output_bits%8 or cores_per_column*output_bits//8<64:
            raise ValueError('at least 64 whole-byte candidates per column required')
        self.cores_per_column=cores_per_column
        self.width=output_bits
        self.shared_cores=shared_cores
        self.warmup=warmup_cycles*output_bits
        self.epoch=-1
        self.reseed(material,epoch)

    def reseed(self, material, epoch):
        if epoch<=self.epoch:
            raise ValueError('epoch must increase; instantiate anew for deterministic replay')
        derive_state(material,epoch,'validation',(0,))
        self.material=material;self.epoch=epoch
        self.streams={};self.shared_bits=deque();self.replay={}

    def stream(self,domain,identity):
        key=(domain,tuple(identity))
        if key not in self.streams:
            self.streams[key]=Bivium(derive_state(self.material,self.epoch,domain,identity),self.warmup)
        return self.streams[key]

    def input_bits(self,probabilities,replay_key=None):
        """12-bit activation codes 0..4096 -> Bernoulli. Return a shared row."""
        probs=tuple(probabilities)
        if any(not isinstance(p,int) or not 0<=p<=4096 for p in probs):
            raise ValueError('input probability codes must lie in 0..4096')
        if replay_key is not None and replay_key in self.replay:
            old,bits=self.replay[replay_key]
            if old!=probs:raise ValueError('replay key reused with different probabilities')
            return list(bits)
        result=[]
        for p in probs:
            while len(self.shared_bits)<12:
                for core in range(self.shared_cores):
                    word=self.stream('shared-input',(core,)).read_word(self.width)
                    self.shared_bits.extend((word>>i)&1 for i in range(self.width))
            value=sum(self.shared_bits.popleft()<<i for i in range(12))
            result.append(int(value<p))
        if replay_key is not None:self.replay[replay_key]=(probs,tuple(result))
        return result

    def release_replay(self,replay_key=None):
        """Release a completed input replay window instead of caching forever."""
        if replay_key is None:self.replay.clear()
        else:self.replay.pop(replay_key,None)

    def weight_bits(self,engine,probabilities):
        """Rows=output columns, 64 weight magnitude codes per row, each 0..127.

        A column draws all cores once per attempt, takes the first 64 accepted
        bytes (<254, then //2). Underflow discards that attempt and retries.
        Successful columns freeze. Return bits plus actual cycle/update counts.
        """
        if not isinstance(engine,int) or engine<0:raise ValueError('invalid engine identity')
        rows=[tuple(row) for row in probabilities]
        if not 1<=len(rows)<=64 or any(len(row)!=64 for row in rows):
            raise ValueError('1..64 output columns, each with 64 input connections')
        if any(not isinstance(p,int) or not 0<=p<=127 for row in rows for p in row):
            raise ValueError('weight magnitude codes must lie in 0..127')
        result=[];attempts=[];rejected=0
        for col,probs in enumerate(rows):
            count=0
            while True:
                count+=1;accepted=[]
                for core in range(self.cores_per_column):
                    word=self.stream('weight',(engine,col,core)).read_word(self.width)
                    for i in range(self.width//8):
                        v=(word>>(8*i))&255
                        if v<254:accepted.append(v//2)
                        else:rejected+=1
                if len(accepted)>=64:break
            result.append([int(v<p) for v,p in zip(accepted[:64],probs)])
            attempts.append(count)
        return result,dict(cycles=max(attempts),core_updates=sum(attempts)*self.cores_per_column,
                           rejected_bytes=rejected,attempts=attempts)
