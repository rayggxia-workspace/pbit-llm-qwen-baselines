from pathlib import Path
import hashlib,json
HERE=Path(__file__).parent
def main():
    c=json.loads((HERE/'MODULE_CATALOG.json').read_bytes())
    s=json.loads((HERE/'ASSEMBLY_STATUS.json').read_bytes())
    assert (c['clock_MHz'],c['period_ns'])==(250,4)
    assert c['PVT']==dict(corner='TT',voltage_V=1.2,temperature_C=25)
    assert c['independence']==dict(modifies_100MHz=False,imported_by_100MHz=False,
        sets_global_default=False,run_function_provided=False,new_jobs=False,new_RTL_PT=False)
    assert all(v is None for v in c['whole_model_outputs'].values())
    # The original catalog is frozen historical evidence. Current assembly can
    # supersede its catalog-only status without rewriting prior characterization.
    if s['complete_TLM_provided']:
        assert s['ordinary_FMA_lanes']==256 and s['FFN_core_count']==3
        assert s['SRAM_clock_MHz']==s['DMA_front_clock_MHz']==250
    else:assert s['ordinary_FMA_lanes'] is None
    assert c['full_SC_samples']==64 and c['full_SC_frame_ns']==66*4
    assert len(c['ffn_and_array_modules'])==8 and len(c['verified_archives'])==8
    assert len(c['attention_legacy_modules'])==9
    assert not any(x['accepted_as_system_profile'] for x in c['ffn_and_array_modules']+c['attention_legacy_modules'])
    assert not c['attention_archive_status']['complete_archive_sha_available']
    assert all(x['PVT']=='TT_1.2V_25C' and x['clock_MHz']==250 for x in c['ffn_and_array_modules'])
    summary=dict(status='PASS_catalog_isolation_and_scope',checks=11,
        files_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (HERE/'MODULE_CATALOG.json',HERE/'ASSEMBLY_STATUS.json')},
        catalog_check_does_not_launch_simulation=True,new_PPA_in_catalog_check=False)
    print(json.dumps(summary))
if __name__=='__main__':main()
