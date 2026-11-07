"""Check new16KiB runs against sealed24KiB same-host references."""
from pathlib import Path
import hashlib,json,math

ROOT=Path(__file__).resolve().parents[4]
WORK=Path(__file__).resolve().parent
OLD=ROOT/'work/rayggxia/225/module_refresh_20261107'
load=lambda p:json.loads(p.read_bytes())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    rows=[]
    for cores,oldname in [(3,'local250_c3_fixed'),(2,'local250_c2')]:
        op=OLD/oldname;np=WORK/('local_c%d'%cores)
        old,new=load(op/'RESULT.json'),load(np/'RESULT.json')
        ob,nb=load(op/'REPRICED_CURRENT.json'),load(np/'BUDGET.json')
        for folder in (op,np):
            seal=load(folder/'SEAL.json')
            assert sha(folder/'RESULT.json')==seal['result_sha256']
            assert sha(folder/'BUDGET.json')==seal['budget_sha256']
        assert old['status']==new['status']=='completed'
        assert old['seed']==new['seed']==17
        assert old['source_identity']['input_sha256']==new['source_identity']['input_sha256']
        assert old['kernel_active']==new['kernel_active']
        for k in ('digital_BF16_MAC','attention_QK_MAC','PV_ADD','samples','unique_V',
                  'GU_logical_R8_ports','NL_logical_R8_ports','common_R8_words'):
            assert old['actions'].get(k,0)==new['actions'].get(k,0),k
        for kind,v in old['memory']['by_kind'].items():
            for k in ('issued_bytes','issued_address_sum','issued_address_xor'):
                assert v.get(k,0)==new['memory']['by_kind'][kind].get(k,0),(kind,k)
        assert new['memory']['ingress']['holding_bytes']==16384
        assert old['memory']['ingress']['holding_bytes']==24576
        assert not new['memory']['final_pending'] and not new['memory']['final_response_occupied']
        assert new['ingress_capacity_contract']['slots64B']==256
        assert new['compact_memory']['capacity_KiB']==1216
        audit=new['memory']['ingress']['clock_audit']
        assert audit['off_edge_ticks']==0 and audit['min_spacing_cycles']>=1
        area_saved=ob['totals']['covered_area55_mm2']-nb['totals']['covered_area55_mm2']
        assert math.isclose(area_saved,1.188794880000015/3,abs_tol=1e-10)
        assert nb['totals']['short_FFN_measured_energy_mJ'] is None
        phases=[]
        assert [p['stage'] for p in old['phases']]==[p['stage'] for p in new['phases']]
        for x,y in zip(old['phases'],new['phases']):
            phases.append(dict(stage=x['stage'],old_us=x['duration_ns']/1000,new_us=y['duration_ns']/1000))
        rows.append(dict(cores=cores,old_ms=old['simulated_ms'],new_ms=new['simulated_ms'],
            change_percent=(new['time_ns']/old['time_ns']-1)*100,
            old_area55_proxy_mm2=ob['totals']['covered_area55_mm2'],
            area55_proxy_mm2=nb['totals']['covered_area55_mm2'],area_saved_mm2=area_saved,
            phases=phases,peak_returned_bytes=new['memory']['counts']['peak_response_bytes'],
            clock_audit=audit,result_sha256=sha(np/'RESULT.json'),
            old_result_sha256=sha(op/'RESULT.json')))
    summary=dict(status='PASS',scope='complete cold first layer+embedding;nohead;36-layer allocation',
        backend='analytic136.4606GB/s30ns',default_ingress_KiB=16,reference_ingress_KiB=24,
        SRAM_KiB=1216,SRAM_banks=304,return_SRAM_reservation_KiB=32,
        TT250_shortT_PPA_pending=True,new_PPA=False,new_PPL=False,native_whole_token=False,
        arithmetic_samples_inputs_external_bytes_addresses_equal=True,rows=rows)
    (WORK/'SUMMARY.json').write_bytes((json.dumps(summary,indent=2)+'\n').encode())
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
