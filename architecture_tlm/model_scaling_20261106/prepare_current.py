"""Freeze current host/module glue without copying weights or native libraries."""
from pathlib import Path
import argparse,hashlib,json,shutil

HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepare(project,out):
    out.mkdir(parents=True,exist_ok=False);index={}
    def copy(src,rel):
        p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,p);index[rel]=dict(source=str(src),sha256=sha(p))
    current=project/'tmp/tlm-unified250-issue225-20261107'
    directories=('sram1216_20261106','module_refresh_20261107','ffn6_100mhz_20261107',
        'qk_supply_100mhz_20261107','attention_candidate_20261107','sampling_latency_20261106')
    for name in directories:
        source=current/'architecture_tlm'/name
        if not source.exists():source=project/'architecture_tlm'/name
        for p in source.rglob('*'):
            if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in p.parts and not any('review_' in x for x in p.parts):
                copy(p,'host/architecture_tlm/'+name+'/'+p.relative_to(source).as_posix())
    for name in ('attention_digital_small_20261107','ffn_digital_contract_20261107','attention_resource_compaction_20261107'):
        for p in (project/'architecture_tlm'/name).rglob('*'):
            if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in p.parts:
                copy(p,'modules/architecture_tlm/'+name+'/'+p.relative_to(project/'architecture_tlm'/name).as_posix())
    pin=json.loads((current/'architecture_tlm/module_refresh_20261107/ATTENTION_SOURCE.json').read_bytes())
    front=project/'tmp/attention-compare-issue198-20261027/architecture_tlm/attention_supply_front_20261107'
    for n,h in pin['execution_sources'].items():
        assert sha(front/n)==h;copy(front/n,'owner_front/'+n)
    source=project/'tmp/cross-model245-20261106/work/rayggxia/245/execute_20261107/local_runtime/inputs'
    for n in ('SHAPE_FIXTURES.json','SAMPLES.json'):copy(source/n,'inputs/'+n)
    copy(project/'project_archives/attention_integrated250_198_20261107/inputs/representative.json','inputs/representative.json')
    for n in ('CURRENT_WORKLOAD_PLAN.json','execution.py','current_mainline.py','current_run.py','current_pricing.py'):
        copy(HERE/n,'glue/'+n)
    targets=json.loads((HERE.parent/'equal_area_100_250_20261107/TARGETS.json').read_bytes())
    core=json.loads((current/'architecture_tlm/module_refresh_20261107/FFN_PROFILE.json').read_bytes())['versions']['250MHz']['core']
    t=targets['versions']['250'];t['target_area55_mm2']=t['target_update_formula']['fixed_without3FFNcores_mm2']+3*core['area55_mm2']
    t['target_status']='accepted_v3_calibrated_components_plus_declared_proxies'
    t['target_update_formula']['accepted_new_core_area_mm2']=core['area55_mm2']
    p=out/'architecture_tlm/equal_area_100_250_20261107/TARGETS.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(targets,indent=2)+'\n').encode())
    index[p.relative_to(out).as_posix()]=dict(generated='current55 area;no28nm substitution',sha256=sha(p))
    for path,name in [('architecture_tlm/attention_digital_small_20261107/CALIBRATION.json','DIGITAL_ATTENTION_PRICES.json'),
        ('digital_circuit_simulation_registry/records/attention-sampler-gate-hold-198-20261105.json','SAMPLER_SS100.json'),
        ('project_archives/ffn_sram_batch204_20261106/runtime/PRICES.json','LEGACY_RESIDENCY_PRICES.json')]:copy(project/path,'inputs/'+name)
    manifest=dict(status='snapshot_prepared_not_submitted',sources=index,private_owner_sources=True,
        public_scope='only glue,configs,numerical summary and hashes;no owner source/fixtures/PDK',
        parent_runtime='project_archives/ffn_sram_batch204_20261106/runtime',
        parent_deps='project_archives/sram1216_225_20261106/dependencies')
    (out/'SNAPSHOT_MANIFEST.json').write_bytes((json.dumps(manifest,indent=2)+'\n').encode())
    print(json.dumps(dict(files=len(index),bytes=sum((out/n).stat().st_size for n in index),snapshot=str(out))))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--workspace',type=Path,required=True);a.add_argument('--out',type=Path,required=True);p=a.parse_args();prepare(p.workspace,p.out)
