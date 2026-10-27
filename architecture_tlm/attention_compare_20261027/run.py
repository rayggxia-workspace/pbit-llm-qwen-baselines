"""Reproducible synthetic smoke/sweep; refuses to overwrite an existing run."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import numpy as np
from .core import bf16, compare
from .schedule import Config, run


def write(path, obj):
    with path.open('w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--lengths', nargs='+', type=int, default=[512, 2048, 8192])
    p.add_argument('--dims', nargs='+', type=int, default=[64, 128])
    p.add_argument('--seeds', nargs='+', type=int, default=[17, 503, 1009])
    p.add_argument('--budget-blocks', type=int, default=8)
    p.add_argument('--samples-ratio', type=int, default=16)
    p.add_argument('--winner-burn', type=int, default=32)
    a = p.parse_args()
    if any(d not in (64, 128) for d in a.dims) or min(a.lengths+a.seeds+[a.samples_ratio]) < 1:
        p.error('positive lengths/seeds/ratio; dimensions 64/128')
    a.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[2]
    sources = list(Path(__file__).parent.glob('*.py')) + [root/'architecture_tlm'/n for n in
        ('parallel_sampler_v5.py', 'winner_hold_tlm_v5.py', 'corrected_rejection_tlm_v5.py')]
    source = {str(f.relative_to(root)): sha(f) for f in sources}
    write(a.output/'SOURCE.json', dict(base_commit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),
                                     files=source, binding='base plus exact listed working-source hashes'))
    config = dict(lengths=a.lengths, dims=a.dims, seeds=a.seeds, samples_ratio=a.samples_ratio,
                  winner_burn=a.winner_burn, budget_blocks=a.budget_blocks, schedule=asdict(Config()),
                  input_kind='synthetic independent normal QKV seed=12345+L+d; BF16 RNE storage',
                  arithmetic='FP64 mathematical oracle; no BF16 MAC rounding',
                  protocol='one decode query/head; warm summaries; not model PPL', model=None, tokenizer=None,
                  train_test_text=None, source_response='ideal independent sigmoid; no drive quantization',
                  command=sys.argv, python=sys.version, numpy=np.__version__, platform=platform.platform())
    write(a.output/'CONFIG.json', config)
    summary = []
    for length in a.lengths:
        for d in a.dims:
            rng = np.random.default_rng(12345+length+d)
            q, k, v = [bf16(x) for x in (rng.normal(size=d), rng.normal(size=(length,d)), rng.normal(size=(length,d)))]
            input_sha = hashlib.sha256(b''.join(x.astype('<f8').tobytes() for x in (q,k,v))).hexdigest()
            for seed in a.seeds:
                rows = compare(q,k,v,max(1,length//a.samples_ratio),seed,budget=a.budget_blocks,burn=a.winner_burn)
                for row in rows:
                    row.update(length=length, d=d, input_sha256=input_sha)
                    if row['status'] == 'completed':
                        row['schedule'] = run(row,d)
                        assert row['schedule']['memory_link_bytes'] == row['K_physical_bytes']+row['V_physical_bytes']
                    name = f'L{length}_d{d}_s{seed}_{row["mode"]}.json'
                    write(a.output/name,row)
                    summary.append({k:v for k,v in row.items() if k in ('mode','status','length','d','seed','QK_MAC','PV_MAC','V_adds','K_physical_bytes','V_physical_bytes','unique_V','relative_error_full','squared_error_screen','squared_error_sampling')})
                    if row['status']=='completed':
                        summary[-1]['conditional_cycles'] = row['schedule']['cycles']
    write(a.output/'SUMMARY.json', summary)
    write(a.output/'MANIFEST.json', dict(status='completed', cases=len(summary),
        files={f.name:dict(sha256=sha(f),bytes=f.stat().st_size) for f in a.output.iterdir() if f.is_file()}))
    print(json.dumps(dict(cases=len(summary), output=str(a.output), failed=sum(r['status']!='completed' for r in summary))))


if __name__ == '__main__':
    main()
