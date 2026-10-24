# Swish stochastic FSM reconstruction

See [the Chinese report](../results/smurf_swish_20261024/REPORT_ZH.md) for measured error and the fixed-W8 interface. This is an independent reconstruction of the mechanism in SMURF, not the author's released code or an exact reproduction of the published Swish number.

```sh
python qwen3/smurf_swish/test_core.py
python qwen3/smurf_swish/run.py
python qwen3/smurf_swish/report.py
```

The original function-only run requires its four execution sources/configuration to match the checked-out Git commit. Python 3.8, NumPy 1.24, SciPy 1.10 and Matplotlib 3.7 were used. Runtime state updates and probability comparisons are integers; fitting and diagnostics are offline floating-point calculations. That function-only run involved no pretrained model, training set, GPU, RTL or PPA.

`core.py`: stationary coefficient fitting, finite-time moments, literal sequential sampler, signed bit-plane reduction. `run.py`: 51 configurations at 32/64/128 clocks. `config.json`: all frozen assumptions. `test_core.py`: eight functional/statistical checks. `report.py`: manifest verification and plots. Results retain the executing commit and source/configuration SHA-256.

The subsequent [fixed-g Qwen3-4B test](../results/smurf_swish_20261024/model/REPORT_ZH.md) completed 128 sealed suffix scores (118 distinct configurations, three seeds), replacing all 36 FFNs. Every 4/8-state candidate degraded model quality severely, including finite-time mean controls. This is negative evidence, not a successful FSM replacement. Full WT2 and training were not performed.

`model_tables.py` fits finite-horizon coefficients with true g units inside SiLU; `model_kernel.py` executes each random FSM transition and u-AND; `model_core.py` connects fixed W8 projections and integer output accumulation. The [model contract](MODEL_TEST_ZH.md) states fixed-point scales, controls, sample budgets, and remaining front-matrix reference arithmetic. Source snapshots and failed preflight logs remain immutable; see `work/jieruiz/175/MODEL_SUBMISSION.json`.
