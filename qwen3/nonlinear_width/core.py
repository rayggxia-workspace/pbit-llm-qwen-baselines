"""Finite nonlinear interface, conditional-mean diagnostic (no AND sampling).

Matrix restoration remains the historical FP32 oracle. Amplitude uses b
unsigned magnitude bits plus sign, fixed per-group PoT scale, no full-one.
Sigmoid driver: signed f bits, step=32/2**f, saturation to [-16,16-step].
Probability: q/2**p with explicit true-one; stored LUT is frozen before eval.
"""
import hashlib
import torch
from torch.nn import functional as F
from qwen3.fixed_scale.static_core import StaticFFN


def magnitude(value, scales, bits):
    if bits == 0:
        return value, torch.zeros_like(value, dtype=torch.bool)
    if not 2 <= bits <= 12:
        raise ValueError('Supported magnitude bits: 2..12')
    top = scales.repeat_interleave(64)
    codes = (value.abs() / top * (2**bits)).round().clamp(0, 2**bits-1)
    return value.sign() * codes * (top / (2**bits)), value.abs() > top*(1-2**(-bits))


def make_lut(field_bits, probability_bits):
    if field_bits not in (8,10,12) or probability_bits not in (0,6,8,10,12):
        raise ValueError('Unsupported LUT format')
    step = 32. / (2**field_bits)
    field = torch.arange(-(2**(field_bits-1)), 2**(field_bits-1), dtype=torch.float64)*step
    p = torch.sigmoid(field)
    if probability_bits:
        return (p*(2**probability_bits)).round().clamp(0,2**probability_bits).to(torch.int16)
    return p # diagnostic: isolate driver quantization, output not quantized


def probability(g, field_bits, probability_bits, lut=None):
    if field_bits:
        half = 2**(field_bits-1)
        code = (g/(32./(2**field_bits))).round().clamp(-half, half-1).long()
        p = lut[code+half].double()
        if probability_bits:
            p = p/(2**probability_bits)
    else:
        p = torch.sigmoid(g.double())
        if probability_bits:
            p = (p*(2**probability_bits)).round().clamp(0,2**probability_bits)/(2**probability_bits)
    return p


class NonlinearFFN(StaticFFN):
    def __init__(self, original, layer):
        super().__init__(original, mode='w8_only', layer=layer)
        self.spec = (0,0,0)
        self.capture_gu = None
        self.register_buffer('g_top', torch.ones(self.width//64, device=self.gu_decoded.device))
        self.register_buffer('u_top', torch.ones(self.width//64, device=self.gu_decoded.device))
        self.register_buffer('lut', torch.empty(0,device=self.gu_decoded.device))
        # n, gclip, uclip, zero-g, zero-u, g-SSE/g-power, u-SSE/u-power, z-SSE/z-power
        self.register_buffer('nl_stats',torch.zeros(11,dtype=torch.float64,device=self.gu_decoded.device))

    def set_spec(self, amplitude_bits=0, field_bits=0, probability_bits=0):
        self.spec = (amplitude_bits,field_bits,probability_bits)
        self.lut = make_lut(field_bits,probability_bits).to(self.gu_decoded.device) if field_bits else torch.empty(0,device=self.gu_decoded.device)
        self.nl_stats.zero_()

    def forward(self,x):
        self.calls += 1
        g,u=self._stage(x.float(),'x','gu',self.rng_input).chunk(2,-1)
        if self.capture_gu is not None:
            self.capture_gu(self.layer,'g',g)
            self.capture_gu(self.layer,'u',u)
        a,f,p=self.spec
        if not any(self.spec):
            z=F.silu(g)*u
        else:
            gq,gclip=magnitude(g,self.g_top,a)
            uq,uclip=magnitude(u,self.u_top,a)
            prob=probability(gq,f,p,self.lut)
            # With all fields quantized, numerator has <=36 bits and PoT
            # scales: FP64 evaluates this conditional mean exactly in range.
            # Casting z to FP32 is the explicit old down-interface oracle.
            z=(gq.double()*uq.double()*prob).float()
            ref=F.silu(g)*u
            sums=[g.numel(),gclip.sum(),uclip.sum(),(gq==0).sum(),(uq==0).sum(),
                  (gq-g).square().sum(dtype=torch.float64),g.square().sum(dtype=torch.float64),
                  (uq-u).square().sum(dtype=torch.float64),u.square().sum(dtype=torch.float64),
                  (z-ref).square().sum(dtype=torch.float64),ref.square().sum(dtype=torch.float64)]
            for i,s in enumerate(sums):self.nl_stats[i]+=s
        return self._stage(z,'z','down',self.rng_product).to(x.dtype)

    def nonlinear_report(self):
        s=self.nl_stats.tolist()
        raw=self.lut.detach().cpu().contiguous().numpy().tobytes()
        return dict(amplitude_bits_plus_sign=self.spec[0],field_signed_bits=self.spec[1],
            probability_bits_plus_true_one=self.spec[2],lut_sha256=hashlib.sha256(raw).hexdigest(),
            lut_entries=self.lut.numel(),field_range=[-16,16],rounding='nearest_even',
            raw_stats=s,g_clip_fraction=s[1]/max(s[0],1),u_clip_fraction=s[2]/max(s[0],1),
            g_nmse=s[5]/max(s[6],1e-30),u_nmse=s[7]/max(s[8],1e-30),z_nmse=s[9]/max(s[10],1e-30),
            conditional_mean_only=True,nonlinear_samples=0,matrix_bittrue=False)
