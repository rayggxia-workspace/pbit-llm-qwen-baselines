"""Bounded synthetic graph-size timing probe; never run the 2K case here."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from architecture_tlm.cycle_v1.attention import AttentionConfig
from architecture_tlm.cycle_v1.gqa import GQAConfig, make_gqa
from architecture_tlm.cycle_v1.run import json_write, source_provenance


def worker(context):
    data=dict(queries=[dict(q=[0.]*64,candidate_ids=list(range(context))) for _ in range(7)],
              k=[[0.]*64 for _ in range(context)],v=[[float(i%17)/17]*64 for i in range(context)])
    start=time.perf_counter()
    k,s=make_gqa(data,AttentionConfig(mode='exact',capacity=2048,score_capacity_bytes=65536),GQAConfig())
    built=time.perf_counter()
    r=k.run('event')
    print(json.dumps(dict(context=context,heads=7,dimension=64,operations=len(r.accepted_ps),
        event_steps=r.steps,build_seconds=built-start,execute_seconds=time.perf_counter()-built,
        total_seconds=time.perf_counter()-start,finish_ps=r.finish_ps,cycle_event_checked=False)))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',type=int)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    if args.worker is not None:
        worker(args.worker)
        return
    args.out.mkdir(parents=True,exist_ok=False)
    records=[]
    for n in (64,128):
        command=[sys.executable,'-X','utf8','-P',str(Path(__file__).resolve()),'--worker',str(n)]
        try:
            result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=30)
        except subprocess.TimeoutExpired:
            records.append(dict(context=n,status='timeout_30_seconds'))
            break
        (args.out/f'n{n}.stdout.txt').write_text(result.stdout,encoding='utf-8',newline='\n')
        (args.out/f'n{n}.stderr.txt').write_text(result.stderr,encoding='utf-8',newline='\n')
        if result.returncode: raise RuntimeError('bounded probe failed')
        records.append(dict(json.loads(result.stdout),status='passed'))
        json_write(args.out/'RESULTS.json',dict(source=source_provenance(),records=records,
                   scope='small synthetic event-only wall-time probe; full 2K never executed'))
    json_write(args.out/'RESULTS.json',dict(source=source_provenance(),records=records,
               scope='small synthetic event-only wall-time probe; full 2K never executed'))
    print(json.dumps(records))


if __name__=='__main__': main()
