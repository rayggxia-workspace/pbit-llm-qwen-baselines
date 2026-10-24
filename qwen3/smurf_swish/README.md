# Swish stochastic FSM reconstruction

See [the Chinese report](../results/smurf_swish_20261024/REPORT_ZH.md) for measured error and the fixed-W8 interface. This is an independent reconstruction of the mechanism in SMURF, not the author's released code or an exact reproduction of the published Swish number.

```sh
python qwen3/smurf_swish/test_core.py
python qwen3/smurf_swish/run.py
python qwen3/smurf_swish/report.py
```

The run requires its four execution sources/configuration to match the checked-out Git commit. Python 3.8, NumPy 1.24, SciPy 1.10 and Matplotlib 3.7 were used. Runtime state updates and probability comparisons are integers; fitting and diagnostics are offline floating-point calculations. No pretrained model, training set, GPU, RTL or PPA is involved.

`core.py`: stationary coefficient fitting, finite-time moments, literal sequential sampler, signed bit-plane reduction. `run.py`: 51 configurations at 32/64/128 clocks. `config.json`: all frozen assumptions. `test_core.py`: eight functional/statistical checks. `report.py`: manifest verification and plots. Results retain the executing commit and source/configuration SHA-256.
