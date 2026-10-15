# Block-scale extension of p-bit QK

This is our extension of the paper's per-query-head signed Bernoulli encoder,
not an exact reproduction of Section 5. The archived single-scale experiment
at `experiments/pbit_qk` remains unchanged.

Split each 64-dimensional post-RoPE query head into contiguous blocks of 64,
16, or 8 features. Each block gets its own `a = max(abs(q_block))`. Encode
`p = abs(q)/a`, retain signs, and reconstruct `q_hat = sign(q)*a*count/B`.
The 64-feature case is exactly the preceding per-head baseline. There are
1, 4, or 8 continuous scales per head respectively. Zero blocks remain zero.

All 24 decode attention layers use the encoder. Original FFNs, continuous K,
dense PV, projections, RoPE, and exact prefill are retained. No training.
The experiment uses stratified sampling; counts are compressed as
`floor(B*p) + Bernoulli(frac(B*p))` with the exact literal-strata count law.

## Fair comparison and hardware limits

- 2k/8k contexts use the same WT2 suffix positions as earlier attention runs,
  scoring 4096/2048 tokens with 128 cached teacher-forced steps per span.
- Block sizes 64/16/8, B=4/8/16/32, three inference seeds, and four dense
  baselines give 76 evaluations. These are exploratory subset PPLs, not
  independent held-out validation after selecting the design.
- Tests check analytic moments and zero blocks, bitwise equality to the
  preceding 64-feature encoder, and model cache/prefill/seed behavior.
- `summarize.py` also requires every block64 result to exactly match its
  archived per-seed PPL, and checks source, FFN, corpus, and target identities.
- A hardware implementation needs separate signed sums, continuous scale
  restoration, and reduction for each block. More scales are not free.
- Smaller scales tend to increase active bits and logical key-feature access.
  Every nonzero block's largest component is encoded exactly. At the limiting
  block size 1, all magnitudes move into continuous scales: this reduces to
  the original continuous multiplication and is not a useful p-bit speedup.
- The present implementation reconstructs floating queries and uses dense
  matmuls, with additional exact-score diagnostics. No sparse speed or energy
  claim follows from these arithmetic experiments.

Full results: [Chinese report](../../results/pbit_qk_block_20261006/RESULTS_ZH.md).

## Reproduction

Use CUDA PyTorch and Transformers 4.45.2; place the original model and test text
at `models/Qwen2.5-0.5B` and `data/wikitext-2/wiki.test.raw`. From the repo root:

```bash
python experiments/pbit_qk_block/test_sampling.py
python experiments/pbit_qk_block/test_integration.py
python experiments/pbit_qk_block/evaluate.py --mode stratified --block-size 8 --samples 8 --context 2048 --examples 32 --decode 128 --batch 16 --seed 0 --output outputs/pbit_qk_block_reproduction/ctx2048_g8_b8_seed0.json
```

For 8k use `--context 8192 --examples 16 --batch 4`. Repeat seeds 0/1/2.
Use a new output path each time. B is query sampling rounds, not value samples.
The original 76-run launcher uses idle GPUs and refuses an existing protocol.
`summarize.py` needs matplotlib and the prior QK results, but does not need CUDA.
