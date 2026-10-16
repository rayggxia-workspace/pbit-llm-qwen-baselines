"""Read-only budget analysis of saved TLM runs; no new RTL/PPA claims.

The fixed-weight inputs can be regenerated using:
 python run_rng_hierarchy.py --variant fixed_sc_exact --output
 results/rng_sharing_analysis_20261015/fixed_baseline
No model scheduler or RNG implementation is changed by this script.
"""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'results/rng_sharing_analysis_20261015'


def analyze(path):
    d=json.loads(path.read_text())
    c=d['config'];tokens=c['decode_tokens'];T=c['samples']
    profile=json.loads((ROOT/'configs/evidence_contract.json').read_text())['profiles'][c['sc_profile']]
    with (ROOT/'evidence/grouped_38015538/breakdown.csv').open(encoding='utf-8-sig') as f:
        rows=[r for r in csv.DictReader(f) if int(r['group'])==profile['group'] and
              int(r['batch'])==1 and int(r['case'])==profile['case']]
    prob=next(r for r in rows if r['block']=='probability_registers')
    sign=next(r for r in rows if r['block']=='input_sign_registers')
    frames=d['actions']['sc_tile_frames']
    engine_seconds=frames*(T+1)/c['frequency_hz']/tokens
    wave_seconds=d['bounds']['SC_wave_compute_ms']*1e-3/tokens
    sp=c['scratchpad'];traffic=d['traffic'];e=d['energy_J']
    writes=traffic.get('random_replay_write_bytes',0)/tokens
    reads=traffic.get('random_replay_read_bytes',0)/tokens
    replay_mJ=(writes*sp['write_pJ_per_byte']+reads*sp['read_pJ_per_byte'])*1e-9
    factor=64*c['rng']['input_bits_per_decision']/8
    mJ={k:v/tokens*1000 for k,v in e.items()}
    total=d['metrics']['scenario_mJ_per_token']
    front_W=sum(float(r['total_mW'])*1e-3 for r in rows if r['block'] in
                ('probability_registers','input_sign_registers','probability_comparators_config_selection'))
    local=d.get('rng_hierarchy',{}).get('local_instances',0)
    return dict(source=str(path.relative_to(ROOT)),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        variant=d['variant'],metrics=d['metrics'],mJ_per_token=mJ,
        local_weight_rng_state_bits=local*177,
        threshold_sign_bits_current_estimate=c['sc_engines']*64*14,
        threshold_sign_bits_eight_bit_per_engine=c['sc_engines']*64*9,
        threshold_sign_bits_eight_bit_one_synchronized_frontend=64*9,
        per_token_replay=dict(write_bytes=writes,read_bytes=reads,current_access_mJ=replay_mJ,
            common8_replay_access_mJ=replay_mJ/factor,
            removable_access_mJ_common8=replay_mJ*(1-1/factor),
            removable_access_mJ_no_replay_upper_budget=replay_mJ,
            common8_access_saving_pct_total=100*replay_mJ*(1-1/factor)/total),
        probability_sign_internal_power_upper_budget_mJ=(float(prob['internal_mW'])+
            float(sign['internal_mW']))*engine_seconds,
        frontend_cross_engine_dedup_upper_budget_mJ=front_W*(engine_seconds-wave_seconds)*1000,
        note_budgets='Upper deletion budgets only: retain leakage, charge ICG/loading/wiring and replacement PRNG; '
            'frontend dedup and register gating budgets overlap and MUST NOT be added',
        local_rng_updates_pct_total=100*mJ.get('RNG_local_updates',0)/total,
        input_front_generation_serial_ms=d.get('rng_hierarchy',{}).get('stats',{}).get('shared_busy_ns',0)/tokens/1e6,
        raw_word_replay_write_serial_ms=writes/sp['bandwidth_GBs']/1e6,
        recompute_source_updates_per_token_one_frontend=wave_seconds*c['frequency_hz']*T/(T+1),
        recompute_source_updates_per_token_per_engine=frames*T/tokens,
        existing_scratch_peak_bytes=d['bounds']['scratch_peak_bytes'])


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    results={}
    for name,path in (
        ('dual_hierarchy_v1',ROOT/'results/rng_hierarchy_v1/hierarchical_v1.json'),
        ('fixed_hierarchy_v1',OUT/'fixed_baseline/hierarchical_v1.json')):
        results[name]=analyze(path)
    T=4096
    out=dict(scope='analytical budgets from saved simplified-Link TLM; not a new shared-RNG schedule or measured PPA',
        replay_inventory=dict(old12_independent_bytes=64*T*12//8,
                              independent8_bytes=64*T,
                              common8_bytes=T,
                              lfsr_checkpoint_bytes=4,
                              lfsr_live_plus_checkpoint_bytes=8),
        results=results)
    (OUT/'budget_analysis.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    for name,d in results.items():
        print(name,json.dumps({k:d[k] for k in ('metrics','per_token_replay',
            'probability_sign_internal_power_upper_budget_mJ','local_rng_updates_pct_total',
            'input_front_generation_serial_ms','raw_word_replay_write_serial_ms')},indent=2))


if __name__=='__main__':main()
