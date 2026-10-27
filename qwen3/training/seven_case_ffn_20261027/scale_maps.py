"""Offline scale assignments for the seven-case one-factor experiment.

Input is the already verified common parent model, before any case training.
The returned int8 exponent maps are frozen deployment metadata, not optimizer
parameters. Fullscale powers are held constant in the W6/W10 ablations.
"""
import torch
from qwen3.weight_quantization.pot64 import choose_exponents, validate_exponents

POLICIES = ('tile64', 'all_ffn', 'projection_role')


@torch.no_grad()
def make_scale_maps(model, weight_bits=8, sharing='tile64'):
    if weight_bits not in (6, 8, 10):
        raise ValueError('this experiment fixes total signed widths to W6/W8/W10')
    if sharing not in POLICIES:
        raise ValueError('unknown frozen weight scale sharing policy')
    layers = model.model.layers
    if not layers:
        raise ValueError('no decoder FFN layers')
    base = {}
    for i, layer in enumerate(layers):
        base[str(i)] = {}
        for role in ('gate_proj', 'up_proj', 'down_proj'):
            projection = getattr(layer.mlp, role)
            if projection.bias is not None:
                raise ValueError('this reference contract is bias-free')
            # W8 provides the common power-of-two range before changing bits.
            base[str(i)][role] = choose_exponents(projection.weight, bits=8)
    if sharing == 'all_ffn':
        exponent = max(int(table.max()) for roles in base.values() for table in roles.values())
        base = {i: {role: torch.full_like(table, exponent)
                    for role, table in roles.items()} for i, roles in base.items()}
    elif sharing == 'projection_role':
        role_exponents = {role: max(int(roles[role].max()) for roles in base.values())
                          for role in ('gate_proj', 'up_proj', 'down_proj')}
        base = {i: {role: torch.full_like(table, role_exponents[role])
                    for role, table in roles.items()} for i, roles in base.items()}
    result = {}
    for i, layer in enumerate(layers):
        roles = base[str(i)]
        # w = Q * 2**k. Keep E=k+(b-1) fixed when b changes.
        delta = 8 - weight_bits
        gate = roles['gate_proj'].int() + delta
        up = roles['up_proj'].int() + delta
        down = roles['down_proj'].int() + delta
        gu_weight = torch.cat((layer.mlp.gate_proj.weight, layer.mlp.up_proj.weight), 0)
        result[str(i)] = {
            'gu': validate_exponents(gu_weight, torch.cat((gate, up), 0)).tolist(),
            'down': validate_exponents(layer.mlp.down_proj.weight, down).tolist()}
    return result


def attach_to_common_calibration(calibration, scale_maps, weight_bits):
    """Keep common x/g/u tables; only attach the case's frozen weight map."""
    import copy
    from qwen3.weight_quantization.pot64 import FORMAT
    if calibration.get('format') != 'fixed-four-and-training-pot64-v2':
        raise ValueError('rebuild common activation calibration with the PoT64 reference first')
    if set(scale_maps) != set(calibration['layers']):
        raise ValueError('scale map layer coverage mismatch')
    result = copy.deepcopy(calibration)
    result['weight_format'] = FORMAT
    result['weight_bits'] = weight_bits
    for i in result['layers']:
        result['layers'][i]['weight_exponents'] = copy.deepcopy(scale_maps[i])
    return result
