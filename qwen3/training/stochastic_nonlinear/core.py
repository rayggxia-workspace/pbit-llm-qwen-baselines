"""Research training reference, not a fused kernel or a complete RTL model.

Hard forward reuses PR174's joint32 sampler and integer Wd oracle. No sampled
z re-encoding, no FP32 SiLU on the hard nonlinear path. Wg/Wu restoration
retains the documented FP32 reference boundary. Backward is biased STE,
NOT a derivative of the discrete distribution or a physical circuit.
"""
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import hashlib
import json
import torch
from torch import nn
from torch.nn import functional as F
from qwen3.fixed_scale.static_core import _validated_scales, _encode_static_validated
from qwen3.stochastic.vendor.stratified_core import stratified_counts
from qwen3.and_direct.short_core import encode_fixed, joint_counts, POLICIES
from qwen3.and_direct.multiscale_core import sigmoid_field, shifted_output
from qwen3.and_direct.core import coefficient_table, finish_bf16
from qwen3.nonlinear_width.core import make_lut


@dataclass(frozen=True)
class Config:
    weight_bits: int = 8
    input_samples: int = 64
    input_strata: int = 64
    nonlinear_samples: int = 128
    policy: str = 'lower_half'

    def __post_init__(self):
        if self.weight_bits not in (4, 6, 8):
            raise ValueError('weight_bits must be 4, 6 or 8')
        if (self.input_samples, self.input_strata) != (64, 64):
            raise ValueError('this implementation freezes input T=K=64')
        if self.nonlinear_samples not in (32, 64, 128):
            raise ValueError('joint32 requires T=32,64,128')
        if self.policy not in POLICIES:
            raise ValueError('unknown fixed g/u scale policy')


@dataclass(frozen=True)
class NoiseKey:
    seed: int
    step: int = 0
    microbatch: int = 0
    rank: int = 0

    def generator(self, device, layer, stage):
        # Stable across Python processes; independent stage/rank/microbatch.
        payload = json.dumps([self.seed, self.step, self.microbatch, self.rank,
                              layer, stage], separators=(',', ':')).encode('ascii')
        seed = int.from_bytes(hashlib.sha256(payload).digest()[:8], 'little') % (2**63-1)
        return torch.Generator(device=device).manual_seed(seed)


class _Attach(torch.autograd.Function):
    @staticmethod
    def forward(ctx, hard, proxy):
        return hard.clone()  # Avoid hard + proxy - proxy.detach() rounding.

    @staticmethod
    def backward(ctx, grad):
        return None, grad


def attach(hard, proxy):
    return _Attach.apply(hard.detach(), proxy)


