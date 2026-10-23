"""Faithful discrete p-bit attention forwards; explicit training estimators.

Independent ideal Bernoulli responses are a behavioral model, not physical
randomness or a clock model. No softmax is evaluated in the default forward.
"""
import math
from dataclasses import dataclass
from typing import Dict, List, Optional

import torch
from torch import Tensor, nn
from torch.nn import functional as F


def score_function_loss(loss: Tensor, score_log_prob: Tensor,
                        baseline=0.0) -> Tensor:
    """Unreduced REINFORCE objective, retaining the loss's direct derivatives.

    Shapes must match: for a sequence-level loss, sum log probabilities over
    that sequence's heads/queries/layers BEFORE calling this function. Baselines
    may depend on inputs/past draws, but not the current sampled trajectory.
    """
    if loss.shape != score_log_prob.shape:
        raise ValueError('loss and joint score_log_prob must have identical shapes')
    b = torch.as_tensor(baseline, dtype=loss.dtype, device=loss.device)
    if b.ndim and b.shape != loss.shape:
        raise ValueError('baseline must be scalar or have the loss shape')
    term = (loss.detach() - b.detach()) * score_log_prob
    return loss + (term - term.detach())


@dataclass
class SampleResult:
    output: Tensor
    indices: Tensor
    score_log_prob: Tensor  # Parameter-dependent Bernoulli terms, not full path density.
    stats: Dict[str, Tensor]
    trace: List[Dict[str, Tensor]]
    gradient_mode: str

    def objective(self, loss: Tensor, baseline=0.0) -> Tensor:
        if self.gradient_mode != 'score_function':
            raise ValueError('objective() requires score_function mode')
        return score_function_loss(loss, self.score_log_prob, baseline)


class SamplingCapError(RuntimeError):
    def __init__(self, stats):
        super().__init__('proposal cap reached; no fallback or successful partial result')
        self.stats = stats


class _Draws:
    """Fresh independent draws; generator state advances, including in eval()."""
    def __init__(self, generator, probability_bits):
        self.generator, self.probability_bits = generator, probability_bits

    def bits(self, drive, mask):
        p = torch.sigmoid(drive.detach()[mask])
        if self.probability_bits is None:
            bit = torch.rand(p.shape, dtype=p.dtype, device=p.device,
                             generator=self.generator) < p
        else:
            levels = 1 << self.probability_bits
            threshold = torch.round(p * levels).to(torch.long).clamp(0, levels)
            word = torch.randint(levels, p.shape, device=p.device, generator=self.generator)
            bit = word < threshold  # threshold==levels is true probability one.
        out = torch.zeros_like(mask)
        out[mask] = bit
        return out

    def rank(self, counts):
        """Exact uniform integer in [0,count); reject excess power-of-two codes."""
        widths = torch.ceil(torch.log2(counts.to(torch.float64))).to(torch.long)
        result = torch.zeros_like(counts)
        used = torch.zeros_like(counts)
        pending = widths > 0
        while bool(pending.any()):
            w = widths[pending]
            raw = torch.randint(1 << int(w.max()), w.shape, device=w.device,
                                generator=self.generator)
            raw = raw & ((1 << w) - 1)
            loc = pending.nonzero(as_tuple=True)[0]
            used[loc] += w
            good = raw < counts[loc]
            result[loc[good]] = raw[good]
            pending[loc[good]] = False
        return result, used

    def coin(self, shift):
        """Reference accepted iff m independent fair bits are all zero."""
        yes = torch.ones_like(shift, dtype=torch.bool)
        active = shift > 0
        if bool(active.any()):
            m = shift[active]
            raw = torch.randint(1 << int(m.max()), m.shape, device=m.device,
                                generator=self.generator)
            yes[active] = (raw & ((1 << m) - 1)) == 0
        return yes


def _positive_int(value, name, zero=False):
    if type(value) is not int or value < (0 if zero else 1):
        raise ValueError(name + ' must be an integer in range')


