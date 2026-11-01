"""Controlled extension of frozen Issue206 G64/B4; no catalog refit.

This module imports the immutable Issue206 snapshot via PYTHONPATH. Comparator
thresholds are int64 software containers, not additional stored hardware state.
shared9 stores sign+mag8; shared8 stores sign+mag7 and wires mag7<<1 into P8.
The existing sigmoid table/step1/8 field and sampling law remain unchanged.
"""
import torch
from torch.nn import functional as F
from qwen3.group_shared.group_sweep_core import GroupSweepFFN, encode_grouped
from qwen3.group_shared.independent_gate import original_g_field
from qwen3.group_shared.pot_weight import exact_pow2
from qwen3.group_shared.recal_core import catalog_accumulate
from qwen3.and_direct.multiscale_core import sigmoid_field
from qwen3.and_direct.short_core import joint_counts
from qwen3.and_direct.core import finish_bf16

MODES = ('independent9', 'shared9', 'shared8', 'raw9', 'raw8')


def raw_g_code(value, total_bits):
    """One signed value code:8total uses step1/8;9total step1/16.

    The ranges match the existing sigmoid field's approximately+-16 range.
    This is a separate encoding family from normalized amplitude storage.
    """
    fractional = total_bits-5
    if total_bits not in (8,9):raise ValueError(total_bits)
    limit = 1<<(total_bits-1)
    return (value.float()*(1<<fractional)).round().clamp(-limit,limit-1).long()


def thresholds_from_raw(code, exponent, total_bits):
    """Integer RNE and saturation into existing P8 amplitude comparator domain."""
    delta = 8-(total_bits-5)-exponent
    mag = code.abs();right = (-delta).clamp_min(0)
    assert not bool((right>40).any()) and not bool((delta>40).any())
    q = mag>>right;rem = mag-(q<<right)
    half = torch.ones_like(q)<<((right-1).clamp_min(0))
    inc = (right>0)&((rem>half)|((rem==half)&((q&1)!=0)))
    return torch.where(delta>=0,mag<<delta.clamp_min(0),q+inc.long()).clamp(0,255)


def field_from_raw(code,total_bits):
    if total_bits==8:return code
    return sigmoid_field(code.abs(),code.sign(),torch.tensor(4,device=code.device))


def amplitude_threshold(value, encoded, total_bits):
    """Direct RNE from upstream value at the SAME selected group exponent."""
    if total_bits == 9:
        return encoded[0]
    if total_bits != 8:
        raise ValueError('total width must be 8 or 9 including sign')
    # Do not round a pre-quantized mag8/2: that would double-round some values.
    scale = exact_pow2(encoded[2]).float()
    mag7 = (value.float().abs()/scale*128).round().clamp(0, 127).long()
    return mag7 << 1


