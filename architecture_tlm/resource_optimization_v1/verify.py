"""Independent conservation and paired-control gates for completed search cases."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from .search import METHODS, digest, generate_candidates
from .summarize import ROOT, archive_audit, read, record, write


def verify(inputs, expected):
    checked, old = archive_audit()
    cases, sources, count = {}, {}, 0
    for folder in inputs:
        for manifest in folder.rglob('RUN_MANIFEST.json'):
            plan=read(manifest);execution=read(manifest.parent/'EXECUTION.json')
            assert plan['execution_commit']==execution['commit']
            assert plan['source_sha256']==execution['source_sha256']==digest(execution['files'])
            for name,info in execution['files'].items():
                assert record(ROOT/name)==info, 'execution source bytes changed: '+name
            sources[execution['source_sha256']]=execution['files']
            for spec in plan['cases']:
                path=manifest.parent/(spec['id']+'.json');r=read(path);receipt=read(path.with_name(path.name+'.receipt.json'))
                assert receipt['sha256']==record(path)['sha256']
                assert receipt['file']==path.name
                assert digest(r['config'])==spec['config_sha256']==r['config_sha256']==receipt['config_sha256']
                meta=r['resource_search'];cfg=r['config'];model=r['model']
                assert meta['case_id']==spec['id'] and meta['candidate']==spec['candidate']
                assert meta['method']==spec['method'] and model==plan['shape']
                assert meta['candidate_sha256']==digest(meta['candidate'])
                assert meta['input_shape_sha256']==digest(model)
                assert r['execution_source_sha256']==execution['source_sha256'] and r['execution_commit']==execution['commit']
                assert (cfg['ffn']['mode'],cfg['attention']['mode'])==METHODS[spec['method']]
                assert cfg['context_tokens']==spec['context'] and cfg['seed']==spec['seed']
                assert cfg['decode_tokens']==1 and cfg['core_hz']==100000000 and cfg['sram']['clock_hz']==80000000
                assert (cfg['ffn']['bins'],cfg['ffn']['samples'],cfg['ffn']['strata'])==(4,32,32)
                assert cfg['random']['backend']=='integrated_service'
                assert r['metrics']['full_physical_energy_J'] is None and r['metrics']['full_physical_area_mm2'] is None
                assert r['metrics']['quality_reference_ppl'] is None
                assert math.isclose(sum(r['phase_ns'].values()),r['metrics']['elapsed_ns'],abs_tol=1e-5)
                assert max(r['resource_busy_ns'].values())<=r['metrics']['elapsed_ns']+1e-5
                mem=r['SRAM'];regions=sorted(mem['layout'].values(),key=lambda x:x['address'])
                assert all(x['address']+x['bytes']<=y['address'] for x,y in zip(regions,regions[1:]))
                assert max(x['address']+x['bytes'] for x in regions)==mem['reserved_peak_bytes']<=mem['configured_bytes']==mem['physical_bytes']
                assert cfg['sram']['fabric_GBs']<=cfg['sram']['banks']*cfg['sram']['word_bytes']*cfg['sram']['clock_hz']/1e9
                assert r['random_interface']['random_stream_SRAM_bytes']==0
                assert meta['source_output_sha256']==r['random_interface']['frame_output_sha256']
                assert meta['source_activity_sha256']==digest(r['random_interface'])
                assert meta['attention_activity_sha256']==digest(r['attention_activity'])
                assert meta['physical_traffic_sha256']==digest(dict(DRAM=r['DRAM']['traffic'],SRAM=r['SRAM']['traffic']))
                if spec['method']=='sc_screen_pv':
                    assert meta['routing_rows']==meta['sampled_rows']==model['num_hidden_layers']*model['num_attention_heads']
                    assert len(r['row_receipts'])==meta['routing_rows']
                    wanted={(0,layer,head) for layer in range(model['num_hidden_layers']) for head in range(model['num_attention_heads'])}
                    assert {(x['token'],x['layer'],x['head']) for x in r['row_receipts']}==wanted
                    samples=math.ceil(cfg['context_tokens']/16)
                    assert all(x['outputs']==samples and x['candidates']==512 for x in r['row_receipts'])
                    assert r['attention_activity']['V_sample_events']==len(wanted)*samples
                    assert r['attention_activity']['QK_logical_positions']==len(wanted)*512
                key=(spec['candidate']['id'],spec['method'],spec['context'],spec['seed'])
                assert key not in cases;cases[key]=r;count+=1
    assert count==expected,(count,expected)
    coarse={(c['id'],method,context,0) for c in generate_candidates() for method in METHODS for context in (2048,8192)}
    confirmation={(c,method,context,seed) for c in ('baseline_1m','mapped_1m','balanced_2m','wide_4m')
                  for method in METHODS for context in (2048,8192) for seed in (1,2)}
    assert expected in (128,192)
    assert set(cases)==(coarse if expected==128 else coarse|confirmation), 'predeclared case grid differs'
    assert len(sources)==1,'numerical/scheduler source files differ between phases'
    capacity_checks=0
    for (candidate,method,context,seed),r in cases.items():
        if candidate.startswith('capacity_'):
            b=cases[('baseline_1m',method,context,seed)]
            assert r['metrics']['TPOT_ms']==b['metrics']['TPOT_ms']
            assert r['DRAM']['traffic']==b['DRAM']['traffic'] and r['SRAM']['traffic']==b['SRAM']['traffic']
            assert r['SRAM']['layout']==b['SRAM']['layout'] and r['SRAM']['reserved_peak_bytes']==b['SRAM']['reserved_peak_bytes']
            ratio=r['SRAM']['physical_bytes']/b['SRAM']['physical_bytes']
            assert ratio in (2,4,8) and math.isclose(r['SRAM']['area_mm2'],b['SRAM']['area_mm2']*ratio)
            for key in ('routing_sha256','sample_addresses_sha256','source_output_sha256'):
                assert r['resource_search'][key]==b['resource_search'][key]
            capacity_checks+=1
    baseline_checks={}
    anchors={('bf16_exact',2048):234.36001,('bf16_exact',8192):260.45281,
             ('w8_exact',2048):163.56481,('w8_exact',8192):189.65761,
             ('sc_exact',2048):201.72241,('sc_screen_pv',2048):198.00316,
             ('sc_screen_pv',8192):202.83611}
    for (method,context),value in anchors.items():
        measured=cases[('baseline_1m',method,context,0)]['metrics']['TPOT_ms']
        assert measured==value
        baseline_checks[method+'_'+str(context)]=measured
    return dict(status='PASS',completed_cases=count,immutable_archive_cases=len(old),
        immutable_archive_payloads=len(checked),capacity_only_paired_checks=capacity_checks,
        fresh_baseline_anchors=baseline_checks,identical_execution_source_sets=len(sources),
        scope='manifest/config/source identity, full route receipts, phase/resource/storage conservation, negative controls; not PPL/STA/PPA')


def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,nargs='+',required=True);p.add_argument('--expected',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=verify(a.inputs,a.expected);write(a.output,result);print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
