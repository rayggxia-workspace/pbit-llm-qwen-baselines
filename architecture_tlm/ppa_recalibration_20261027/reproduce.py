"""Recreate all energy rows from archived completed summaries; no TLM rerun."""
import argparse
import json
import statistics
from pathlib import Path
from .rebudget import estimate,read,sha
from ..clock500_resource_20261026 import ppa as old_ppa


def reproduce():
    here=Path(__file__).resolve().parent;root=here.parents[1]
    a=read(here/'ANCHORS.json');old=read(here.parent/'clock500_resource_20261026/PPA_ANCHORS.json')
    cases=[];inputs=[]
    scenarios=[('new_counter_CE',False,False),('counter_real_ICG',True,False),('counter_ICG_plus_digital_gate_candidate',True,True)]
    for folder,index in [('results',0),('results',5),('results',6),('results_early_dma',1),('results_early_dma',2),('results_early_dma',3)]:
        p=here.parent/f'scheduling_v2_20261027/{folder}/case_{index}/RESULT_SUMMARY.json'
        s=read(p);manifest=read(p.with_name('MANIFEST.json'))
        if manifest['status']!='completed' or sha(p)!=manifest['files']['RESULT_SUMMARY.json']['sha256']:
            raise ValueError('not a verified completed summary')
        inputs.append(dict(path=p.relative_to(root).as_posix(),sha256=sha(p),raw_result_sha256=s['raw_result_sha256'],execution=s['execution_commit'],config_sha256=read(p.with_name('EXECUTION.json'))['config_sha256']))
        if folder=='results' and index!=0:continue
        rows={name:estimate(s,a,counter_gate=cg,digital_gate=dg) for name,cg,dg in scenarios}
        oldr=old_ppa.estimate(s,old_ppa.usage_from_tlm(s),old)
        cases.append(dict(case=s['case']['name'],seed=s['config']['seed'],input=inputs[-1],old_counter_price_legacy_subtotal_J=oldr['priced_subtotal_J'],rows=rows,
            sensitivity=[estimate(s,a,counter_gate=True,digital_gate=True,b7_scale=k)['covered_onchip_J'] for k in (1.,a['b7_bitwork_scale'],1.75)]))
    means={}
    for name,_,_ in scenarios:
        rows=[c['rows'][name] for c in cases[1:]]
        means[name]={k:statistics.mean(v[k] for v in rows) for k in ('elapsed_ms','covered_onchip_J','covered_onchip_W','covered_area_mm2','legacy_external_budget_J','legacy_external_budget_W','conditional_budget_with_legacy_external_J','conditional_budget_with_legacy_external_W')}
        means[name]['modules']={r['module']:{k:statistics.mean(next(v for v in q['modules'] if v['module']==r['module']).get(k,0) for q in rows) for k in ('energy_J','area_mm2')} for r in rows[0]['modules']}
    return dict(schema_version=1,scope='existing full36layer Qwen3-4B B1/2K screen_pv synthetic activity repriced; no new timing/PPL/EDA',
        cases=cases,optimized_three_seed_means=means,inputs=inputs,anchors_sha256=sha(here/'ANCHORS.json'),code_sha256=sha(here/'rebudget.py'),sample_stream_unchanged=True,
        full_calibrated_system_energy=None,old_external_proxy='64pJ/byte +50mW background retained ONLY as a budget sensitivity, not an HBM/DRAMPower measurement')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);args=p.parse_args()
    r=reproduce();reference=read(Path(__file__).with_name('RESULTS.json'))
    if r!=reference:raise ValueError('derived results changed from recorded table')
    if args.output:args.output.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'status':'passed','completed_summary_sha':len(r['inputs']),'cases':len(r['cases']),'scenarios':3,'reproduces_RESULTS_json':True}))


if __name__=='__main__':main()
