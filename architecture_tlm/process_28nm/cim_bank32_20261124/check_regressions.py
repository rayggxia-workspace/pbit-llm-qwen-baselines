"""Cross-case resource checks and deliberately corrupted event traces."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from validate_trace import validate


def load(p):return json.loads(p.read_bytes())


def main():
    p=argparse.ArgumentParser();p.add_argument('--results-root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    names=('small1_repeat','small5','stress5','target_block5','capture32','rng_slow')
    results={};checks={}
    for name in names:
        d=a.results_root/name;r=load(d/'RESULT.json');seal=load(d/'SEAL.json')
        assert seal['status']=='completed'
        for filename,sha in seal['files_sha256'].items():
            assert hashlib.sha256((d/filename).read_bytes()).hexdigest()==sha,(name,filename)
        checks[name]=validate(d/'EVENTS.jsonl',load(d/'EFFECTIVE_ALIGNMENT.json'),r['SRAM'])
        assert r['alignment']['events']['trace_complete']
        results[name]=r
    assert results['small1_repeat']['commands']==2
    assert checks['small1_repeat']['events']['input_cache_hit']>0
    assert checks['small5']['outputs_executed_across_multiple_cores']>0
    assert max(results['stress5']['alignment']['results']['peak_used_per_core'])==2
    assert results['stress5']['alignment']['events']['wait_ns']['result_slot']>0
    records=[json.loads(x) for x in (a.results_root/'target_block5/EVENTS.jsonl').read_text().splitlines()]
    ready=[x for x in records if x['event']=='weight_ready']
    blocked=min(x['ns'] for x in ready if x['core']==0)
    assert any(x['core']!=0 and x['ns']<blocked for x in ready)
    assert results['target_block5']['alignment']['events']['events']['dma_target_wait']>0
    assert all(x['memory']['counts']['peak_response_bytes']<=16384 for x in results.values())
    assert results['capture32']['time_ns']>results['small5']['time_ns']
    assert all(x['effective_frame_cycles']==x['frame_cycles']+3 for x in results['capture32']['common_FFN_stages'])
    assert results['rng_slow']['alignment']['events']['wait_ns']['rng_assignment']>0
    assert results['rng_slow']['time_ns']>results['small5']['time_ns']
    # The independent consumer must reject meaningful hazards, not just accept its own producer.
    original=[json.loads(x) for x in (a.results_root/'small5/EVENTS.jsonl').read_text().splitlines()]
    contract=load(a.results_root/'small5/EFFECTIVE_ALIGNMENT.json')
    mutations={
        'release_before_capture':lambda rows:next(x for x in rows if x['event']=='result_capture').update(event='uncommitted_capture'),
        'missing_state_beat':lambda rows:next(x for x in rows if x['event']=='result_beat_accept').update(beat=3),
        'wrong_K':lambda rows:next(x for x in rows if x['event']=='command_accept').update(k=1),
        'weight_overwrite':lambda rows:next(x for x in rows if x['event']=='cim_release').update(event='unreleased_CIM'),
        'truncated':lambda rows:rows.pop(),
    }
    rejected=[]
    with tempfile.TemporaryDirectory(prefix='trace-negative-',dir=str(a.results_root)) as temp:
        for name,mutate in mutations.items():
            rows=json.loads(json.dumps(original));mutate(rows);path=Path(temp)/(name+'.jsonl')
            path.write_bytes(('\n'.join(json.dumps(x) for x in rows)+'\n').encode())
            try:validate(path,contract)
            except (AssertionError,KeyError):rejected.append(name)
    assert set(rejected)==set(mutations)
    value=dict(status='PASS',sealed_cases=checks,negative_traces_rejected=rejected,
        unrelated_core_progress_during_target_stall=True,shared_DMA_payload_within_16KiB=True,
        capture_bandwidth_and_RNG_latency_affect_time=True,
        RTL_cycle_or_numeric_equivalence_claimed=False)
    a.out.write_bytes((json.dumps(value,indent=2)+'\n').encode())
    print(json.dumps(dict(status='PASS',cases=len(names),negative_hazards=len(rejected))))


if __name__=='__main__':main()
