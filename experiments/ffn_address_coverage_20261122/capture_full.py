"""Read-only full-width activation capture for address-occupancy analysis.

Reuses immutable T64 deployment/scorer helpers, without patching their files.
The saved tensors stay in the authorized private server project.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(16 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--helpers', type=Path, required=True)
    p.add_argument('--inputs', type=Path, required=True)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--legacy', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    started = time.time()
    sys.path.insert(0, str(a.helpers))
    import numpy as np
    import torch
    from run_wt2 import prepare, load_model
    from adapter import SamplingOverride

    inputs, tokens, ledger, protocol = prepare(a.inputs, a.runtime, a.output)
    model, context, modules, identity = load_model(inputs)
    import seven_forward as sf
    case = dict(id='strat64', T_x=64, T_and=64,
                input_law='stratified_T', and_law='joint_grid',
                grid_g_sig_u=[4, 4, 4])
    patch = SamplingOverride(case)
    patch.configure(modules)
    positions = [31, 159, 287, 415, 543, 671, 799, 927,
                 1023, 1151, 1279, 1407, 1535, 1663, 1919, 2015]
    pos = torch.tensor(positions, device='cuda')
    ids = torch.as_tensor(tokens[:2048].astype(np.int64), device='cuda')[None]

    def forward():
        context.seed = 101
        context.begin(0, 0, domain='ffn-wt2-deployment')
        return model(ids, use_cache=False).logits[0].detach().cpu()

    with patch, torch.no_grad():
        reference = forward()
    values = {}
    seen = []
    legacy_checks = []
    legacy = np.load(a.legacy, allow_pickle=False)
    legacy_positions = {0: (31, 0), 17: (1023, 4864), 35: (2015, 9664)}
    original = sf.upstream.hard_forward

    def take(t):
        return t.detach().float().cpu().numpy().copy()

    def hooked(x, wg, wu, wd, module, key):
        result = original(x, wg, wu, wd, module, key)
        layer = int(module.layer)
        cache = result[1]
        assert x.shape == (1, 2048, 2560)
        assert cache[1].shape[-1] == 9728
        # All weights here are actual decoded W8 + frozen PoT scales, not codes.
        assert torch.equal(wg, module.frozen_gu_decoded[:9728])
        assert torch.equal(wu, module.frozen_gu_decoded[9728:])
        assert torch.equal(wd, module.frozen_down_decoded)
        tag = 'L%02d_' % layer
        xx = x.reshape(-1, 2560).index_select(0, pos).float()
        enc = sf._encode_static_validated(xx, module.x_scales)
        code = torch.where(enc['full_one'], 256, enc['q']).long()
        x_mean = enc['sign'] * enc['scale'] * code / 256
        gq = cache[3].reshape(-1, 9728).index_select(0, pos)
        uq = cache[4].reshape(-1, 9728).index_select(0, pos)
        sigmoid = cache[8].reshape(-1, 9728).index_select(0, pos)
        values[tag + 'x_raw'] = take(xx)
        values[tag + 'x_p8mean'] = take(x_mean)
        values[tag + 'z_p8mean'] = take(gq * uq * sigmoid)
        values[tag + 'z_sample'] = take(cache[9].reshape(-1, 9728).index_select(0, pos))
        values[tag + 'norm_gu'] = (wg.double().square().sum(0)
                                  + wu.double().square().sum(0)).sqrt().cpu().numpy()
        values[tag + 'norm_wd'] = wd.double().square().sum(0).sqrt().cpu().numpy()
        if layer in legacy_positions:
            token, first = legacy_positions[layer]
            for suffix, tensor in [('x_raw', x.reshape(-1, 2560)[token]),
                                   ('g_raw', cache[1].reshape(-1, 9728)[token, first:first+64]),
                                   ('u_raw', cache[2].reshape(-1, 9728)[token, first:first+64])]:
                ok = np.array_equal(take(tensor), legacy['L%d_%s' % (layer, suffix)])
                legacy_checks.append(dict(layer=layer, field=suffix, equal=bool(ok)))
                assert ok, ('legacy capture mismatch', layer, suffix)
        seen.append(layer)
        print('CAPTURE_LAYER', layer, flush=True)
        return result

    sf.upstream.hard_forward = hooked
    try:
        with patch, torch.no_grad():
            observed = forward()
    finally:
        sf.upstream.hard_forward = original
    assert torch.equal(reference, observed), 'Read-only hook changed logits'
    assert sorted(seen) == list(range(36))
    np.savez_compressed(a.output / 'capture.npz', **values)
    result = dict(status='completed', kind='real_full_width_activation_capture',
                  no_op_all_window_logits_bitwise_equal=True,
                  legacy_checks=legacy_checks, layers=seen, positions=positions,
                  vectors_per_signal=36*len(positions), window_start=0,
                  window_length=2048, identity=identity, protocol=protocol, case=case,
                  seed=101, capture_sha256=sha(a.output/'capture.npz'),
                  capture_bytes=(a.output/'capture.npz').stat().st_size,
                  inputs_sha256=sha(a.inputs), script_sha256=sha(__file__),
                  helper_sha256={n: sha(a.helpers/n) for n in
                                 ['run_wt2.py', 'adapter.py', 'sampling.py']},
                  seconds=time.time()-started,
                  scope='one WT2 window; real T64 checkpoint; no new PPL/quality claim; '
                        'z_p8mean is the product of encoded amplitudes and P8 sigmoid, '
                        'not a separate exact-FP32-SiLU path')
    (a.output/'RESULT.json').write_bytes((json.dumps(result, indent=2)+'\n').encode())
    print(json.dumps({k: result[k] for k in ['status', 'capture_bytes', 'seconds']}), flush=True)


if __name__ == '__main__':
    main()
