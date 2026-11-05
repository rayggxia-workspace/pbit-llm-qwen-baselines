"""Summarize sealed JSON; never substitute a pending run for completion."""
import hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[3]
BASE=ROOT/'architecture_tlm/unified_v6/results/memory_20261025'
rows=[]
for p in sorted(BASE.glob('*/MANIFEST.json')):
    man=json.loads(p.read_text());folder=p.parent
    if man.get('status')!='completed':continue
    raw=folder/'RESULT.json'
    if not raw.exists():
        compact=folder/'RESULT_SUMMARY.json'
        derived=json.loads(compact.read_text(encoding='utf-8'))
        expected=next(x for x in json.loads((BASE/'DERIVED_SUMMARY_INDEX.json').read_text(encoding='utf-8')) if x['file']==compact.relative_to(BASE).as_posix())
        if hashlib.sha256(compact.read_bytes()).hexdigest()!=expected['sha256']:raise ValueError('derived SHA mismatch')
        if derived['raw_manifest_sha256']!=hashlib.sha256(p.read_bytes()).hexdigest():raise ValueError('manifest SHA mismatch')
        if derived['raw_result_sha256']!=man['files']['RESULT.json']['sha256']:raise ValueError('raw result SHA mismatch')
        if derived['row']['result_sha256']!=derived['raw_result_sha256']:raise ValueError('row provenance mismatch')
        if hashlib.sha256((folder/'EXECUTION.json').read_bytes()).hexdigest()!=man['files']['EXECUTION.json']['sha256']:raise ValueError('execution SHA mismatch')
        rows.append(derived['row']);continue
    for name,item in man['files'].items():
        path=folder/name
        if name in ('RESULT.json','EXECUTION.json') and not path.is_file():raise ValueError('missing sealed '+name)
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError(str(path))
    r=json.loads((folder/'RESULT.json').read_text())
    traffic=r['DRAM']['traffic'];sram=r['SRAM']['traffic'];c=r['config']
    def total(d,suffix):return sum(v for k,v in d.items() if k.endswith(suffix))
    row=dict(case=man['case'],seed=c['seed'],folder=folder.name,ffn=c['ffn']['mode'],attention=c['attention']['mode'],engines=c['ffn']['engines'],
        backend=r['DRAM']['backend'],TPOT_ms=r['metrics']['TPOT_ms'],cycles=r['metrics']['elapsed_ns']*c['core_hz']/1e9,
        FFN_ms=sum(v for k,v in r['phase_ns'].items() if k.startswith('FFN_'))/1e6,
        SRAM_busy_ms=r['resource_busy_ns']['sram_fabric']/1e6,DRAM_busy_ms=r['resource_busy_ns']['dram_dma']/1e6,
        DRAM_bytes=total(traffic,'_physical_bytes'),SRAM_bytes=total(sram,'_physical_bytes'),
        SRAM_capacity=r['SRAM']['configured_bytes'],SRAM_reserved=r['SRAM']['reserved_peak_bytes'],
        SRAM_macro_area_mm2=r['SRAM']['area_mm2'],SRAM_internal_J=r['energy_J']['SRAM_internal'],SRAM_leak_J=r['energy_J']['SRAM_leakage'],
        DRAM_core_J=r['energy_J'].get('external_DRAMPower_core'),DRAM_interface_J=r['energy_J'].get('external_DRAMPower_interface'),
        full_energy_J=None,full_area_mm2=None,
        SC_tiles=r['FFN_activity'].get('SC_64x64_tiles'),SC_waves=r.get('FFN_contract',{}).get('weight_pipeline',{}).get('counts',{}).get('waves'),
        execution_commit=r.get('execution_commit'),result_sha256=hashlib.sha256((folder/'RESULT.json').read_bytes()).hexdigest())
    negative=[]
    for adapter, power in r['DRAM'].get('details',{}).get('power_at_system_end',{}).items():
        if not isinstance(power,dict):continue
        for name,value in power.get('core_components_J',{}).items():
            if isinstance(value,(int,float)) and value<0:negative.append(dict(adapter=adapter,component=name,J=value))
    row['negative_DRAM_core_components']=negative
    row['DRAM_energy_status']='raw DRAMPower estimate; negative component from current-limit combination, not calibrated PPA' if negative else 'model estimate, not measured'
    rows.append(row)
print(json.dumps(dict(scope='sealed synthetic full-model decode TLM, no new PPL/RTL/PPA',rows=rows),ensure_ascii=False,indent=2))
