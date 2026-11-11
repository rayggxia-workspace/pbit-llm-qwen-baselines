"""Verify frozen local scheduler gates;emit only small reproducible summaries."""
from pathlib import Path
import argparse,hashlib,json

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())

def verify(work):
    x=load(work/'EXECUTION.json');source=Path(x['root']);manifest=load(source/'MANIFEST.json')
    assert sha(source/'MANIFEST.json')==x['manifest_sha256']
    for name,h in manifest['files_sha256'].items():assert sha(source/name)==h,name
    rows=[]
    for name in ('closed250_v3','closed500_v3','closed500_sram2_v3'):
        path=work/name;seal=load(path/'SEAL.json');assert seal['status']=='completed'
        for f,h in seal['files_sha256'].items():assert sha(path/f)==h,(name,f)
        r,b,v=[load(path/(f+'.json')) for f in ('RESULT','BUDGET','VALIDATION')]
        assert r['status']=='completed' and v['status']=='PASS'
        for f,h in r['code_sha256'].items():assert h==manifest['files_sha256'][f]
        assert r['bindings_sha256']==manifest['files_sha256'][str(r['clock_MHz'])+'MHz/BINDINGS.json']
        assert r['macro_config_sha256']==manifest['files_sha256'][str(r['clock_MHz'])+'MHz/WHOLE_CONFIG.json']
        assert b['full_system_area_mm2'] is None and b['full_system_energy_mJ_token'] is None
        assert not b['used55nm_prices'] and b['area_multiplier']==1
        assert r['SRAM']['dynamic_mJ'] is None and r['SRAM']['area_mm2'] is None
        assert r['memory']['by_kind']['sample_V']['issued_bytes']==r['actions']['unique_V']*256
        assert all(z['max_words_per_head']<=2 for z in r['resource_audit']['PV'])
        assert all(z['peak_core_reserved_results']<=2 for z in r['common_FFN_stages'])
        assert all(z['period_ns']==1000/r['clock_MHz'] for z in (r['memory']['ingress'],))
        rows.append(dict(case=name,clock_MHz=r['clock_MHz'],FFN_cores=r['FFN_cores'],layers=r['layers'],head=r['includes_lm_head'],
            time_ms=r['time_ms'],without_lm_head_stage_ms=r['time_without_lm_head_stage_ms'],lm_head_stage_ms=r['lm_head_stage_ms'],
            head_probe_rows=r['head_probe_rows'],full_vocab_tiling_checked=r['full_vocab_tiling_checked'],
            first_layer_end_ms=next(z['end_ns']/1e6 for z in r['phases'] if z['stage']=='residual' and z['layer']==0),
            SRAM_latency_cycles=r['assumptions']['SRAM_latency_cycles'],external_bytes=b['external_bytes'],
            SRAM_read_bytes=r['SRAM']['counts']['read_physical_bytes'],SRAM_write_bytes=r['SRAM']['counts']['write_physical_bytes'],
            covered_component_area_mm2=b['covered_component_area_mm2'],covered_component_energy_mJ=b['covered_component_energy_mJ'],
            full_system_area_mm2=None,full_system_energy_mJ_token=None,
            original_result_path=str(path),files_sha256=dict(seal['files_sha256'],**{'SEAL.json':sha(path/'SEAL.json')})))
    assert rows[0]['layers']==2 and rows[0]['head'] and rows[0]['head_probe_rows']==384
    assert rows[1]['layers']==rows[2]['layers']==1 and not rows[1]['head'] and not rows[2]['head']
    for key in ('external_bytes','SRAM_read_bytes','SRAM_write_bytes'):
        assert rows[1][key]==rows[2][key],('SRAM latency sensitivity must keepwork',key)
    return dict(status='PASS_FROZEN_WHOLE_MODEL_INTEGRATION_GATES',cases=rows,
        checks=['7 frozeninput hashes','3case SEAL/files','executed code/binding/config identity',
                'FFN/sample/conversion/readwork andcredit gates','sharedGQA sampleV bytes equal realcachemisses',
                'finite PVandcore result buffers','pending costs remainnull/no55 prices','matchedSRAM latencywork'],
        execution=x,full36_run=False,new_RTL_PT=False,native_DRAM_run=False,
        SRAM2cycle_delta_percent=100*(rows[2]['time_ms']/rows[1]['time_ms']-1))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();v=verify(a.work);a.out.write_bytes((json.dumps(v,indent=2)+'\n').encode())
    print(json.dumps(dict(status=v['status'],cases=[{k:z[k] for k in ('case','time_ms','layers','head')} for z in v['cases']])))
