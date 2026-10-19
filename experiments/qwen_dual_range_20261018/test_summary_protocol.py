"""Regression: full corpus and short prefix are separate reference protocols."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
from run_ranges import summarize


temp_root=Path(__file__).resolve().parents[2]/'work/jieruiz/32'
temp_root.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir=temp_root) as tmp:
    project=Path(tmp).resolve()
    output=project/'outputs/check'
    (output/'runs').mkdir(parents=True)
    for name,tokens,ppl in [('bf16_full',299077,11.65),('bf16_prefix',127,14.33)]:
        row=dict(configuration=dict(name=name,kind='baseline'),perplexity=ppl,
                 nll=2.5,scored_tokens=tokens,forward_seconds=1.)
        (output/'runs'/f'{name}.json').write_text(json.dumps(row),encoding='utf-8')
    for seed,ppl in enumerate([15.,16.,17.]):
        name=f'both_dual_all_T256_s{seed}'
        row=dict(configuration=dict(name=name,variant='both',kind='dual',scope='all',cycles=256,seed=seed),
                 perplexity=ppl,nll=2.7,scored_tokens=127,forward_seconds=2.)
        (output/'runs'/f'{name}.json').write_text(json.dumps(row),encoding='utf-8')
    args=argparse.Namespace(project_root=str(project),output=str(output),prefix_tokens=128)
    with contextlib.redirect_stdout(io.StringIO()):summarize(args)
    result=json.loads((output/'summary.json').read_text(encoding='utf-8'))
    assert len(result['references'])==2
    assert {r['tokens'] for r in result['references']}=={299077,127}
    assert len(result['groups'])==1 and result['groups'][0]['ppl_mean']==16.
    assert result['groups'][0]['completed']==3
    assert all(r['kind']!='baseline' for r in result['groups'])
print('PASS: full and prefix BF16 references remain separate; only matched sampled protocols are averaged')
