# p-bit Attention literature and proposed experiments

Date: 2026-10-18. Read-only literature/source assessment; no numerical experiment, synthesis or physical validation was run. Parent agent handles Zotero import and project publication.

## Main finding

The present project does not establish a physical p-bit advantage. `architecture_tlm/ising_macro_v4.py` deliberately models only a timed macro contract and produces addresses with ideal IID categorical samples, unless supplied a physical/simulation sample trace. `attention_reference_v3.py` also has a serial random-scan heat-bath reference using one maximum-logit reference state and N-1 mutually inhibited active bits. Its stationary distribution is Softmax; that statement does not establish finite-time mixing, independent samples, asynchronous circuit correctness, or PPA. Each attempted microstep, not each flip, must be charged.

Probability block screening first computes max-of-four subblock mean scores, mean/std, a calibrated sigmoid and Bernoulli decisions. Replacing only the final sigmoid/RNG with native p-bits leaves summary maintenance/access, dot products, normalization, GQA candidate unions and scheduling costs. First test whether screening itself saves energy against dense attention and deterministic selection; then isolate the p-bit implementation benefit at identical selection distributions.

## Primary literature actually inspected

1. **Kyle Lee, Corentin Delacour, Kevin Callahan-Coray, Kyle Jiang, Can Yaras, Samet Oymak, Tathagata Srimani, Kerem Y. Camsari. Stochastic Sparse Attention for Memory-Bound Inference (2026).** arXiv:2605.01910. [Paper](https://arxiv.org/abs/2605.01910), [full text](https://arxiv.org/html/2605.01910v1), [PDF](https://arxiv.org/pdf/2605.01910), [official code](https://github.com/OPUSLab/SANTA).
   - Read abstract, Sections 2, 3, 5 and Tables 1, 5. SANTA samples post-Softmax V rows. Systematic S2ANTA requires one random offset per query/head, and is unbiased, although unlike independent stratification it has no universal variance-reduction guarantee. Reported 32k decode-kernel speedup is about 1.5x; quality-matching budgets are 128 for proportional global allocation and 2048 for fixed tile budgets. Primary savings are V bandwidth, obtainable digitally. Bernoulli QK samples query features, unlike this project's token-block screening. BitNet B=4 K coverage grows from 67.5% per head to 97.9% after GQA union. No physical p-bit circuit validation.

2. **William Whitehead, Zachary Nelson, Kerem Y. Camsari, Luke Theogarajan. CMOS-compatible Ising and Potts annealing using single-photon avalanche diodes (2023).** Nature Electronics 6, 1009-1019. DOI:10.1038/s41928-023-01065-0; preprint arXiv:2211.12607. [Publisher](https://www.nature.com/articles/s41928-023-01065-0), [full preprint](https://arxiv.org/html/2211.12607), [PDF](https://arxiv.org/pdf/2211.12607), [official hardware/data/code](https://github.com/ucsb-biomimetic/ising-potts-with-SPADs-discrete).
   - Read abstract, background and CTMC-neuron architecture sections plus publisher availability statement. Variable-rate Poisson sources and latches create binary or categorical stochastic states. Conditional energies determine event rates; a categorical output can avoid explicitly calculating a normalized probability vector. Experimental platforms used 16 and 144 circuits. This is physical support for a categorical sampling mechanism, not a measured 2048-way Transformer Softmax replacement. The rate-generation circuits, bias loading and state readout still cost hardware.

3. **William Whitehead, Wonsik Oh, Luke Theogarajan. CMOS Single-Photon Avalanche Diode Circuits for Probabilistic Computing (2024).** IEEE Journal on Exploratory Solid-State Computational Devices and Circuits. DOI:10.1109/JXCDC.2024.3452030. [Publisher](https://ieeexplore.ieee.org/document/10659028/), [author repository](https://escholarship.org/uc/item/38h7m5pc), [PDF](https://escholarship.org/content/qt38h7m5pc/qt38h7m5pc.pdf).
   - Read Sections II, V and Table 3 (author PDF pp.3-4, 8-11, 21). Eq.3 gives categorical state occupancy proportional to variable event rates and Softmax when rates are exponential in negative cost. Nine 65nm CMOS variable-rate SPAD circuit designs were fabricated; reported complete binary p-bit reaches 50MHz flips, 81um2 and 1pJ/flip. Binary flip rate is not independent categorical samples/second. Paper highlights Potts rate-matching and variability sensitivity; no measured thousands-category Attention module. These figures are external measured building-block references, not our process or full-macro PPA.

4. **Nihal Sanjay Singh, Keito Kobayashi, Qixuan Cao, Kemal Selcuk, Tianrui Hu, Shaila Niazi, Navid Anjum Aadit, Shun Kanai, Hideo Ohno, Shunsuke Fukami, Kerem Y. Camsari. CMOS plus stochastic nanomagnets enabling heterogeneous computers for probabilistic inference and learning (2024).** Nature Communications 15, 2685. DOI:10.1038/s41467-024-46645-6. [Publisher/full text](https://www.nature.com/articles/s41467-024-46645-6), [PDF](https://www.nature.com/articles/s41467-024-46645-6.pdf).
   - Read experimental architecture, inference/learning results and energy/transistor comparison. Five physical sMTJs supply asynchronous clocks to digital PRNG-based p-bits; experimental sMTJs have millisecond relaxation. Random clocks improve the particular low-cost LFSR inference/learning results toward Xoshiro quality. This differs from slow seed refresh. Integrated 7nm comparisons use synthesis/HSPICE plus literature device estimates, not the tabletop measured full system. Native mixed-signal p-bits can remove LUT/PRNG; that per-cell comparison does not imply an Attention speedup or prove TRNG reseeding improves an already adequate digital generator.

5. **Woojin Lee, Hyunjin Kim, Hyundo Jung, Yohan Choi, Jinwoo Jeon, Chulwoo Kim. Correlation free large-scale probabilistic computing using a true-random chaotic oscillator p-bit (2025).** Scientific Reports 15, 8018. DOI:10.1038/s41598-025-93218-8. [Publisher](https://www.nature.com/articles/s41598-025-93218-8), [PDF](https://www.nature.com/articles/s41598-025-93218-8.pdf), [official data/code](https://github.com/LWJ96-BD/CO_pbit).
   - Read architecture, factorization experiments and methods (PDF pp.1-3, 6-9). A fabricated 180nm CMOS noise/chaos source supports an 8-bit controlled p-bit and FPGA factorization. Experiments use 16 chips with two p-bits each; 10MHz board input transfer limits the run while the device update ceiling is 50MHz. Paper reports 4.26pJ/bit versus a 48-bit LFSR's 17.62pJ under specified conditions; energy comparison excludes the FPGA VCBM. Results motivate application-level correlation tests, not an assertion that every LFSR or digital sampler fails.

## Experiments proposed, not executed

### A. Isolate algorithmic sparsity from the physical randomness implementation

Use identical trace/model, Q/K/V formats, candidate map and V-gather/count engine. Factorial ablations:

- Dense exact stable Softmax + dense PV.
- Same candidates, digital Softmax + IID categorical samples.
- Same candidates, digital Softmax + systematic/stratified sampling (one-offset systematic is essential).
- Same candidates, finite-time inhibited binary-pbit sampler.
- Same candidates, native variable-rate categorical/Potts sampler.
- For each output path: no screen, deterministic top-B screen, score-threshold screen, digital sigmoid+PRNG screen, native sigmoid p-bit screen.

Never attribute V-sparsity savings to the native sampler: compare it first against digital sampling at matched output quality, then report dense-to-sparse total benefit separately. For screening match total selected blocks and captured dense attention mass; forced first/recent blocks and budget-repair logic must match.

### B. Trace and quality matrix

Start with captured Qwen2.5-0.5B and Llama2-7B decode traces, dense FFN unchanged. L={512,2048,8192}; only extend within checkpoint-supported context. Trace all heads over at least 64-128 decode positions; cover layers across depth and include near-uniform, sharply peaked, multimodal and changing-logit cases. Candidate N={64,128,256,512,2048}, samples S={16,32,64,128,256,512}. Calibrate per-layer screening on disjoint data. Report retained attention mass, group-union K/V bytes and burst amplification, vector NMSE/cosine, bias and replicate variance. Promote 2-3 candidates to existing complete WT2 protocol, at least three seeds; local error is not full-model PPL.

### C. Physical sampler characterization and accounting

Native binary-pbit simulation must include measured/declared p(input), gain/offset mismatch, bias quantization, autocorrelation time, feedback delay and readout uncertainty. Compare serial legal updates, legal parallel independent sets and asynchronous delayed feedback; count all invalid states and retries. Native categorical rate model needs rate quantization, dynamic range/saturation, rate mismatch, global logit offset, event collision/deadtime and encoder limits. A common offset leaves mathematical Softmax unchanged but changes physical total event rate and power: sweep it explicitly.

For N<=16 enumerate the transition kernel and verify stationary probabilities. For large N run fixed-bias batches and abrupt bias switches from at least two initial states, measuring finite-horizon bias, TV/KL/JS, invalid fraction, integrated autocorrelation and ESS of category indicators and of the actual V-output projections. A raw categorical index has no meaningful numeric geometry, so avoid ESS of the integer index alone. Estimate rare-state frequency only with sufficient counts or confidence intervals. Burn-in/thinning sweeps must charge consumed updates/time/energy. Across-query warm-start is an experiment; switching logits invalidates old equilibrium automatically.

### D. RNG architecture matrix

R0: high-quality independent digital generator reference. R1: current external TRNG + local PRNG slow refresh. R2: per-cluster refresh using independent source derivation and stream identifiers. R3: local native tunable p-bits for screening only, digital systematic sampler downstream. R4: native categorical module, keep legacy RNG for unrelated FFN. Optional R5: physical asynchronous clocks plus LFSR, only if circuit support exists. Sweep reseed interval {startup only, per 4096,256,16,1 query groups}, generator width {16,32,64}, stream sharing {per head, per KV group, per tile} and selected PRNG families. Fix well-defined stream identity (run/layer/head/token/purpose/counter); shared-seed changes must not accidentally duplicate streams. Use application PPL and selector/categorical bias, cross-head/token correlations and realized ESS; generic randomness-test passes alone do not establish Attention correctness. Reseeding cannot repair all deterministic stream construction errors.

## Break-even quantities

For same sparse output quality, native categorical wins only when its total bias/configuration + settle/burn + correlated sampling + feedback/readout/encoder energy is less than digital max/subtract/EXP/sum/reciprocal + sampler energy. The K/V gather, count accumulation and memory terms cancel only if the generated address distributions and sample budgets actually match. If native ESS fraction is r, roughly S/r physical samples may be needed to match IID estimator variance; systematic digital sampling must be compared by measured output variance, not raw sample count.

Screening wins only if avoided physical K bytes and QK work exceed summary access/maintenance, proxy dots, mean/std/scaling, selector, budget repair and changed burst costs. Native screen must additionally beat digital sigmoid LUT/interpolation + comparator/RNG with the same scores/distribution and quality. There is no prerequisite that the full architecture use one RNG mechanism: a small native selector with digital systematic output may be a better point than a large Ising macro.

Return surfaces for maximum tolerable configure energy per candidate, sample spacing/ESS and feedback delay at each N,S,L; measured or synthesized numbers can later be inserted. External literature coefficient scaling is sensitivity analysis, not process characterization.