def quantize(weight, bits):
    rows, cols = weight.shape
    if rows % 64 or cols % 64:
        raise ValueError('64 x 64 weight tiles required')
    tiles = weight.detach().float().reshape(rows//64, 64, cols//64, 64).permute(0,2,1,3)
    limit = 2**(bits-1)-1
    lsb = tiles.abs().amax((-1,-2)).clamp_min(1e-20) / limit
    codes = (tiles / lsb[...,None,None]).round().clamp(-limit,limit).to(torch.int16)
    codes = codes.permute(0,2,1,3).reshape(rows,cols)
    decoded = codes.float()*lsb.repeat_interleave(64,0).repeat_interleave(64,1)
    return codes, decoded, lsb


def _top(value, groups, device):
    t = torch.as_tensor(value, dtype=torch.float64).detach().cpu()
    if tuple(t.shape) != (groups,) or not bool(torch.isfinite(t).all()) or not bool((t>0).all()):
        raise ValueError('g/u tops must be finite positive per-group vectors')
    m, e = torch.frexp(t)
    if not bool((m==.5).all()) or bool(((e-1 < -20)|(e-1 > 20)).any()):
        raise ValueError('g/u top must be a power of two with exponent in [-20,20]')
    return t.float().to(device).clone()


def hard_forward(x, wg, wu, wd, module, key):
    """Actual finite forward; all caller paths disable autocast and TF32."""
    cfg = module.config
    with torch.no_grad(), torch.autocast(device_type=x.device.type, enabled=False):
        if x.is_cuda and torch.backends.cuda.matmul.allow_tf32:
            raise ValueError('disable TF32 for bounded exact integer-container GEMMs')
        enc = _encode_static_validated(x.float(), module.x_scales)
        counts_x = stratified_counts(enc['probability'], cfg.input_samples,
            cfg.input_strata, key.generator(x.device, module.layer, 'input'), 64)
        _, gu_dq, _ = quantize(torch.cat((wg,wu),0), cfg.weight_bits)
        dc, _, dl = quantize(wd, cfg.weight_bits)
        # Preserve the inference oracle's operation order (divide after GEMM).
        g, u = (F.linear(enc['sign']*enc['scale']*counts_x, gu_dq)/cfg.input_samples).chunk(2,-1)
        gc, gs, ge, gshift = encode_fixed(g, module.g_top, module.offsets)
        uc, us, ue, ushift = encode_fixed(u, module.u_top, module.offsets)
        field = sigmoid_field(gc,gs,ge)
        hc = module.lut[field+128].long()
        counts, _ = joint_counts((gc,hc,uc), cfg.nonlinear_samples,
            key.generator(x.device, module.layer, 'and'))
        coeff, exponent, _ = coefficient_table(dl,module.g_top,module.u_top)
        R = 2*max(module.offsets)
        acc = shifted_output(counts,gs*us,gshift+ushift,dc,coeff,cfg.nonlinear_samples,R)
        y = finish_bf16(acc,exponent-R,cfg.nonlinear_samples).to(x.dtype)
        # Cache for the surrogate only: these are NOT deployed z registers.
        xhat = enc['sign']*enc['scale']*counts_x/cfg.input_samples
        sg, su = torch.ldexp(torch.ones_like(g),ge), torch.ldexp(torch.ones_like(u),ue)
        zsample = (gs*us).float()*sg*su*counts/cfg.nonlinear_samples
        scale = torch.ldexp(coeff.double(),exponent[:,None]-16)
        scale = scale/(module.g_top*module.u_top).double()[None,:]
        effective_wd = (dc.double()*scale.repeat_interleave(64,0).repeat_interleave(64,1)).float()
        cache = (xhat, g, u, gc.float()*gs*sg/256, uc.float()*us*su/256,
                 sg, su, field.float()*.125, hc.float()/256, zsample, gu_dq, effective_wd)
        return y, cache


def surrogate(x, wg, wu, wd, module, cache):
    """Explicit biased STE, invoked ONLY by backward.

    Gradients treat PoT bin selection, weight scales and coefficients as fixed.
    Clipped activation and signed8-field derivatives are zero outside range.
    Wd gradient sees actual sampled z. Upstream gradient uses a quantized
    conditional-mean surrogate; its sigmoid derivative is backward-only.
    """
    xhat,g,u,gq,uq,sg,su,field,hprob,zsample,gu_dq,effective_wd = cache
    top = module.x_scales[:,0].repeat_interleave(64)
    xx = attach(xhat, torch.maximum(torch.minimum(x.float(),top),-top))
    gw, uw = attach(gu_dq,torch.cat((wg,wu),0)).chunk(2,0)
    gg, uu = attach(g,F.linear(xx,gw)), attach(u,F.linear(xx,uw))
    gg = attach(gq,torch.maximum(torch.minimum(gg,sg*255/256),-sg*255/256))
    uu = attach(uq,torch.maximum(torch.minimum(uu,su*255/256),-su*255/256))
    drive = attach(field,gg.clamp(-16.,15.875))
    pp = attach(hprob,torch.sigmoid(drive))
    zz = attach(zsample,gg*uu*pp)
    return F.linear(zz,attach(effective_wd,wd))


class _StochasticFFN(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x, wg, wu, wd, module, key):
        y, cache = hard_forward(x,wg,wu,wd,module,key)
        ctx.module = module
        ctx.save_for_backward(x,wg,wu,wd,*cache)
        return y

    @staticmethod
    def backward(ctx, grad):
        saved = ctx.saved_tensors
        with torch.enable_grad(), torch.autocast(device_type=grad.device.type,enabled=False):
            # Rebuild a surrogate graph, without drawing another random number.
            leaves = [v.detach().float().requires_grad_(True) for v in saved[:4]]
            proxy = surrogate(*leaves,ctx.module,saved[4:])
            grads = torch.autograd.grad(proxy,leaves,grad.float())
        return tuple(g.to(v.dtype) if needed else None for g,v,needed in
                     zip(grads,saved[:4],ctx.needs_input_grad[:4])) + (None,None)


class TrainableFFN(nn.Module):
    def __init__(self, original, tables, layer, config=Config()):
        super().__init__()
        self.config, self.layer = config, int(layer)
        self.offsets = POLICIES[config.policy]
        device = original.gate_proj.weight.device
        for name in ('gate_proj','up_proj','down_proj'):
            old = getattr(original,name)
            if old.bias is not None:
                raise ValueError('this contract is bias-free Qwen3 FFN')
            # Reuse Parameter identity/names; cast masters before creating optimizer.
            setattr(self,name,old.float())
            old.weight.requires_grad_(True)
        hidden = self.gate_proj.in_features
        width = self.gate_proj.out_features
        if self.up_proj.weight.shape != self.gate_proj.weight.shape or \
                tuple(self.down_proj.weight.shape)!=(hidden,width):
            raise ValueError('gate/up/down shape mismatch')
        self.register_buffer('x_scales',_validated_scales(tables['x'],hidden//64,device))
        self.register_buffer('g_top',_top(tables['g'],width//64,device))
        self.register_buffer('u_top',_top(tables['u'],width//64,device))
        self.register_buffer('lut',make_lut(8,8).to(device))
        self.noise_key = None

    def forward(self,x):
        if self.noise_key is None:
            raise RuntimeError('use noise_context around BOTH forward and backward')
        if x.shape[-1]!=self.gate_proj.in_features or x.dtype not in (torch.float32,torch.bfloat16):
            raise ValueError('expected FP32/BF16 container with correct hidden width')
        return _StochasticFFN.apply(x,self.gate_proj.weight,self.up_proj.weight,
                                   self.down_proj.weight,self,self.noise_key)


def trainable_names(model):
    return [name for name,p in model.named_parameters() if p.requires_grad]


def install(model, calibration, config=Config()):
    """Patch all decoder FFNs. Call AFTER loading old weights, BEFORE optimizer/DDP.

    calibration['layers'] keys are decimal layer indices. Frozen normalizations,
    embeddings, attention and lm_head retain the loaded checkpoint's values.
    """
    layers = model.model.layers
    expected = {str(i) for i in range(len(layers))}
    if set(calibration['layers'])!=expected:
        raise ValueError('exact all-layer calibration coverage required')
    if any(isinstance(layer.mlp,TrainableFFN) for layer in layers):
        raise ValueError('model is already patched')
    model.requires_grad_(False)
    for i,layer in enumerate(layers):
        layer.mlp = TrainableFFN(layer.mlp,calibration['layers'][str(i)],i,config)
    names = trainable_names(model)
    if len(names)!=3*len(layers) or any(not n.endswith(tuple(
            'mlp.'+p+'.weight' for p in ('gate_proj','up_proj','down_proj'))) for n in names):
        raise AssertionError('FFN-only training audit failed')
    return names


@contextmanager
def noise_context(model,key):
    """One microbatch: forward, loss, backward must all occur inside this scope.

    Non-reentrant activation checkpoint replay therefore sees the same key.
    No mutable RNG cursor. Do not start another microbatch before backward.
    """
    modules = [m for m in model.modules() if isinstance(m,TrainableFFN)]
    if not modules:
        raise ValueError('no trainable stochastic FFN installed')
    previous = [m.noise_key for m in modules]
    try:
        for m in modules: m.noise_key = key
        yield
    finally:
        for m,old in zip(modules,previous): m.noise_key = old


def contract(config):
    return dict(config=asdict(config),input_rng='R8 shared64, T=K=64',
        nonlinear_rng='32 Cartesian cells (4,2,4), independent lanes and axes',
        hard_forward='P8 g/u, signed8 field, frozen P8 LUT, AND counts, integer Wd, BF16 RNE',
        backward='biased STE; sampled-z Wd gradient; conditional-mean upstream gradient',
        gate_up_restore_bittrue=False,z_reencoding=False,trainable='gate/up/down weights only')
