"""Fresh observation-only executions, with legacy-field equality checks.

Output paths must be new. Never rewrite or enrich a frozen old JSON in place.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from architecture_tlm.unified_v6.config import load,tiny
from architecture_tlm.unified_v6.model import FullDecode


def write(p,r):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(r,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    sources={}
    for p in ['architecture_tlm/parallel_sampler_v5.py','architecture_tlm/unified_v6/model.py','architecture_tlm/unified_v6/config.py','architecture_tlm/inspector/observe.py']:
        raw=(ROOT/p).read_bytes();assert raw==subprocess.check_output(['git','show',head+':'+p],cwd=ROOT)
        sources[p]=hashlib.sha256(raw).hexdigest()
    runs=[]
    for mode in ('screen_winner','screen_rejection','screen_serial_ising'):
        c,m=tiny();c['attention']['mode']=mode
        r=FullDecode(c,m).run();path=out/('tiny_'+mode+'.json');write(path,r)
        compact={k:r[k] for k in ['config','model','metrics','input_provenance','sampler_audit','stage_busy_ns']}
        compact['config']={'attention':{'mode':mode}}
        runs.append(dict(label='小形状完整观测 '+mode,path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),result=compact))
    c,m=load('qwen');c['attention']['mode']='screen_rejection'
    r=FullDecode(c,m).run()
    old_path=ROOT/'architecture_tlm/unified_v6/results/qwen_20261022_v2/qwen/qwen_L2048_seed0_sc_screen_rejection.json'
    old=json.loads(old_path.read_text(encoding='utf-8'));old.pop('execution_commit');old.pop('config_sha256')
    legacy={k:v for k,v in r.items() if k not in ('stage_busy_ns','sampler_audit')}
    path=out/'qwen_L2048_seed0_sc_screen_rejection_observed.json';write(path,r)
    if old!=legacy:
        changed=[k for k in set(old)|set(legacy) if old.get(k)!=legacy.get(k)]
        write(out/'LEGACY_DIFFERENCES.json',dict(changed_fields=changed,
            before={k:old.get(k) for k in changed},after={k:legacy.get(k) for k in changed}))
        raise AssertionError('legacy fields differ, preserved for diagnosis: '+repr(changed))
    compact={k:r[k] for k in ['config','model','metrics','input_provenance','sampler_audit','stage_busy_ns']}
    compact['config']={'attention':{'mode':'screen_rejection'}}
    runs.insert(0,dict(label='Qwen完整24层2K／seed0／拒绝，旧字段逐项相同',path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),result=compact))
    obs=dict(execution_commit=head,source_sha256=sources,runs=runs,legacy_full_model_fields_identical=True,
        scope='fresh synthetic TLM observations, not new inference/PPL/PT/DRAMSys')
    write(out/'observations.json',obs)
    print(json.dumps(dict(execution_commit=head,full_model_queries=len(r['sampler_audit']),runs=len(runs),legacy_identical=True,output=str(out))))


if __name__=='__main__':main()