class _Attention(nn.Module):
    def __init__(self, samples=64, gradient_mode='score_function',
                 drive_step=None, probability_bits=None):
        super().__init__()
        _positive_int(samples, 'samples')
        if gradient_mode not in ('score_function', 'softmax_surrogate', 'none'):
            raise ValueError('unknown gradient_mode')
        if drive_step is not None and (not math.isfinite(drive_step) or drive_step <= 0):
            raise ValueError('positive finite drive_step required')
        if probability_bits is not None:
            _positive_int(probability_bits, 'probability_bits')
            if probability_bits > 16:
                raise ValueError('probability_bits supported range is 1..16')
        if gradient_mode == 'score_function' and (drive_step is not None or probability_bits is not None):
            raise ValueError('rounded modes have no exact continuous score gradient; use none or explicit surrogate')
        self.samples, self.gradient_mode = samples, gradient_mode
        self.drive_step, self.probability_bits = drive_step, probability_bits

    def _prepare(self, scores, values, mask, generator):
        if not scores.is_floating_point() or not values.is_floating_point():
            raise ValueError('floating scores and values required')
        if scores.ndim < 1 or not scores.numel() or values.ndim < 2:
            raise ValueError('scores [...,N], values [...,N,D] required')
        if values.shape[-2] != scores.shape[-1] or values.shape[-1] < 1:
            raise ValueError('K/V length mismatch or empty V width')
        if values.device != scores.device:
            raise ValueError('scores and values must share a device')
        if torch.isnan(scores).any() or torch.isposinf(scores).any():
            raise ValueError('scores must be finite or -inf padding')
        valid = torch.isfinite(scores)
        if mask is not None:
            if mask.dtype != torch.bool or mask.device != scores.device:
                raise ValueError('mask must be bool on scores device, True=valid')
            valid = valid & torch.broadcast_to(mask, scores.shape)
        if not bool(valid.any(-1).all()):
            raise ValueError('each row must have at least one valid key')
        v = torch.broadcast_to(values, scores.shape[:-1] + values.shape[-2:])
        # Invalid V padding cannot introduce NaNs into optional dense surrogate.
        v = torch.where(valid.unsqueeze(-1), v, torch.zeros_like(v))
        if not bool(torch.isfinite(v).all()):
            raise ValueError('valid values must be finite')
        dtype = torch.float64 if scores.dtype == torch.float64 else torch.float32
        z = scores.to(dtype).masked_fill(~valid, -torch.inf)
        ref = z.argmax(-1, keepdim=True)
        d = (z - z.gather(-1, ref)).masked_fill(~valid, 0)
        if not bool(torch.isfinite(d).all()):
            raise ValueError('score differences overflow work dtype')
        prefix = scores.shape[:-1]
        return (z.reshape(-1, scores.shape[-1]), d.reshape(-1, scores.shape[-1]),
                valid.reshape(-1, scores.shape[-1]), ref.reshape(-1),
                v.reshape(-1, values.shape[-2], values.shape[-1]), prefix,
                _Draws(generator, self.probability_bits))

    def _drive(self, d):
        if self.drive_step is None:
            return d
        return d.sign() * (d.abs() / self.drive_step).round().clamp(max=255) * self.drive_step

    def _score(self, drive, bits, mask):
        if self.gradient_mode != 'score_function':
            return torch.zeros(drive.shape[0], dtype=drive.dtype, device=drive.device)
        lp = torch.where(bits, F.logsigmoid(drive), F.logsigmoid(-drive))
        return lp.masked_fill(~mask, 0).sum(-1)

    def _finish(self, z, v, prefix, idx, lp, stats, trace):
        gathered = v.gather(1, idx.unsqueeze(-1).expand(-1, -1, v.shape[-1]))
        dtype = torch.float64 if v.dtype == torch.float64 else torch.float32
        out = gathered.to(dtype).mean(1)
        if self.gradient_mode == 'softmax_surrogate':
            proxy = torch.bmm(z.softmax(-1).unsqueeze(1), v.detach().to(z.dtype)).squeeze(1)
            out = out + (proxy - proxy.detach()).to(out.dtype)
        return SampleResult(out.to(v.dtype).reshape(prefix + (v.shape[-1],)),
                            idx.reshape(prefix + (self.samples,)), lp.reshape(prefix),
                            {k: x.detach().reshape(prefix) for k, x in stats.items()},
                            trace, self.gradient_mode)


class WinnerHoldAttention(_Attention):
    """All sites propose; hold if current site fires or none fires, else uniform pick.

    Starting at argmax, run burn_in + samples*spacing updates. Retain each spacing-th
    update after burn. Holds count as samples. Finite chains are NOT IID softmax.
    """
    def __init__(self, samples=64, burn_in=0, spacing=1, shift=0.0, **kwargs):
        super().__init__(samples, **kwargs)
        _positive_int(burn_in, 'burn_in', zero=True)
        _positive_int(spacing, 'spacing')
        if not math.isfinite(shift) or shift < 0:
            raise ValueError('nonnegative finite shift required')
        self.burn_in, self.spacing, self.shift = burn_in, spacing, shift

    def forward(self, scores, values, mask=None, *, generator=None, record_trace=False):
        z, d, valid, state, v, prefix, rng = self._prepare(scores, values, mask, generator)
        drive = self._drive(d - self.shift)
        rows = torch.arange(z.shape[0], device=z.device)
        lp = torch.zeros(z.shape[0], dtype=z.dtype, device=z.device)
        updates = self.burn_in + self.samples * self.spacing
        stats = {k: torch.zeros_like(state) for k in ('updates', 'pbit_draws', 'holds', 'switches', 'rank_fair_bits')}
        indices, trace = [], []
        for t in range(updates):
            bits = rng.bits(drive, valid)
            count = bits.sum(-1)
            before = state.clone()
            change = (~bits[rows, state]) & (count > 0)
            chosen = state.clone()
            if bool(change.any()):
                rr = rows[change]
                rank, cost = rng.rank(count[change])
                hit = bits[change] & (bits[change].long().cumsum(-1) == rank[:, None] + 1)
                chosen[rr] = hit.long().argmax(-1)
                stats['rank_fair_bits'][rr] += cost
            state = chosen
            lp = lp + self._score(drive, bits, valid)
            stats['updates'] += 1
            stats['pbit_draws'] += valid.sum(-1)
            stats['holds'] += ~change
            stats['switches'] += change
            if record_trace:
                trace.append(dict(bits=bits.detach().clone(), before=before, state=state.clone()))
            if t >= self.burn_in and (t - self.burn_in + 1) % self.spacing == 0:
                indices.append(state.clone())
        return self._finish(z, v, prefix, torch.stack(indices, -1), lp, stats, trace)


