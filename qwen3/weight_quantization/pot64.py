"""One frozen power-of-two LSB per 64x64 weight tile.

The exponent is chosen offline on initial/warm-start weights, not from runtime
activations. Training reuses the stored exponent; only integer codes change.
FP32 tensors below are simulation containers for Q * 2**exponent. They do not
imply floating-point weight MACs in the proposed circuit.
"""
import torch

FORMAT = 'signed-pow2-tile64-frozen-v1'
BLOCK = 64


def _tiles(weight, bits):
    if bits not in (4, 6, 8, 9, 10):
        raise ValueError('supported total signed weight widths: 4, 6, 8, 9, 10')
    if weight.ndim != 2 or any(n % BLOCK for n in weight.shape):
        raise ValueError('weight matrix must be divisible into 64x64 tiles')
    if not bool(torch.isfinite(weight).all()):
        raise ValueError('weight matrix contains nonfinite values')
    rows, cols = weight.shape
    return (weight.detach().float().reshape(rows // BLOCK, BLOCK,
            cols // BLOCK, BLOCK).permute(0, 2, 1, 3))


def choose_exponents(weight, bits=8):
    """Smallest dyadic step covering the initial tile max; no selected clipping.

    Exact power-of-two boundaries use frexp instead of rounded log2/ceil.
    An all-zero tile receives the documented step 2**-24. This initializer
    is not claimed to be the best language-model calibration criterion.
    """
    tiles = _tiles(weight, bits)
    maximum = tiles.double().abs().amax((-1, -2))
    ratio = maximum / (2 ** (bits - 1) - 1)
    mantissa, exponent = torch.frexp(ratio)
    chosen = exponent - (mantissa == .5).to(exponent.dtype)
    chosen = torch.where(maximum == 0, torch.full_like(chosen, -24), chosen)
    # Normal FP32 containers and one signed byte of hardware exponent state.
    if bool(((chosen < -126) | (chosen > 120)).any()):
        raise ValueError('weight exponent is outside the supported [-126,120] contract')
    return chosen.to(torch.int8).contiguous()


def validate_exponents(weight, exponents):
    wanted = (weight.shape[0] // BLOCK, weight.shape[1] // BLOCK)
    raw = torch.as_tensor(exponents, device=weight.device)
    if tuple(raw.shape) != wanted:
        raise ValueError('frozen exponent table shape mismatch')
    if raw.dtype not in (torch.int8, torch.int16, torch.int32, torch.int64):
        raise ValueError('weight exponents must be integers')
    if bool(((raw < -126) | (raw > 120)).any()):
        raise ValueError('frozen weight exponent outside supported range')
    return raw.to(torch.int8).contiguous().clone()


def quantize(weight, bits=8, exponents=None):
    """Return signed codes, decoded container and dyadic tile LSB.

    Pass stored exponents during every training/inference call. Omitting them
    is an explicit offline initialization operation, never an activation-max
    operation. Nearest-even rounding, symmetric signed-magnitude saturation.
    """
    tiles = _tiles(weight, bits)
    if exponents is None:
        exponents = choose_exponents(weight, bits)
    else:
        exponents = validate_exponents(weight, exponents)
    exponent = exponents.to(torch.int32)
    limit = 2 ** (bits - 1) - 1
    scaled = torch.ldexp(tiles.double(), -exponent[..., None, None])
    codes = scaled.round().clamp(-limit, limit).to(torch.int16)
    rows, cols = weight.shape
    codes = codes.permute(0, 2, 1, 3).reshape(rows, cols).contiguous()
    step = torch.ldexp(torch.ones_like(exponent, dtype=torch.float32), exponent)
    expanded = exponent.repeat_interleave(BLOCK, 0).repeat_interleave(BLOCK, 1)
    decoded = torch.ldexp(codes.float(), expanded).contiguous()
    if not bool(torch.isfinite(decoded).all()):
        raise ValueError('decoded fixed-point weight exceeds the container range')
    return codes, decoded, step.contiguous()


def export_weights(module):
    """CPU deployment payload; preserve codes AND the exact frozen exponent.

    This payload exports weights only. Activation tables, LUT, RNG contract
    and the remaining model must be exported alongside it by the caller.
    """
    bits = module.config.weight_bits
    gu = torch.cat((module.gate_proj.weight, module.up_proj.weight), 0)
    result = dict(format=FORMAT, total_weight_bits=bits, tile_shape=[64, 64])
    for name, weight, exponent in (
            ('gu', gu, module.gu_weight_exponents),
            ('down', module.down_proj.weight, module.down_weight_exponents)):
        codes, _, _ = quantize(weight, bits, exponent)
        result[name + '_codes'] = codes.to(torch.int8 if bits <= 8 else torch.int16).cpu()
        result[name + '_exponents'] = exponent.detach().cpu().clone()
    return result
