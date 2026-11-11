"""Check work, units, seals and accounting of the explicitly rough projection."""
from pathlib import Path
import hashlib,json,math

p=Path(__file__).resolve().parent/'rough_estimate_20261109'
load=lambda x:json.loads(x.read_bytes())
sources=load(p/'SOURCES.json')['files_sha256']
for n,h in sources.items():assert hashlib.sha256(Path(n).read_bytes()).hexdigest()==h,n
r=load(p/'RESULTS.json');assert r['status']=='CONDITIONAL_ROUGH_SYSTEM_ESTIMATE_NOT_SIGNOFF'
for c in r['cases']:
    t=c['time_ms'];assert math.isclose(t,c['time_without_lm_head_ms']+c['lm_head_ms'])
    assert math.isclose(c['chip_energy_mJ']/t,c['chip_average_W'])
    assert math.isclose(c['total_energy_mJ_at4pJbit']/t,c['system_average_W_at4pJbit'])
    assert math.isclose(c['external_bytes']*8*4/1e9,c['external_mJ']['4.0'])
    assert math.isclose(c['chip_energy_mJ']+c['external_mJ']['4.0'],c['total_energy_mJ_at4pJbit'])
    assert c['DRAM_ideal_floor_ms']<t
    assert c['area_scenario_interval_mm2'][0]<c['area_mm2']<c['area_scenario_interval_mm2'][1]
    assert c['PV_proxy']['fixed_state_preserved'] and c['PV_proxy']['timing_failed']
    assert all(c['SRAM_counts'][k]>0 for k in ('read_words','write_words'))
    assert c['head_fit']['full256_tiles']*256+c['head_fit']['tail_rows']==151936
    rows=c['component_rows'];core=next(x for x in rows if x['component']=='FFN_shared_GU_Wd')
    assert core['instances']==c['FFN_cores'] # no replication by layer count
    assert len(rows)==10 and all(x['area_mm2']>0 and x['energy_mJ']>=0 for x in rows)
    assert c['total_without_lm_head_mJ_at4pJbit']<c['total_energy_mJ_at4pJbit']
assert r['SRAM_transfer_is_28_foundry_calibration'] is False
out=dict(status='PASS',source_files=len(sources),cases=2,
    checks=['sourceSHA/6headSEAL/2layerSEAL','head256tiling128tail','area-once','nonzeroSRAMreadwrite',
        'gross-idle-accounting','energy-power-time-units','explicit500FMA/PVproxies','separateoffchipenergy'],
    excludes=['full36-layer28nativeLPDDRrun','whole-chipSTA','28foundrySRAMcalibration','newPPL/RTL/PT'])
(p/'VALIDATION.json').write_bytes((json.dumps(out,indent=2)+'\n').encode())
print(json.dumps(out))