class CorrectedRejectionAttention(_Attention):
    """Zero encodes argmax. Single one accepts; zero accepts with 2**(-m).

    Multi-one rejection increments m; rejected zero decrements m. Accepted states
    leave m unchanged. Ideal acceptance law is softmax, without digital softmax.
    """
    def __init__(self, samples=64, initial_shift=0, max_shift=24,
                 max_trials_per_sample=64, adaptive=True, **kwargs):
        super().__init__(samples, **kwargs)
        _positive_int(initial_shift, 'initial_shift', zero=True)
        _positive_int(max_shift, 'max_shift', zero=True)
        _positive_int(max_trials_per_sample, 'max_trials_per_sample')
        if not 0 <= initial_shift <= max_shift <= 24:
            raise ValueError('require 0 <= initial_shift <= max_shift <= 24')
        self.initial_shift, self.max_shift = initial_shift, max_shift
        self.max_trials_per_sample, self.adaptive = max_trials_per_sample, bool(adaptive)

    def forward(self, scores, values, mask=None, *, generator=None, record_trace=False):
        z, d, valid, ref, v, prefix, rng = self._prepare(scores, values, mask, generator)
        rows = torch.arange(z.shape[0], device=z.device)
        proposed = valid.clone()
        proposed[rows, ref] = False
        shift = torch.full_like(ref, self.initial_shift)
        stats = {k: torch.zeros_like(ref) for k in ('proposals', 'pbit_draws', 'collisions',
                 'zero_rejections', 'reference_accepts', 'correction_fair_bits', 'accepted')}
        lp = torch.zeros(z.shape[0], dtype=z.dtype, device=z.device)
        out = torch.full((z.shape[0], self.samples), -1, dtype=torch.long, device=z.device)
        trace = []
        for _ in range(self.samples * self.max_trials_per_sample):
            rr = rows[stats['accepted'] < self.samples]
            if not rr.numel():
                break
            m = shift[rr].clone()
            drive = self._drive(d[rr] - m[:, None] * math.log(2.0))
            bits = rng.bits(drive, proposed[rr])
            counts = bits.sum(-1)
            empty, single = counts == 0, counts == 1
            ref_accept = torch.zeros_like(empty)
            if bool(empty.any()):
                ref_accept[empty] = rng.coin(m[empty])
                stats['correction_fair_bits'][rr[empty]] += m[empty]
            take = single | ref_accept
            address = torch.where(ref_accept, ref[rr], bits.long().argmax(-1))
            dst = rr[take]
            out[dst, stats['accepted'][dst]] = address[take]
            stats['accepted'][dst] += 1
            stats['proposals'][rr] += 1
            stats['pbit_draws'][rr] += proposed[rr].sum(-1)
            stats['collisions'][rr] += counts > 1
            stats['zero_rejections'][rr] += empty & ~ref_accept
            stats['reference_accepts'][rr] += ref_accept
            lp = lp.index_add(0, rr, self._score(drive, bits, proposed[rr]))
            if self.adaptive:
                shift[rr[counts > 1]] = (m[counts > 1] + 1).clamp(max=self.max_shift)
                shift[rr[empty & ~ref_accept]] = (m[empty & ~ref_accept] - 1).clamp(min=0)
            if record_trace:
                trace.append(dict(rows=rr.clone(), bits=bits.clone(), shift_before=m,
                                  shift_after=shift[rr].clone(), accepted=take.clone(),
                                  reference_accepted=ref_accept.clone(), address=address.clone()))
        stats['final_shift'] = shift
        if bool((stats['accepted'] < self.samples).any()):
            raise SamplingCapError({k: x.detach().reshape(prefix) for k, x in stats.items()})
        return self._finish(z, v, prefix, out, lp, stats, trace)
