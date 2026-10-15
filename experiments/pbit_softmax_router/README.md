# Ising SoftMax and BoltzFormer-inspired Qwen routing

All original Qwen2.5-0.5B weights and FFNs remain fixed. Only all 24 decode
attention modules change; prefill is exact. Same WikiText-2 suffix targets as
the previous 2k/8k attention experiments (4096/2048 scored tokens).

## Ising scope

For L logits there are L-1 bits and degree L-2. The 0/1 energy is
`E=-sum_i (z_i-z_ref)b_i + lambda*sum_(i<j)b_i*b_j`.
All-zero encodes the reference category; single-active states encode the rest.
The reference is the largest logit, making all relative fields nonpositive.
Within valid states the exact conditional distribution is softmax.

The LLM experiment uses the **hard-penalty limit**, with exact continuous-time
heat-bath dynamics, not a finite-conductance hardware model. From all-zero,
birth rates are sigmoid(z_i-z_ref); from active i, death rate is 1-birth_i.
We generate the alternating exponential holding times in bulk and observe
states at fixed clock intervals. This preserves residence weighting and
sample correlations. Counting transition events instead would be biased.
Time is in unit per-bit update clocks, NOT microseconds or GPU runtime.
Burn-in is at target temperature (beta=1); there is no optimization annealing.

diagnostics.py separately checks finite penalties by exact enumeration and
literal asynchronous Gibbs updates, and compares compressed hard-limit
transients with a matrix-exponential solution of the generator. No claim that
the paper's finite circuitry, delays, noise or energy consumption is reproduced.

## Router scope

This is an **untrained language-model adaptation**, not a reproduction of the
trained image BoltzFormer predictor. Each 64-token block has cached key mean
and coordinate variance. The cache is built once from the prefix and updated
incrementally. full-rank and 16-coordinate low-rank proxies are compared.

- block_mean: query dot mean key + log block size.
- block_moment: Gaussian moment approximation, mean score + half variance
  (diagonal covariance) + log block size.
- block_paper: sigmoid confidence with tau=1/(layer+1), inspired by paper.
- oracle: true full-QK block probability mass; diagnostic, cannot save QK.
- oracle_topk: deterministic full-QK relevance control, not a mathematical
  upper bound on end-to-end language-model quality.

Bernoulli inclusion is `1-(1-p_block)^K`. The first and last two blocks are
always retained and included in reported sparsity. Selected blocks get exact
softmax attention. No importance correction: this changes the target function.

The software computes dense QK and masked dense PV for correctness and teacher
diagnostics. Logical selected fractions are NOT measured sparse-kernel speedups.
FFN hashes, source hashes, text hashes, sample positions and wall times are saved.
