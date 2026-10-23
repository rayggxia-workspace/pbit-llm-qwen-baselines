from prepare_cpu_gate import ROOT,project,guard,m
import json,hashlib,re,sys
job=json.loads((ROOT/'GPU_FULL_V2_JOB.json').read_text())
remote=project+'/results/'+job['commit'][:12]
local=ROOT/'formal_results'/job['commit'][:12];local.mkdir(parents=True,exist_ok=True)
# Completed JSON files commit atomically. Ignore active logs and .tmp files.
listing=m.ssh(guard+"find "+remote+" -type f -name '*.json' -printf '%P\\n'")
names=listing.splitlines()
assert all(re.fullmatch(r'[A-Za-z0-9_./-]+\.json',n) and '..' not in n.split('/') for n in names)
selected=[n for n in names if not n.startswith('anchor/')]
commands='sha256sum '+' '.join(remote+'/'+n for n in selected)
hashes={line.split(None,1)[1].strip()[len(remote)+1:]:line.split()[0] for line in m.ssh(guard+commands).splitlines()}
assert set(hashes)==set(selected)
downloaded=[]
for name,digest in hashes.items():
    path=local/name
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest()==digest:continue
        raise ValueError('immutable artifact changed remotely: '+name)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.part')
    assert temporary.resolve().is_relative_to(local.resolve())
    m.transfer(temporary,remote+'/'+name,download=True)
    assert hashlib.sha256(temporary.read_bytes()).hexdigest()==digest,name
    temporary.replace(path)
    downloaded.append(name)
receipt=dict(job=job['job'],commit=job['commit'],remote=remote,
             files={n:dict(sha256=d,remote=remote+'/'+n) for n,d in hashes.items()},anchor_window_files_excluded=sum(n.startswith('anchor/') for n in names))
(local/'TRANSFER.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(downloaded=downloaded,known_files=len(hashes),anchor_windows=receipt['anchor_window_files_excluded'])))
if (local/'benchmark.json').exists():
    r=json.loads((local/'benchmark.json').read_text())['result']
    selected=[s for s in r['summaries'] if s['context_tokens']==2048 and s['decode_steps']==128]
    print(json.dumps(dict(gpu=r['gpu_name'],power_unavailable=r['nvml_unavailable_reason'],decode_tokens_per_second={s['mode']:s['decode']['tokens_per_wall_second'] for s in selected}),ensure_ascii=False))
if (local/'ppl_vectorized_bf16.json').exists():
    r=json.loads((local/'ppl_vectorized_bf16.json').read_text())['result']
    print(json.dumps(dict(anchor_scored_tokens=r['scored_tokens'],anchor_ppl=r['perplexity'],paired_quality_complete=False)))
