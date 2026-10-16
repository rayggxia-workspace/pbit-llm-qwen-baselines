"""Cost-only sensitivity through complete screened-Ising decode; no timing claim."""
import copy
import json
from pathlib import Path
from run_screen_ising_v4 import setup
from screen_ising_tlm_v4 import ScreenIsingLocal
from cacti_memory import apply_cost_profile

ROOT=Path(__file__).resolve().parent
def main():
    out=ROOT/'results/cacti_memory_20261016';rows=[]
    for name in ('original_no_flags','cacti_b8','cacti_b16'):
        cfg,evidence,shape=setup('fixed_budget',2048,1)
        if name!='original_no_flags':
            profile=json.loads((out/('tlm_cost_b'+name.split('_b')[1]+'.json')).read_text())
            apply_cost_profile(cfg,profile)
        model=ScreenIsingLocal(cfg,'fixed_sc_exact',evidence,shape)
        d=model.run()
        assert abs(sum(d['energy_J'].values())*1000-d['metrics']['scenario_mJ_per_token'])<1e-8
        assert d['weight_validity_contract']['energy_J']==0
        for key in ('attention_v4','events'):
            if key=='events':d.pop(key,None)
            else:d[key].pop('events',None)
        d['comparison_scope']='memory cost sensitivity ONLY; original service timings/local tile holds retained'
        (out/(name+'_decode.json')).write_text(json.dumps(d,indent=2)+'\n')
        r=dict(name=name,ms_per_token=d['metrics']['mean_TPOT_ms'],
            mJ_per_token=d['metrics']['scenario_mJ_per_token'],area_mm2=d['metrics']['parameterized_area_mm2'],
            weight_access_mJ=d['energy_J']['weight_sram_access']*1000,
            scratch_access_mJ=d['energy_J']['scratch_access']*1000,
            validity_bits=0)
        rows.append(r);print(json.dumps(r),flush=True)
    assert len(set(r['ms_per_token'] for r in rows))==1
    (out/'tlm_comparison.json').write_text(json.dumps(rows,indent=2)+'\n')

if __name__=='__main__':main()
