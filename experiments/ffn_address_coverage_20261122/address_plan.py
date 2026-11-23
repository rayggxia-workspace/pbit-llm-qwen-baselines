"""Integer/address reference for a proposed FFN sampler. Not TLM or RTL.

The input is already encoded: |v_i| = q_i * 2**(e_i-fractional_bits).
No float normalization, sigmoid, or model-dependent oracle is used here.
"""
from collections import Counter
from dataclasses import dataclass


class SumTree:
    def __init__(self, values):
        values = list(values)
        if not values or any(type(x) is not int or x < 0 for x in values):
            raise ValueError('nonempty nonnegative integer masses required')
        self.length = len(values)
        self.width = 1 << (len(values)-1).bit_length()
        self.nodes = [0]*(2*self.width)
        self.nodes[self.width:self.width+len(values)] = values
        for i in range(self.width-1, 0, -1):
            self.nodes[i] = self.nodes[2*i]+self.nodes[2*i+1]

    @property
    def total(self):
        return self.nodes[1]

    def select(self, ticket):
        """Return leaf and residual ticket using integer compare/subtract."""
        if type(ticket) is not int or not 0 <= ticket < self.total:
            raise ValueError('ticket outside positive total mass')
        node = 1
        while node < self.width:
            left = self.nodes[2*node]
            if ticket < left:
                node *= 2
            else:
                ticket -= left
                node = 2*node+1
        index = node-self.width
        assert index < self.length
        return index, ticket


class AddressSampler:
    def __init__(self, codes, exponents, signs, fractional_bits=8, group=64):
        self.codes, self.exponents, self.signs = map(tuple, (codes, exponents, signs))
        n = len(self.codes)
        if n == 0 or len(self.exponents) != n or len(self.signs) != n or group < 1:
            raise ValueError('matching nonempty encoded vector required')
        if any(type(q) is not int or not 0 <= q <= 256 for q in self.codes):
            raise ValueError('P8 integer code, including full-one code256, required')
        if any(type(e) is not int for e in self.exponents):
            raise ValueError('integer power-of-two exponents required')
        if any(s not in (-1, 1) for s in self.signs) or fractional_bits < 0:
            raise ValueError('separate signs and nonnegative fractional bits required')
        # e_min is a format/configuration parameter derived from the supplied
        # scale table, not a dynamic maximum of the floating-point activations.
        self.minimum_exponent = min(self.exponents)
        self.fractional_bits = fractional_bits
        self.group = group
        self.masses = tuple(q << (e-self.minimum_exponent)
                            for q,e in zip(self.codes,self.exponents))
        self.local = [SumTree(self.masses[i:i+group]) for i in range(0,n,group)]
        self.top = SumTree(t.total for t in self.local)

    @property
    def total(self):
        return self.top.total

    def select_ticket(self, ticket):
        g, residual = self.top.select(ticket)
        j, _ = self.local[g].select(residual)
        return g*self.group+j

    def draw(self, samples, rng):
        """rng.getrandbits is the explicit uniform-bit service interface.

        Rejection removes the power-of-two range bias. No modulo fallback or
        hidden fixed-cycle guarantee. This is not a physical-RNG validation.
        """
        if type(samples) is not int or samples < 1:
            raise ValueError('positive address budget required')
        if self.total == 0:
            return dict(zero_input=True, requested_samples=samples,
                        effective_samples=0, proposals=0, random_bits=0, entries=[])
        bits = (self.total-1).bit_length()
        counts, proposals = Counter(), 0
        for _ in range(samples):
            while True:
                ticket = rng.getrandbits(bits) if bits else 0
                proposals += 1
                if type(ticket) is not int or not 0 <= ticket < (1 << bits):
                    raise ValueError('random source violated bit width')
                if ticket < self.total:
                    break
            counts[self.select_ticket(ticket)] += 1
        entries = [dict(input_index=i, count=c, sign=self.signs[i],
                        original_input_group=i//64)
                   for i,c in sorted(counts.items())]
        assert sum(x['count'] for x in entries) == samples
        return dict(zero_input=False, requested_samples=samples,
                    effective_samples=samples, proposals=proposals,
                    random_bits=proposals*bits, entries=entries)


@dataclass(frozen=True)
class StripeLayout:
    inputs: int
    outputs: int
    projections: int = 1
    output_chunk: int = 512
    weight_bytes: int = 1
    base: int = 0

    def __post_init__(self):
        if min(self.inputs,self.outputs,self.projections,self.output_chunk,self.weight_bytes) < 1:
            raise ValueError('positive layout dimensions required')
        if self.base < 0 or self.base % 512:
            raise ValueError('512-byte-aligned nonnegative base required')

    @property
    def strips(self):
        return (self.outputs+self.output_chunk-1)//self.output_chunk

    @property
    def packet_bytes(self):
        return self.projections*self.output_chunk*self.weight_bytes

    @property
    def storage_bytes(self):
        return self.strips*self.inputs*self.packet_bytes

    def address(self, input_index, output_index, projection=0):
        if not (0 <= input_index < self.inputs and 0 <= output_index < self.outputs
                and 0 <= projection < self.projections):
            raise ValueError('matrix index outside layout')
        strip, lane = divmod(output_index,self.output_chunk)
        return (self.base+(strip*self.inputs+input_index)*self.packet_bytes
                +(projection*self.output_chunk+lane)*self.weight_bytes)

    def reads(self, entries):
        ids = [x['input_index'] for x in entries]
        if len(ids) != len(set(ids)) or any(not 0 <= i < self.inputs for i in ids):
            raise ValueError('unique valid input entries required')
        if any(type(x['count']) is not int or x['count'] < 1 or x['sign'] not in (-1,1)
               for x in entries):
            raise ValueError('positive counts and separate signs required')
        result=[]
        for strip in range(self.strips):
            valid=min(self.output_chunk,self.outputs-strip*self.output_chunk)
            for entry in sorted(entries,key=lambda x:x['input_index']):
                i=entry['input_index']
                result.append(dict(strip=strip, output_start=strip*self.output_chunk,
                    valid_outputs=valid, input_index=i, count=entry['count'],
                    sign=entry['sign'], original_input_group=i//64,
                    address=self.base+(strip*self.inputs+i)*self.packet_bytes,
                    bytes=self.packet_bytes,
                    useful_bytes=self.projections*valid*self.weight_bytes))
        return result


def count_pulses(counts):
    """Deterministic replay AFTER stochastic address selection; exact sum only.

    One group uses max(counts) pulses. It does not redraw addresses or simulate
    Bernoulli input probabilities. OR aggregation is not equivalent.
    """
    if any(type(c) is not int or c < 0 for c in counts):
        raise ValueError('nonnegative integer counts required')
    for t in range(max(counts,default=0)):
        yield [int(c > t) for c in counts]
