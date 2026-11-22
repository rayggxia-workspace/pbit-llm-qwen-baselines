# FFN address occupancy (Issue 261)

See [REPORT_ZH.md](REPORT_ZH.md) for the real-vector results and interpretation.

This analysis evaluates a **proposed whole-vector categorical address sampler**,
not the native FFN Bernoulli-event stream, winner-hold sampler, or model PPL.
It reuses a trained Qwen3-4B T64 deployment snapshot and captures full-width
real activations at 36 layers × 16 positions in one WT2 window. Raw tensors
remain in the private authorized server project; Git stores small aggregate
results and provenance only. There is no model or hardware-default change.

Commands from the repository root:

```sh
python experiments/ffn_address_coverage_20261122/test_coverage.py
python experiments/ffn_address_coverage_20261122/coverage.py --capture /private/capture.npz --capture-result /private/RESULT.json --out /new/result-directory
python experiments/ffn_address_coverage_20261122/render_report.py
```

`coverage.py` requires NumPy; `render_report.py` also requires Matplotlib and
uses the committed aggregates. The raw result identity, CSV byte hashes,
source SHA and numerical scope are in `results/RESULTS.json`.
Capture prerequisites and executed paths are explicit in `run_capture.sh`.
Do not silently replace its frozen deployment helpers with another revision.
The run log for failed job6096 is retained; job6099 changes the Slurm launcher
working-directory handling only and reuses the same analysis source bytes.
