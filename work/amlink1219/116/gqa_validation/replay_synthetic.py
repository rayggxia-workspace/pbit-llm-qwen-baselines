"""Small public seven-query regression; never substitutes for model quality."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys

from architecture_tlm.cycle_v1.attention import AttentionConfig
from architecture_tlm.cycle_v1.gqa import GQAConfig
from architecture_tlm.cycle_v1.run import json_write, digest
from architecture_tlm.cycle_v1.run_gqa import synthetic_gqa, run_gqa_case


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    unit=subprocess.run([sys.executable,'-X','utf8','-m','unittest',
        'architecture_tlm.cycle_v1.test_attention','architecture_tlm.cycle_v1.test_gqa','-v'],
        capture_output=True,text=True,encoding='utf-8')
    (args.out/'unit.stdout.txt').write_text(unit.stdout,encoding='utf-8',newline='\n')
    (args.out/'unit.stderr.txt').write_text(unit.stderr,encoding='utf-8',newline='\n')
    if unit.returncode: raise RuntimeError('unit regression failed')
    records=[]
    fixture=synthetic_gqa(7)
    group=GQAConfig(k_slots=1,v_slots=1,operand_slots=1)
    for mode in ('exact','pv','winner','rejection'):
        config=AttentionConfig(mode=mode,samples=4,seed=0)
        result=run_gqa_case(fixture,config,group,args.out/mode,memory_window=1,write_public_report=True)
        records.append(dict(mode=mode,passed=True,latency_ns=result['latency_ns'],
            operations=result['operations'],K_union=len(result['shared']['K_union']),
            V_union=len(result['shared']['V_union']),equivalence=result['mode_equivalence']))
    json_write(args.out/'SUMMARY.json',dict(scope='synthetic seven-query one-KV group; no model quality',
        group_config=asdict(group),memory_window=1,cases=records,unit_tests=20))
    json_write(args.out/'MANIFEST.json',{p.relative_to(args.out).as_posix():digest(p.read_bytes())
        for p in sorted(args.out.rglob('*')) if p.is_file() and p!=args.out/'MANIFEST.json'})
    print(json.dumps(records))


if __name__=='__main__': main()
