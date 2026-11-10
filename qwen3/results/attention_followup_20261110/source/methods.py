"""Matched digital categorical controls and prioritized logit-sum/8K checks."""
import torch
from experiments.qk_selector_confirm_20261109.methods import Patch as SelectorPatch
from experiments.sparq_ising_20261028 import core, scoring


def case(name, k=None, samples=None, seed=0, method="exact", selector="softmax_sum"):
    return dict(name=name, k=k, samples=samples, seed=seed,
                overlay="k_wh64" if k else None, r=32, selector=selector, method=method)


GROUPS = {
    "2k": [case("bf16")]
        + [case("logit_sum_r32_k128_s64", 128, 64, seed, "winner", "logit_sum") for seed in (1, 2)]
        + [case(f"digital_{kind}_k128_s64", 128, 64, seed, kind)
           for kind in ("categorical", "systematic") for seed in (0, 1, 2)],
    "8k": [case("bf16")]
        + [case(f"softmax_r32_k{k}_" + ("exact" if s is None else "s64"),
                k, s, 0, "exact" if s is None else "winner")
           for k in (128, 256) for s in (None, 64)],
}


def configuration(c):
    if c["k"] is None:
        return None
    return core.Config(r=32, k=c["k"], local=32, samples=c["samples"] or 64,
                       burn=0, mode="exact" if c["method"] == "exact" else
                       "winner" if c["method"] == "winner" else "iid")


def inverse_cdf(logits, uniforms):
    """FP32 software reference. right=True never chooses a zero-width bin."""
    p = logits.float().softmax(-1)
    cdf = p.cumsum(-1)
    # Normalize accumulated rounding as well, keeping bins monotone and last=1.
    cdf = cdf / cdf[:, -1:]
    cdf[:, -1] = 1.0
    # Float32 (S-1+offset)/S can round to 1 even when offset<1.
    uniforms = uniforms.clamp_max(1.0 - 2**-24)
    return torch.searchsorted(cdf.contiguous(), uniforms.contiguous(), right=True)


def draw(logits, samples, method, seed, uniforms=None):
    generator = torch.Generator(device=logits.device).manual_seed(seed)
    if uniforms is None:
        if method == "categorical":
            uniforms = torch.rand((logits.shape[0], samples), device=logits.device,
                                  generator=generator)
        elif method == "systematic":
            # One random offset per row, S equal CDF intervals; exactly S draws.
            offset = torch.rand((logits.shape[0], 1), device=logits.device,
                                generator=generator)
            uniforms = (torch.arange(samples, device=logits.device)[None, :] + offset) / samples
        else:
            raise ValueError(method)
    assert uniforms.shape == (logits.shape[0], samples)
    return inverse_cdf(logits, uniforms)


class Patch(SelectorPatch):
    def __init__(self, c):
        self.full_case = {"method": "winner" if c["samples"] else "exact", **c}
        super().__init__(c)

    def __enter__(self):
        super().__enter__()
        if self.full_case["method"] in ("categorical", "systematic"):
            # Parent installed a sigmoid wrapper for samples!=None; restore it.
            self.kernels.probabilities = self.original_probability
        owner = self
        parent = self.Controller

        class Controller(parent):
            def report(self):
                r = super().report()
                r.update(sampler=owner.full_case["method"],
                         front_end=owner.report()["numeric"],
                         ideal_sigmoid_source=False, hardware_bittrue=False)
                return r

        self.Controller = Controller
        scoring.Controller = Controller
        return self

    def readout(self, logits, value, cfg, seed):
        method = self.full_case["method"]
        if method not in ("categorical", "systematic"):
            return super().readout(logits, value, cfg, seed)
        b, h, g, n = logits.shape
        local = draw(logits.reshape(-1, n), cfg.samples, method, seed)
        activity = torch.zeros((b*h*g, 6), device=logits.device, dtype=torch.int64)
        activity[:, 1] = cfg.samples
        local = local.reshape(b, h, g, cfg.samples)
        bb = torch.arange(b, device=value.device)[:, None, None, None]
        hh = torch.arange(h, device=value.device)[None, :, None, None]
        # The same FP32 V gather/add/normalization as winner-hold core.readout.
        output = value[bb, hh, local].sum(-2) / cfg.samples
        return output, local, activity

    def report(self):
        r = super().report()
        r["case"] = self.full_case
        r["sampler"] = self.full_case["method"]
        if self.full_case["method"] in ("categorical", "systematic"):
            r.update(numeric="FP32 QK -> FP32 softmax/CDF -> fixed-S categorical addresses -> FP32 sum/S -> BF16",
                     threshold_bits=None, lut_entries=None, burn=None,
                     initial_winner_slot=None, rng="SHA-keyed Philox uniform float32; systematic uses one offset per row",
                     hardware_bittrue=False, probability_calls=0, score_entries=0,
                     caveat="algorithmic control, not P8/R8 digital RTL replay; Ising differences include score/probability quantization and chain effects")
        return r
