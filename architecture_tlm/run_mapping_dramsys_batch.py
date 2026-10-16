"""CPU-only DRAMSys jobs; uses the existing server executable."""
import os
from run_mapping_optimization import OUTPUT, validate

jobs = [(c, p, v, w) for c, p in [(2048, 'NoPowerDown'), (8192, 'NoPowerDown'),
                                  (2048, 'Staggered'), (8192, 'Staggered')]
        for v in ('digital_int8_ffn', 'fixed_sc_exact') for w in ('before', 'after')]
index = int(os.environ['SLURM_ARRAY_TASK_ID'])
context, policy, variant, which = jobs[index]
validate(OUTPUT, OUTPUT/'selection.json',
         os.environ.get('DRAMSYS_BRIDGE', 'build/pbit_dram_bridge'),
         context, 2, policy, variant, which)
