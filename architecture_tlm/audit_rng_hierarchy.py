"""Read saved comparisons, enforce accounting and preserved global baseline."""
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent
folder=ROOT/'results/rng_hierarchy_v1'
a=json.loads((folder/'global_pool.json').read_text())
b=json.loads((folder/'hierarchical_v1.json').read_text())
ref=json.loads((ROOT/'results/system_decode/base_dual_sc_sz_2048.json').read_text())
assert a['experiment_scope']=='full configured decode'
assert a['variant']=='dual_sc_sz' and a['external_memory_model']['backend']=='simplified Link'
for k,v in ref['metrics'].items():
    x=a['metrics'][k]
    if v is None or isinstance(v,bool):assert v==x
    else:assert math.isclose(v,x,rel_tol=1e-12,abs_tol=1e-12),(k,v,x)
assert a['actions']==b['actions']
assert a['traffic']==b['traffic']
for r in (a,b):
    n=r['config']['decode_tokens']
    assert math.isclose(sum(r['energy_J'].values())*1000/n,r['metrics']['scenario_mJ_per_token'])
    assert math.isclose(sum(r['time_ns'].values()),r['events'][-1]['end_ns'])
    assert all(math.isclose(x['end_ns'],y['start_ns']) for x,y in zip(r['events'],r['events'][1:]))
h=b['rng_hierarchy'];c=b['config']['rng_hierarchy']
assert h['stats']['root_seed_bits']==h['epochs']*c['seed']['root_bits']
assert h['entropy']['conditioned_delivered_bits']==h['stats']['root_seed_bits']
assert h['entropy']['blocks']*c['entropy']['output_bits_per_block']==h['entropy']['conditioned_delivered_bits']+h['entropy']['conditioned_buffer_bits']
assert h['stats']['seed_wire_bits']==sum(e['wire_bits'] for e in h['seed_events'])
assert h['stats']['weight_bernoulli_outputs']==b['actions']['sc_product_trials']
assert h['stats']['local_generated_bits_expected']>=h['stats']['weight_uniform_bits_ideal_expected']
assert h['stats']['shared_generated_bits']>=h['stats']['shared_requested_bits']
assert not {'RNG_sources','RNG_fabric_FIFO'} & b['energy_J'].keys()
assert all(b['energy_J'][k]==v for k,v in h['energy_J'].items())
result=dict(status='PASS',original_global_metrics_unchanged=True,operation_counts_preserved=True,
            memory_and_replay_traffic_preserved=True,seed_and_entropy_accounting=True,
            local_output_accounting=True,no_legacy_rng_double_charge=True,energy_phase_sums=True,
            physical_entropy_validated=False,ppa_measured=False,dramsys_run=False,ppl_run=False)
(folder/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
