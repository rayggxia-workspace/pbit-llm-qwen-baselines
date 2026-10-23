# Real Qwen GQA activation capture

Slurm GPU job **2781** completed with `ExitCode=0:0` in 9 seconds on the
primary RTX 5090 server. `FIRST_TERMINAL_SCHEDULER.txt` preserves the first
observed terminal scheduler record, including `TresPerNode=gres:gpu:1`.
The scheduler prints server-local UTC+8 timestamps; the submission receipt
uses UTC. The earlier job 2780 was confirmed CPU-only before submission.

This fixture has seven last-token queries (heads 0 through 6), one shared
KV head (head 0), width 64, context 64, layer 12. All 64 causal key positions
are candidates. Model configuration, weights and WikiText-2 input hashes
were checked against the original capture manifest before model execution.
The model executes in BF16; projection outputs are exported to FP32, then
CPU FP32 RoPE is applied. This is an explicit capture boundary, not bitwise
equivalence to the model's BF16 attention implementation or a full-model
quality evaluation.

The private fixture remains at
`/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/gqa_capture_v1/private_fixture/qwen_layer12_gqa7_context64.json`.
It is 138,958 bytes, SHA-256
`ee5722b38a1acb94daf4d09e49651c9a4610dbc9a9b0ac444b29bb1ef2280080`.
No raw activations or model weights are committed here. Automatic approval
review rejected copying this private activation payload to local storage;
subsequent GQA validation uses the server copy in CPU Slurm allocations and
exports only metadata, hashes, counts, timing and pass/error summaries.

`PUBLIC_RECEIPT.json` was produced by `verify_public_receipt.py`, which
checked the private file's bytes, schema and provenance in place and
omitted all Q/K/V and diagnostic output arrays. The original full manifest
remains on the server; its hash is recorded in the public receipt.

The tokenizer warning in stderr concerns tokenizing the entire corpus
(299,078 tokens) before taking its first 64 tokens. Only that 64-token
prefix entered the model. The other warning describes a future Transformers
logits dtype change; installed versions and actual finite-logits check are
recorded in the public receipt. Neither warning was suppressed.

Execution source commit: `c8a0b20e7e6017462af0573be09a10c6e80714d3`.
`SOURCE_MANIFEST.json` records the exact uploaded capture/script bytes.
The original capture source is `architecture_tlm/cycle_v1/capture_gqa_qwen.py`;
the public in-place receipt helper only validates the small saved fixture
and does not run model inference.
