"""Reproducible read-only summaries of frozen evidence and completed search runs."""
import argparse
import hashlib
import json
import statistics
import subprocess
from pathlib import Path

from .ledger import lower_bounds, resource_ledger

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def record(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def write(path, data):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def archive_audit():
    """Verify all archived v6 manifest payloads without rewriting any byte."""
    base = ROOT/'architecture_tlm/unified_v6/results'
    checked, cases = {}, []
    for directory in ('qwen_20261022_v2', 'llama1_bf16_20261022_v2',
                      'llama1_scpv_20261022_v2', 'llama2_bf16_20261022_v2',
                      'llama2_scpv_20261022_v2', 'integrated_rng_20261022_v3'):
        folder = base/directory
        manifest = folder/'ARTIFACT_MANIFEST.json'
        if not manifest.is_file():
            raise ValueError('required archive missing: '+str(manifest))
        for name, expected in read(manifest).items():
            path = folder/name
            if not path.resolve().is_relative_to(folder.resolve()):
                raise ValueError('archive path escapes root')
            if record(path) != expected:
                raise ValueError('archived payload changed: '+str(path))
            checked[path.relative_to(ROOT).as_posix()] = expected
            if path.suffix == '.json':
                value = read(path)
                if isinstance(value, dict) and {'config', 'metrics', 'SRAM', 'DRAM', 'model'} <= value.keys():
                    cases.append((path, value))
    if len(cases) != 92:
        raise ValueError('expected 52 legacy and 40 integrated cases, got '+str(len(cases)))
    return checked, cases


def compact(path, result):
    cfg = result['config']
    lb = lower_bounds(cfg, result['model'], result)
    meta = result.get('resource_search', {})
    return dict(path=path.relative_to(ROOT).as_posix(), **record(path),
        candidate=meta.get('candidate', {}).get('id', 'archived'), method=meta.get('method'),
        model=cfg['model_record']['name'] if 'name' in cfg.get('model_record', {}) else cfg.get('model_record', {}).get('model'),
        context=cfg['context_tokens'], seed=cfg['seed'], ffn=cfg['ffn']['mode'],
        attention=cfg['attention']['mode'], rng_backend=cfg['random'].get('backend','local_prng_interface'),
        TPOT_ms=result['metrics']['TPOT_ms'],
        SRAM_peak_bytes=result['SRAM']['reserved_peak_bytes'],
        SRAM_configured_bytes=result['SRAM']['configured_bytes'],
        SRAM_physical_bytes=result['SRAM']['physical_bytes'],
        SRAM_macro_area_mm2=result['SRAM']['area_mm2'],
        DRAM_physical_bytes=lb['physical_bytes']['DRAM'],
        SRAM_physical_bytes_transferred=lb['physical_bytes']['SRAM'],
        fixed_traffic_LB_ms=lb['fixed_traffic_lower_bound_ns']/1e6/cfg['decode_tokens'],
        fixed_service_LB_ms=lb['conditional_lower_bound_ms_per_token'],
        T_over_fixed_service_LB=lb['elapsed_over_conditional_lower_bound'],
        bottleneck_resources=sorted(lb['fixed_service_resource_busy_ns'],
            key=lb['fixed_service_resource_busy_ns'].get, reverse=True)[:3],
        routing_sha256=meta.get('routing_sha256'),
        sample_addresses_sha256=meta.get('sample_addresses_sha256'),
        source_output_sha256=meta.get('source_output_sha256'),
        full_physical_area_mm2=None, full_physical_energy_J=None,
        lower_bounds=lb)


def p0(output):
    checked, cases = archive_audit()
    rows, ledger = [], {}
    for path, value in cases:
        rows.append(compact(path, value))
        if (value['config']['context_tokens'] in (2048, 8192)
                and value['config']['seed'] == 0
                and value['model']['hidden_size'] == 896):
            value['_source_path'] = path.relative_to(ROOT).as_posix()
            ledger[value['_source_path']] = resource_ledger(value['config'], value['model'], value)
    output.mkdir(parents=True, exist_ok=False)
    write(output/'ARCHIVE_AUDIT.json', dict(status='PASS', cases=len(rows), files=checked,
        scope='immutable original 52 legacy plus 40 integrated; hashes checked, not rerun'))
    write(output/'BASELINE_BOUNDS.json', dict(rows=rows, units='ms per decode token',
        warning='max across resources, fixed traffic and reservation contracts; not achievable ideal overlap'))
    write(output/'RESOURCE_LEDGER.json', dict(ledgers=ledger, full_area_anchor_A0=None,
        equal_total_area_ranking='blocked_by_missing_physical_components'))
    write(output/'PROVENANCE.json', dict(execution_commit=subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
        source={p.relative_to(ROOT).as_posix():record(p) for p in [Path(__file__), Path(__file__).with_name('ledger.py')]},
        model_inference='not_run; synthetic transaction evidence only',
        tokenizer_dataset='not applicable: no model/text inference',
        new_TLM_runs=0, new_RTL_EDA_DRAMSys_runs=0))
    print(json.dumps(dict(status='PASS', archived_cases=len(rows), archived_files=len(checked))))


def search_summary(inputs, output):
    rows, signatures, grids, manifests = [], {}, {}, {}
    for source in inputs:
        for manifest in sorted(source.rglob('RUN_MANIFEST.json')):
            content=read(manifest)
            manifests[manifest.relative_to(ROOT).as_posix()]=record(manifest)
            for case in content['cases']:
                path=manifest.parent/(case['id']+'.json')
                receipt=read(path.with_name(path.name+'.receipt.json'))
                actual=record(path)
                if receipt != dict(file=path.name,sha256=actual['sha256'],config_sha256=case['config_sha256']):
                    raise ValueError('case receipt mismatch: '+str(path))
                r=read(path); meta=r['resource_search'];cfg=r['config']
                if meta['case_id']!=case['id'] or r['config_sha256']!=case['config_sha256']:
                    raise ValueError('case identity mismatch')
                if r['execution_commit']!=content['execution_commit'] or r['execution_source_sha256']!=content['source_sha256']:
                    raise ValueError('execution source mismatch')
                key=(meta['candidate']['id'],meta['method'],cfg['context_tokens'],cfg['seed'])
                if key in signatures:raise ValueError('duplicate case '+repr(key))
                signatures[key]=meta['routing_sha256']
                row=compact(path,r);row['candidate_definition']=meta['candidate'];row['source_wall_seconds']=r['source_wall_seconds']
                rows.append(row)
                if cfg['seed']==0:grids.setdefault((meta['method'],cfg['context_tokens']),set()).add(meta['candidate']['id'])
    if not rows:raise ValueError('no completed search cases')
    if any(v!=next(iter(grids.values())) for v in grids.values()):
        raise ValueError('candidate grid differs across method/context')
    for row in rows:
        ref=(row['method'],row['context'],row['seed'])
        base=next((r for r in rows if r['candidate']=='baseline_1m' and (r['method'],r['context'],r['seed'])==ref),None)
        row['time_ratio_to_paired_baseline']=row['TPOT_ms']/base['TPOT_ms'] if base else None
        row['same_recorded_routing_as_baseline']=row['routing_sha256']==base['routing_sha256'] if base else None
        row['same_sample_addresses_as_baseline']=row['sample_addresses_sha256']==base['sample_addresses_sha256'] if base else None
        row['same_source_output_as_baseline']=row['source_output_sha256']==base['source_output_sha256'] if base else None
    groups={}
    for row in rows:groups.setdefault((row['candidate'],row['method'],row['context']),[]).append(row)
    means=[]
    for (candidate,method,context), group in sorted(groups.items()):
        values=[r['TPOT_ms'] for r in group]
        means.append(dict(candidate=candidate,method=method,context=context,seeds=sorted(r['seed'] for r in group),
            TPOT_mean_ms=statistics.mean(values),TPOT_min_ms=min(values),TPOT_max_ms=max(values),
            TPOT_stdev_ms=statistics.stdev(values) if len(values)>1 else None,
            SRAM_macro_area_mm2=group[0]['SRAM_macro_area_mm2']))
    best=[]
    for method,context in sorted(grids):
        selected=min((r for r in rows if r['method']==method and r['context']==context and r['seed']==0), key=lambda r:r['TPOT_ms'])
        best.append(dict(method=method,context=context,candidate=selected['candidate'],TPOT_ms=selected['TPOT_ms'],
            rule='minimum seed0 conditional time among the common coarse grid; no PPA/quality acceptance'))
    output.mkdir(parents=True,exist_ok=False)
    write(output/'SUMMARY.json',dict(cases=len(rows),rows=rows,aggregates=means,seed0_fastest=best,
        manifest_files=manifests,equal_area_ranking=None,full_physical_energy_ranking=None,
        warnings=['Source clocks may change realized draws; equal seed is not equal numerical output.',
            'Latency comparisons are conditional synthetic TLM, not model accuracy or STA.',
            'Macro area is a partial storage cost, not total ASIC area.',
            'Every method uses the same coarse hardware/mapping candidates; this is not global optimization.']))
    print(json.dumps(dict(cases=len(rows),fastest=best),ensure_ascii=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['p0','search']);p.add_argument('--inputs',nargs='+',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    if a.mode=='p0':p0(a.output)
    else:search_summary(a.inputs or [],a.output)


if __name__=='__main__':main()
