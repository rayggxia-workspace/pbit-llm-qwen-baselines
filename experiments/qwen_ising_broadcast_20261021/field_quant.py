"""Quantize the sigmoid argument, NOT Q/K or the output probability.

All values use natural-log score units. Masked sites stay externally disabled.
"""
import numpy as np


FORMATS = [
    dict(name='signed8_h1', bits=8, step=1., negative_only=False),
    dict(name='signed8_h1_2', bits=8, step=.5, negative_only=False),
    dict(name='signed8_h1_4', bits=8, step=.25, negative_only=False),
    dict(name='signed8_h1_8', bits=8, step=.125, negative_only=False),
    dict(name='signed8_h1_16', bits=8, step=.0625, negative_only=False),
    dict(name='negative8_h1_8', bits=8, step=.125, negative_only=True),
    dict(name='negative8_h1_16', bits=8, step=.0625, negative_only=True),
    dict(name='signed10_h1_16', bits=10, step=.0625, negative_only=False),
    dict(name='signed12_h1_16', bits=12, step=.0625, negative_only=False),
]


def limits(bits, step, negative_only=False):
    if bits < 2 or step <= 0: raise ValueError('invalid format')
    return (-(2**bits-1)*step, 0.) if negative_only else (-(2**(bits-1))*step, (2**(bits-1)-1)*step)


def quantize_field(a, bits, step, negative_only=False, name=None):
    lo,hi=limits(bits,step,negative_only)
    return np.clip(np.rint(np.asarray(a)/step),lo/step,hi/step)*step


def accepted_law(delta, shift, field=None):
    """Exact law conditional on accepting a fixed-shift proposal.

    delta is finite or -inf, max=0. The first argmax is the disabled reference.
    field is the already-quantized complete sigmoid argument. Empty correction
    stays 2**(-shift); reference log weight is exactly zero.
    """
    d=np.asarray(delta,dtype=np.float64)
    m=np.broadcast_to(np.asarray(shift,dtype=np.float64),(len(d),))
    a=d-m[:,None]*np.log(2.) if field is None else np.asarray(field,dtype=np.float64)
    score=a+m[:,None]*np.log(2.)
    score=np.where(np.isfinite(d),score,-np.inf)
    score[np.arange(len(d)),d.argmax(1)]=0.
    score=score-score.max(1)[:,None]
    weight=np.exp(score)
    return weight/weight.sum(1)[:,None]
