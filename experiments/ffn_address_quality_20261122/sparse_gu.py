"""Counted selected-row W8 loads, followed by exact signed64 accumulation.

The bank lives in GPU global memory in this quality experiment. Only selected
input rows are loaded by the projection kernel. This is NOT LPDDR timing/PPA.
"""
import torch
import triton
import triton.language as tl


@triton.jit
def _project(Bank, Records, Pointer, Coeff, Output,
             N: tl.constexpr, M: tl.constexpr, C: tl.constexpr,
             SHIFT: tl.constexpr, BK: tl.constexpr):
    row = tl.program_id(0)
    og = tl.program_id(1)
    out = og * 64 + tl.arange(0, 64)
    projection = out // M
    within = out % M
    stripe = within // C
    lane = within % C
    start = tl.load(Pointer + row)
    end = tl.load(Pointer + row + 1)
    acc = tl.full((64,), 0, tl.int64)
    for at in range(start, end, BK):
        k = at + tl.arange(0, BK)
        valid = k < end
        record = tl.load(Records + k, mask=valid, other=0).to(tl.int64)
        index = record & 4095
        count = (record >> 12) & 2047
        shift = (record >> 23) & 7
        sign = 1 - 2 * ((record >> 26) & 1)
        coeff = tl.load(Coeff + og * (N // 64) + index // 64, mask=valid, other=0)
        factor = ((count << (SHIFT - shift)) * sign * coeff).to(tl.int64)
        # This is the only weight-read site. Every address is supplied by CSR.
        address = (((stripe[:, None] * N + index[None, :]) * 2
                    + projection[:, None]) * C + lane[:, None])
        w = tl.load(Bank + address, mask=(out[:, None] < 2 * M) & valid[None, :], other=0).to(tl.int64)
        acc += tl.sum(w * factor[None, :], axis=1)
    tl.store(Output + row * (2 * M) + out, acc, mask=out < 2 * M)


def pack_bank(codes, stripe=512):
    if codes.ndim != 2 or codes.shape[0] % 128 or codes.shape[1] % 64:
        raise ValueError('two GU projections, original64 tile shapes required')
    m, n = codes.shape[0] // 2, codes.shape[1]
    if m % stripe or bool((codes.abs() > 127).any()):
        raise ValueError('W8 exact codes and complete output stripes required')
    bank = codes.reshape(2, m // stripe, stripe, n).permute(1, 3, 0, 2).to(torch.int8).contiguous()
    return bank


def project(bank, records, pointer, coefficients, max_shift):
    strips, n, projections, stripe = bank.shape
    m, rows = strips * stripe, pointer.numel() - 1
    if projections != 2 or tuple(coefficients.shape) != (2 * m // 64, n // 64):
        raise ValueError('original weight scale map shape changed')
    out = torch.empty((rows, 2 * m), device=bank.device, dtype=torch.int64)
    _project[(rows, 2 * m // 64)](bank, records, pointer, coefficients.contiguous(), out,
                                N=n, M=m, C=stripe, SHIFT=max_shift, BK=64,
                                num_warps=4)
    return out


def multiply_checked(accumulator, multiplier):
    factor = torch.as_tensor(multiplier, device=accumulator.device, dtype=torch.int64)
    if factor.ndim:
        factor = factor[:, None]
    if bool((factor < 0).any()):
        raise ValueError('negative compensation')
    bound = ((1 << 63) - 1) // factor.clamp_min(1)
    if bool((accumulator.abs() > bound).any()):
        raise OverflowError('restoration needs wider than declared signed64')
    return accumulator * factor
