"""Small conditional p-bit gates, with exact marginal training and sampled use.

The 4 -> 8 -> 1 gate contains 49 trainable scalar parameters. Hidden bits
are conditionally independent given x; this is not a coupled Ising model.
Enumerating 256 hidden states is an exact software training calculation,
not a claim about a physical device or about a mean-field approximation.
"""
from __future__ import annotations

import math
from typing import Any

import torch
from torch import nn
from torch.nn import functional as F


def hidden_states(width: int = 8, *, device=None, dtype=torch.float32):
    indices = torch.arange(1 << width, device=device, dtype=torch.int64)
    shifts = torch.arange(width, device=device, dtype=torch.int64)
    return ((indices[:, None] >> shifts) & 1).to(dtype)


class LinearPBit(nn.Module):
    """4-input Bernoulli gate; five parameters including its bias."""

    kind = "linear_pbit"

    def __init__(self):
        super().__init__()
        self.weight = nn.Parameter(torch.empty(4))
        self.bias = nn.Parameter(torch.zeros(()))
        nn.init.normal_(self.weight, std=0.1)

    def forward(self, x):
        return torch.sigmoid(x @ self.weight + self.bias)

    def sample(self, x, *, draws=1, generator=None):
        probability = self(x)
        return torch.bernoulli(
            probability.expand((draws,) + probability.shape), generator=generator
        )

    def output_bias(self):
        return self.bias


class PBitNetwork(nn.Module):
    """Exact marginal q(x) and genuine two-stage Bernoulli samples."""

    kind = "pbit_4_8_1"

    def __init__(self):
        super().__init__()
        self.hidden_weight = nn.Parameter(torch.empty(4, 8))
        self.hidden_bias = nn.Parameter(torch.zeros(8))
        self.output_weight = nn.Parameter(torch.empty(8))
        self.bias = nn.Parameter(torch.zeros(()))
        nn.init.normal_(self.hidden_weight, std=1 / math.sqrt(4))
        nn.init.normal_(self.output_weight, std=1 / math.sqrt(8))
        self.register_buffer("states", hidden_states(), persistent=False)

    def hidden_distribution(self, x):
        logits = x @ self.hidden_weight + self.hidden_bias
        return torch.exp(
            F.logsigmoid(logits) @ self.states.T
            + F.logsigmoid(-logits) @ (1 - self.states).T
        )

    def forward(self, x):
        conditional_output = torch.sigmoid(self.states @ self.output_weight + self.bias)
        return self.hidden_distribution(x) @ conditional_output

    def sample(self, x, *, draws=1, generator=None):
        hidden_probability = torch.sigmoid(x @ self.hidden_weight + self.hidden_bias)
        h = torch.bernoulli(
            hidden_probability.expand((draws,) + hidden_probability.shape),
            generator=generator,
        )
        output_probability = torch.sigmoid(h @ self.output_weight + self.bias)
        return torch.bernoulli(output_probability, generator=generator)

    def output_bias(self):
        return self.bias


def effective_probability(q, valid, forced):
    """Invalid blocks are absent, mandatory blocks are selected with probability 1."""
    if torch.any(forced & ~valid):
        raise ValueError("forced mask includes invalid blocks")
    return torch.where(forced, torch.ones_like(q), q) * valid.to(q.dtype)


def budget_penalty(q_effective, target_blocks):
    """Square of the batch mean budget error, NOT mean squared query errors."""
    if q_effective.ndim != 2:
        raise ValueError("budget loss requires complete [query, block] groups")
    return (q_effective.sum(dim=1).mean() - target_blocks).square()


def export_model(model, mean, std) -> dict[str, Any]:
    return {
        "format_version": 1,
        "kind": model.kind,
        "parameter_count": sum(p.numel() for p in model.parameters()),
        "parameters": {name: p.detach().cpu().tolist() for name, p in model.named_parameters()},
        "normalization": {"mean": list(mean), "std": list(std), "fit_split": "train_free_blocks"},
        "forward_contract": (
            "exact hidden marginal for training; real hidden/output Bernoulli draws at use"
            if isinstance(model, PBitNetwork) else "sigmoid probability; real output Bernoulli draws at use"
        ),
    }


def import_model(payload, *, device="cpu"):
    classes = {PBitNetwork.kind: PBitNetwork, LinearPBit.kind: LinearPBit}
    model = classes[payload["kind"]]().to(device)
    with torch.no_grad():
        for name, parameter in model.named_parameters():
            value = torch.as_tensor(payload["parameters"][name], dtype=parameter.dtype, device=device)
            if value.shape != parameter.shape:
                raise ValueError(f"bad exported shape for {name}")
            parameter.copy_(value)
    return model
