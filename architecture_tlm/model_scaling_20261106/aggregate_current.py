"""Verify all36 full results before emitting24 configuration rows and ratios."""
from pathlib import Path
from collections import defaultdict
import argparse,csv,hashlib,json,statistics

def aggregate(root,out,repair_root=None):
    plan=json.loads((root/'PLAN.json').read_bytes());expected={(p['model'],p['clock'],p['scheme'],p['seed']) for p in plan}
    assert len(expected)==36
    groups=defaultdict(list);index=[];seen=set();components=[];phases=[];allocations=[]
    original_sha=hashlib.sha256((root/'SNAPSHOT_MANIFEST.json').read_bytes()).hexdigest()
    repaired_keys=set();repair_sha=None;folders=list((root/'results/full').glob('*'))
    if repair_root:
        original=json.loads((root/'SNAPSHOT_MANIFEST.json').read_bytes());repair=json.loads((repair_root/'SNAPSHOT_MANIFEST.json').read_bytes())
        assert repair['repair_parent_manifest_sha256']==original_sha
        changes={n for n in set(original['sources'])|set(repair['sources']) if original['sources'].get(n,{}).get('sha256')!=repair['sources'].get(n,{}).get('sha256')}
        assert changes=={'glue/current_mainline.py','PILOTS.json'},changes
        assert repair['repair_scope']=='SC100_large_model_vector_decoder_binding_only'
        repaired_keys={k for k in expected if k[0] in ('llama32_3b','deepseek_7b') and k[1]==100 and k[2]=='SC_ising'}
        assert len(repaired_keys)==6
        repair_sha=hashlib.sha256((repair_root/'SNAPSHOT_MANIFEST.json').read_bytes()).hexdigest()
        folders+=list((repair_root/'results/full').glob('*'))
    for folder in sorted(folders):
        seal=folder/'SEAL.json'
        if not seal.exists():continue
        manifest=json.loads(seal.read_bytes())
        for n,h in manifest['files_sha256'].items():
            assert hashlib.sha256((folder/n).read_bytes()).hexdigest()==h,(folder,n)
        r=json.loads((folder/'RESULT.json').read_bytes());b=json.loads((folder/'BUDGET.json').read_bytes())
        v=json.loads((folder/'VALIDATION.json').read_bytes());key=(r['model'],r['clock_MHz'],r['scheme'],r['seed'])
        assert key in expected and key not in seen;seen.add(key)
        assert r['status']=='completed' and v['status']=='PASS' and r['includes_head']
        assert r['layers']==r['shape']['layers'] and r['backend']=='native'
        assert b['energy_sum_closed'] and b['no_28nm_mixing']
        corrected=key in repaired_keys
        assert folder.parent==(repair_root/'results/full' if corrected else root/'results/full')
        assert r['snapshot_manifest_sha256']==(repair_sha if corrected else original_sha)
        groups[key[:3]].append((r,b))
        index.append(dict(case=key,path=str(folder),files_sha256=manifest['files_sha256'],source_manifest_sha256=r['snapshot_manifest_sha256']))
        identity=dict(model=key[0],clock_MHz=key[1],scheme=key[2],seed=key[3])
        for component in b['components']:components.append(dict(identity,**component))
        for name,ns in r['phase_totals_ns'].items():phases.append(dict(identity,stage=name,duration_ms=ns/1e6))
        allocations.append(dict(identity,area55_mm2=b['area55_mm2'],allocation=b['area_allocation']))
    assert seen==expected,dict(missing=sorted(expected-seen),extra=sorted(seen-expected))
    rows=[]
    for (model,clock,scheme),cases in sorted(groups.items()):
        assert len(cases)==(3 if scheme=='SC_ising' else 1)
        def stat(values):return statistics.mean(values),statistics.stdev(values) if len(values)>1 else None
        t,ts=stat([r['time_ms'] for r,b in cases]);e,es=stat([b['system_mJ_by_pJbit']['4.0'] for r,b in cases])
        nh,nhs=stat([b['excluding_lm_head_stage']['time_ms'] for r,b in cases])
        ne,nes=stat([b['excluding_lm_head_stage']['system_mJ_by_pJbit']['4.0'] for r,b in cases])
        areas=[b['area55_mm2'] for r,b in cases];assert len(set(areas))==1
        row=dict(model=model,clock_MHz=clock,scheme=scheme,deploy_seeds=len(cases),area55_mm2=areas[0],
            including_head_ms=t,time_SD_ms=ts,tokens_per_s=1000/t,system4pJ_mJ=e,energy_SD_mJ=es,
            average_W=e/t,onchip_mJ=statistics.mean(b['onchip_mJ'] for r,b in cases),
            external4pJ_mJ=statistics.mean(b['external_mJ_by_pJbit']['4.0'] for r,b in cases),
            excluding_head_stage_ms=nh,excluding_head_stage_mJ=ne,excluding_head_stage_W=ne/nh,
            system6p6_mJ=statistics.mean(b['system_mJ_by_pJbit']['6.6'] for r,b in cases),
            system8_mJ=statistics.mean(b['system_mJ_by_pJbit']['8.0'] for r,b in cases))
        rows.append(row)
    bykey={(r['model'],r['clock_MHz'],r['scheme']):r for r in rows};ratios=[]
    for row in rows:
        if row['scheme']!='SC_ising':continue
        for control in ('BF16_dense','W8_dense','W8_screen'):
            b=bykey[row['model'],row['clock_MHz'],control]
            ratios.append(dict(model=row['model'],clock_MHz=row['clock_MHz'],control=control,
                speedup=b['including_head_ms']/row['including_head_ms'],energy_efficiency=b['system4pJ_mJ']/row['system4pJ_mJ'],
                digital_area_gap_percent=100*(b['area55_mm2']/row['area55_mm2']-1)))
    out.mkdir(parents=True,exist_ok=False)
    def save(name,data):(out/name).write_bytes((json.dumps(data,indent=2)+'\n').encode())
    save('SUMMARY.json',dict(status='ALL36_FULL_CASES_VERIFIED_24_CONFIGURATIONS',rows=rows,ratios=ratios,
        source_manifest_sha256=hashlib.sha256((root/'SNAPSHOT_MANIFEST.json').read_bytes()).hexdigest(),
        repair_manifest_sha256=repair_sha,repair_scope='SC100_large_model_vector_decoder_binding_only' if repair_sha else None,
        PPA_scope='calibrated/modelled55nm components;not full-chip measurement',quality_verified=False,
        head_exclusion='stage boundary;retains finalnorm and already-issuedhead-prefetch',
        random_uncertainty='3deployment reference-address seeds,not3trainingseeds or real-text switching distributions'))
    save('RESULT_INDEX.json',index)
    save('AREA_ALLOCATIONS.json',allocations)
    with (out/'SUMMARY.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    for name,records in [('COMPONENT_ENERGY.csv',components),('PHASE_TIME.csv',phases)]:
        with (out/name).open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    lines=['# Three-model current55nm TLM evaluation','',
        '36 full model runs verified;24 hardware/configuration rows. B1,N2048,K128/S64. Native LPDDR-derived8533 timing;4pJ/bit main energy scenario. No numerical model or quality result.','',
        '|Model|MHz|Path|Area mm2|ms/token|mJ/token|W|token/s|Without head ms|','|---|---:|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:lines.append('|%s|%d|%s|%.4f|%.5f|%.4f|%.4f|%.2f|%.5f|'%(r['model'],r['clock_MHz'],r['scheme'],r['area55_mm2'],r['including_head_ms'],r['system4pJ_mJ'],r['average_W'],r['tokens_per_s'],r['excluding_head_stage_ms']))
    (out/'REPORT.md').write_bytes(('\n'.join(lines)+'\n').encode())
    save('SEAL.json',dict(status='completed',files_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}))
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--repair-root',type=Path);a=p.parse_args()
    rows=aggregate(a.root,a.out,a.repair_root);print(json.dumps(dict(status='completed',rows=len(rows))))