class UnifiedGUFFN(GroupSweepFFN):
    def __init__(self, original, layer):
        super().__init__(original, layer)
        self.codec_mode = 'independent9'
        self.collect_codec_diagnostics = True
        # n,h_changed,|dh|,dh2,field_changed,z_error2,z_reference2,
        # g_cmp_changed,u_cmp_changed,g_zero,u_zero,g_cap,u_cap,field_saturated
        self.register_buffer('codec_stats', torch.zeros(14, dtype=torch.float64,
                                                       device=self.gu_codes.device))

    def set_codec(self, mode):
        if mode not in MODES:
            raise ValueError(mode)
        self.codec_mode = mode
        self.codec_stats.zero_()

    def _codec_probe(self, a, b, gc, uc, h, field, original_field):
        """At most16 deterministic evenly spaced token rows/layer/call.

        These are descriptive within-call probes, not whole-tensor or model
        accuracy. They compare both encodings at the SAME upstream g/u values.
        """
        nrows = gc.numel()//gc.shape[-1]
        idx = torch.linspace(0, nrows-1, min(16, nrows), device=gc.device).round().long()
        pick = lambda t: t.reshape(nrows, -1).index_select(0, idx)
        g0,u0 = pick(a[0]),pick(b[0]);g1,u1 = pick(gc),pick(uc)
        h0 = self.lut[pick(original_field)+128].long();h1 = pick(h)
        f = pick(field);dh = (h1-h0).double()/256
        exponent = pick(a[2])+pick(b[2])
        z0 = torch.ldexp((g0*h0*u0).double()/256**3, exponent)
        dz = torch.ldexp((g1*h1*u1-g0*h0*u0).double()/256**3, exponent)
        gcap = 254 if self.codec_mode == 'shared8' else 255
        ucap = 254 if self.codec_mode.endswith('8') else 255
        values = (g1.numel(), (h1!=h0).sum(), dh.abs().sum(), dh.square().sum(),
                  (f!=pick(original_field)).sum(), dz.square().sum(), z0.square().sum(),
                  (g1!=g0).sum(), (u1!=u0).sum(), (g1==0).sum(), (u1==0).sum(),
                  (g1==gcap).sum(), (u1==ucap).sum(), ((f==-128)|(f==127)).sum())
        for i,v in enumerate(values):
            self.codec_stats[i] += v

    def forward(self, x):
        if not self.sweep_enabled:
            raise RuntimeError('install frozen G64/B4 before using codec experiment')
        self.calls += 1
        g,u = self._stage(x.float(), 'x', 'gu', self.rng_input).chunk(2, -1)
        # Selection and carrier packing are byte-identical frozen dependencies.
        a = encode_grouped(g, self.g_levels, self.nl_group_size, self.g_carrier)
        b = encode_grouped(u, self.u_levels, self.nl_group_size, self.u_carrier)
        _,gs,ge,gh,gb = a;_,us,ue,uh,ub = b
        bits = 8 if self.codec_mode.endswith('8') else 9
        gc = amplitude_threshold(g, a, bits);uc = amplitude_threshold(u, b, bits)
        original_field = original_g_field(g)
        if self.codec_mode.startswith('raw'):
            stored_g = raw_g_code(g,bits)
            gc = thresholds_from_raw(stored_g,ge,bits)
            gs = stored_g.sign()
            field = field_from_raw(stored_g,bits)
        else:
            field = original_field if self.codec_mode == 'independent9' else sigmoid_field(gc, gs, ge)
        h = self.lut[field+128].long()
        for i,v,c,s,e,bin_id in ((1,g,gc,gs,ge,gb),(2,u,uc,us,ue,ub)):
            scale = exact_pow2(e).float()
            self._record(i,v,scale,c.double()/256,s*c.float()*scale/256,bin_id,True)
        if self.collect_codec_diagnostics:
            self._codec_probe(a,b,gc,uc,h,field,original_field)
        if self.nonlinear_mean:
            p = (gc*h*uc).double()/256**3
            self.event_stats[0] += p.numel();self.event_stats[1] += p.sum()
            value = torch.ldexp(gs*us*p, -gh-uh).float()
            return F.linear(value, self.fixed_effective_weight).to(x.dtype)
        counts,p = joint_counts((gc,h,uc),128,self.rng_and)
        self.event_stats[0] += p.numel();self.event_stats[1] += p.sum()
        self.event_stats[2] += (counts==0).sum()
        acc = catalog_accumulate(counts,gs*us,gh+uh,self.down_codes,
                                 self.coeff,128,self.catalog_limit)
        return finish_bf16(acc,self.output_exp-self.catalog_limit,128).to(x.dtype)

    def codec_report(self):
        s = self.codec_stats.tolist();n = max(s[0],1)
        return dict(mode=self.codec_mode,total_bits_per_g_or_u=8 if self.codec_mode.endswith('8') else 9,
            g_format='signed raw value,step1/'+str(1<<(8 if self.codec_mode.endswith('8') else 9)-5) if self.codec_mode.startswith('raw') else 'normalized sign+magnitude',
            sigmoid_source='original upstream g' if self.codec_mode=='independent9' else 'same stored code+shared PoT exponent',
            probe='at most16 deterministic evenly spaced token rows per layer/call;same upstream values',
            probe_elements=int(s[0]),gate_probability_changed_fraction=s[1]/n,
            gate_probability_mae=s[2]/n,gate_probability_rmse=(s[3]/n)**.5,
            gate_field_changed_fraction=s[4]/n,
            conditional_z_change_nmse=s[5]/max(s[6],1e-30),
            amplitude_g_changed_fraction=s[7]/n,amplitude_u_changed_fraction=s[8]/n,
            g_zero_fraction=s[9]/n,u_zero_fraction=s[10]/n,
            g_cap_fraction=s[11]/n,u_cap_fraction=s[12]/n,
            sigmoid_field_saturation_fraction=s[13]/n,raw_codec_stats=s,
            waveform_or_PPA=False)
