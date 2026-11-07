"""Allocate real legal FMA16 slices under total covered area, once per resource.

Missing current module interfaces produce a pending plan, never zero-cost
hardware or a fabricated simulated time. Host SRAM topology remains explicit.
"""
import argparse,json,math
from pathlib import Path

REQUIRED_ROLES={'FFN_nonmatrix','attention_control','reduction','QK_staging','output_format'}
CASES=(('BF16_dense','BF16','dense'),('W8_dense','W8','dense'),('W8_screen','W8','screen'))

def unique_area(components):
    seen={};roles=set()
    for c in components:
        area=c['area55_mm2']
        if not math.isfinite(area) or area<0:raise ValueError('invalid area')
        if c['resource_id'] in seen and seen[c['resource_id']]!=area:
            raise ValueError('shared resource has conflicting prices')
        seen[c['resource_id']]=area;roles.update(c.get('roles',[]))
    return math.fsum(seen.values()),roles

def allocate(target,components,pool,legal_slices):
    fixed,_=unique_area(components)
    if pool['resource_id'] in {c['resource_id'] for c in components}:
        raise ValueError('pool already charged as fixed resource')
    unit=pool['area55_mm2_per_slice']
    if unit<=0 or not math.isfinite(unit):raise ValueError('invalid pool price')
    valid=[n for n in legal_slices if isinstance(n,int) and n>0 and fixed+n*unit<=target+1e-10]
    if not valid:return dict(status='infeasible',fixed_area55_mm2=fixed,target_area55_mm2=target)
    n=max(valid);total=fixed+n*unit
    return dict(status='allocated_not_executed',slices=n,lanes=n*pool['lanes_per_slice'],
        fixed_area55_mm2=fixed,pool_area55_mm2=n*unit,total_area55_mm2=total,
        target_area55_mm2=target,unused_area55_mm2=target-total,
        area_gap_percent=100*(total/target-1),latency_ms=None,energy_mJ=None)

def plan(targets,bundles=None):
    out=[]
    for clock,t in targets['versions'].items():
        common=t['digital_host_fixed_components'];host,_=unique_area(common)
        for name,ffn,att in CASES:
            row=dict(case=name,clock_MHz=int(clock),FFN=ffn,attention=att,
                target_area55_mm2=t['target_area55_mm2'],SRAM_KiB=t['SRAM_KiB'],
                target_status=t['target_status'],same_external_memory=True,
                raw_weight_traffic_ratio=None,latency_ms=None,energy_mJ=None)
            b=(bundles or {}).get(clock,{}).get(name)
            if not b or b.get('status')!='ready':
                row.update(status='waiting_current_digital_module_contracts',
                    known_host_area55_mm2=host,
                    pool_only_upper_bound_slices=math.floor((t['target_area55_mm2']-host)/t['pool_unit_reference']['area55_mm2_per_slice']),
                    upper_bound_is_not_a_valid_baseline=True,
                    missing=['FFN current format/mapping','Attention shared pool/small SRAM',
                             'complete fixed component ledger and legal pool sizes'])
            else:
                fixed=b['fixed_components'];_,roles=unique_area(fixed)
                if not REQUIRED_ROLES<=roles:raise ValueError('incomplete component boundary '+name)
                if b['clock_MHz']!=int(clock) or b['SRAM_KiB']!=t['SRAM_KiB']:
                    raise ValueError('clock/SRAM mismatch')
                if not b.get('entry_points') or not b.get('timing_contract'):
                    raise ValueError('execution adapter/timing contract missing')
                row.update(allocate(t['target_area55_mm2'],common+fixed,b['pool'],b['legal_pool_slices']))
                row['entry_points']=b['entry_points'];row['timing_contract']=b['timing_contract']
            out.append(row)
    return dict(status='planned_not_simulated',cases=out,
        equal_area_policy='closest legal area not exceeding the complete target; report residual',
        physical_area='covered component sum; raw65 area factor0.81 already applied once',
        no_new_PPA=True,no_new_model_quality=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--modules',type=Path);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();targets=json.loads(Path(__file__).with_name('TARGETS.json').read_bytes())
    bundles=json.loads(a.modules.read_bytes()) if a.modules else None
    a.out.write_bytes((json.dumps(plan(targets,bundles),indent=2)+'\n').encode())
