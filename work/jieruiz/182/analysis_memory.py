"""Summarize sealed JSON; never substitute a pending run for completion."""
import hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[3]
BASE=ROOT/'architecture_tlm/unified_v6/results/memory_20261025'
rows=[]
for p in sorted(BASE.glob('*/MANIFEST.json')):
    man=json.loads(p.read_text());folder=p.parent
    if man.get('status')!='completed':continue
    for name,item in man['files'].items():
        path=folder/name
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError(str(path))
    r=json.loads((folder/'RESULT.json').read_text())
    traffic=r['DRAM']['traffic'];sram=r['SRAM']['traffic'];c=r['config']
    def total(d,suffix):return sum(v for k,v in d.items() if k.endswith(suffix))
    row=dict(case=man['case'],ffn=c['ffn']['mode'],attention=c['attention']['mode'],engines=c['ffn']['engines'],
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
    rows.append(row)
print(json.dumps(dict(scope='sealed synthetic full-model decode TLM, no new PPL/RTL/PPA',rows=rows),ensure_ascii=False,indent=2))
