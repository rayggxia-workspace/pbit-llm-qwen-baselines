"""Explicit Llama 2 7B task matrix; real capture identity is mandatory by default."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def tasks(backend):
    cases = ['bf16_dense', 'int8_dense', 'sc_dense', 'sc_pv', 'sc_screen_exact',
             'sc_screen_pv', 'sc_ising', 'sc_screen_ising']
    contexts = [512, 1024, 2048, 4096] if backend == 'link' else [2048, 4096]
    return [dict(case=case, context=context, seed=seed, engines=8, sram_mib=8)
            for context in contexts for case in cases
            for seed in ([0] if case in ('bf16_dense', 'int8_dense', 'sc_dense') else [0, 1, 2])]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend', choices=['link', 'dramsys'], required=True)
    p.add_argument('--index', type=int)
    p.add_argument('--trace-dir', type=Path)
    p.add_argument('--identity-manifest', type=Path)
    p.add_argument('--synthetic', action='store_true')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--bridge', type=Path)
    p.add_argument('--dram-config', type=Path)
    a = p.parse_args()
    rows = tasks(a.backend)
    if a.index is None:
        print(json.dumps(dict(count=len(rows), tasks=rows), indent=2))
        return
    if not 0 <= a.index < len(rows):
        raise ValueError('task index outside declared matrix')
    if a.synthetic:
        if a.trace_dir or a.identity_manifest:
            raise ValueError('synthetic tasks must not declare trace/model identity')
    elif a.trace_dir is None or a.identity_manifest is None:
        raise ValueError('formal tasks require --trace-dir and --identity-manifest')
    row = rows[a.index]
    name = f"c{row['context']}_{row['case']}_e{row['engines']}_s{row['seed']}"
    command = [sys.executable, str(ROOT / 'run.py')]
    for key in ['case', 'context', 'seed', 'engines']:
        command += ['--'+key, str(row[key])]
    command += ['--sram-mib', str(row['sram_mib']), '--output', str(a.output / (name+'.json'))]
    if a.synthetic:
        command += ['--synthetic']
    else:
        trace = a.trace_dir / f"c{row['context']}.trace.json"
        if not trace.is_file():
            raise FileNotFoundError(trace)
        command += ['--trace', str(trace), '--identity-manifest', str(a.identity_manifest)]
    if a.backend == 'dramsys':
        if not a.bridge or not a.dram_config:
            raise ValueError('explicit DRAMSys executable/configuration required')
        command += ['--bridge', str(a.bridge), '--dram-config', str(a.dram_config)]
    subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
