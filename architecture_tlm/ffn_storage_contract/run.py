"""Reproduce conditional interface schedules and exact integer diagnostics."""
import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import random
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def sibling(name):
    spec=importlib.util.spec_from_file_location('storage_contract_'+name,HERE/(name+'.py'))
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module

def write(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n',
                    encoding='utf-8',newline='\n')

def digest_json(value):
    result=hashlib.sha256()
    for piece in json.JSONEncoder(sort_keys=True,separators=(',',':'),ensure_ascii=False).iterencode(value):
        result.update(piece.encode('utf-8'))
    return result.hexdigest()

def sample_fixture(inputs, samples, seed):
    rng=random.Random(seed)
    signs=[rng.randrange(2) for _ in range(inputs)]
    bins=[i % 4 for i in range(inputs)]
    frames=[[rng.randrange(2) for _ in range(inputs)] for _ in range(samples)]
    tokens=[digest_json(dict(bits=bits,signs=signs,bins=bins)) for bits in frames]
    return dict(seed=seed,signs=signs,bins=bins,frames=frames,tokens=tokens)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True,
                        help='New directory only: never overwrite an archived run')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    model,counter=sibling('model'),sibling('counter')
    sources=[]
    for path in sorted(HERE.glob('*.py')):
        raw=path.read_bytes()
        sources.append(dict(path=path.relative_to(ROOT).as_posix(),bytes=len(raw),
                            sha256=hashlib.sha256(raw).hexdigest()))
    write(args.output/'EXECUTION.json',dict(
        evidence_level='DESIGN_PROOF',base_commit='46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d',
        execution_binding='exact source manifest; may include uncommitted task implementation',
        python=platform.python_version(),platform=platform.platform(),sources=sources,
        command='python -B -P architecture_tlm/ffn_storage_contract/run.py --output NEW_DIRECTORY',
        scope='local CPU synthetic interface schedules and integer diagnostics; no model/RTL/STA/PPA',
        model_revision=None,dataset=None,LLM_weights=None,scoring_protocol=None,
        not_applicable_reason='synthetic hardware-interface inputs, not a language-model evaluation'))
    cases=[]
    for samples in (16,32,64):
        fixture=sample_fixture(64,samples,20261023)
        write(args.output/f'samples_T{samples}.json',fixture)
        for mode in ('resident','reread'):
            cfg=model.candidate_config(mode,samples=samples)
            result=model.simulate(cfg,sample_tokens=fixture['tokens'])
            trace_hash=digest_json(result['events'])
            case=dict(id=f'{mode}_T{samples}',config=asdict(cfg),summary=result['summary'],
                      trace_sha256=trace_hash,trace_events=len(result['events']),
                      trace_encoding='UTF-8 JSON, sort_keys=true, separators comma/colon, no trailing LF',
                      trace_storage='regenerable; full-size events not stored; small traces included',
                      sample_input=f'samples_T{samples}.json',addresses=result['addresses'])
            write(args.output/(case['id']+'.json'),case)
            cases.append({k:case[k] for k in ('id','summary','trace_sha256','trace_events')})
            print(json.dumps(dict(case=case['id'],end_ps=result['summary']['end_ps'],
                                  read_bytes=result['summary']['sram_read_bytes']),ensure_ascii=False),flush=True)
            del result
    # Small completely materialized transaction/data fixture for downstream replay.
    fixture=sample_fixture(8,4,20261023)
    rng=random.Random(118)
    weights=[[rng.randrange(-128,128) for _ in range(8)] for _ in range(8)]
    args_numeric=(weights,fixture['signs'],fixture['bins'],fixture['frames'])
    a,b,reference=counter.accumulate_a(*args_numeric),counter.accumulate_b(*args_numeric),counter.dot_reference(*args_numeric)
    if not a==b==reference: raise AssertionError('small trace numerical fixture differs')
    write(args.output/'SMALL_INPUT.json',dict(fixture,weights=weights,
                                            expected_integer_bins=reference,weight_layout='tile/output/input W8'))
    for mode in ('resident','reread'):
        cfg=model.candidate_config(mode,inputs=8,outputs=4,tiles=2,samples=4)
        write(args.output/('small_'+mode+'_trace.json'),model.simulate(cfg,sample_tokens=fixture['tokens']))
    rejected=[]
    invalid=[('no_hold_resident',dict(mode='resident',local_weight_hold_bytes=0)),
             ('no_hold_full_wave_direct',dict(mode='direct_no_hold')),
             ('T64_signed20_overflow',dict(mode='reread',samples=64,accumulator_bits=20)),
             ('insufficient_sample_hold',dict(mode='reread',sample_hold_capacity_bits=64))]
    for label,kwargs in invalid:
        try: model.simulate(model.candidate_config(**kwargs))
        except model.ContractError as error: rejected.append(dict(case=label,rejected=True,reason=str(error)))
        else: raise AssertionError('invalid contract accepted: '+label)
    write(args.output/'REJECTED.json',rejected)
    numeric=counter.diagnose()
    write(args.output/'COUNTER_DIAGNOSTIC.json',numeric)
    summary=dict(schema_version=1,evidence_level='DESIGN_PROOF',cases=cases,rejected=rejected,
                 numeric_cases=numeric['case_count'],numeric_bin_outputs=numeric['bin_outputs_checked'],
                 full_system_area=None,full_system_energy=None,new_PPL=None,
                 scope='standalone conditional interface schedules; not whole FFN/decode speedup',
                 bandwidth_counterexample=dict(weight_bytes_per_wave=32768,core_hz=100000000,
                     no_hold_direct_GB_per_second=3276.8,sram_16x128_80MHz_GB_per_second=20.48,
                     fabric_GB_per_second=16.0,
                     condition='all wave weights visible every sample; no persistent local holding'))
    write(args.output/'SUMMARY.json',summary)
    files=[]
    for path in sorted(args.output.iterdir()):
        raw=path.read_bytes()
        files.append(dict(path=path.name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    write(args.output/'MANIFEST.json',dict(files=files,self_excluded=True))
    print(json.dumps({'completed_cases':len(cases),'rejected':len(rejected),'numeric_cases':numeric['case_count']}))

if __name__=='__main__': main()
