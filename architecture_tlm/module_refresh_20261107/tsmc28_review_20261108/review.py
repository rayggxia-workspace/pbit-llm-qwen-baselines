"""Consumer audit of measured28nm components; no55nm override or new TLM run."""
from pathlib import Path
import argparse,hashlib,json,math,tarfile

HERE=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
def save(n,x):(HERE/n).write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def file_sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def run(project):
    owner=project/'architecture_tlm/module_handoff/ffn_tsmc28_three_classes_20261107'
    inputs=owner/'POWER_RESULTS_20261108.json';p=json.loads(inputs.read_bytes())
    work=project/'tmp/matrix-t32-issue204-20261028/work/rayggxia/204/tsmc28_review_20261108/recovery/v3_model_scope'
    collection=work/'COLLECTION_VERIFIED_3cases_44windows.json'
    c=json.loads(collection.read_bytes());verification=work/'FINAL_VERIFICATION.json'
    v=json.loads(verification.read_bytes())
    assert p['full_PT_windows']==v['full_PT_windows']==44 and v['status']=='PASS'
    assert set(p['qualified_pre_layout_prices'])=={'ffn_250','bf16_250'}
    assert p['timing_failed_measurements']['a9_250']['data_hold_ns']<0
    assert sum(p['cases'][k]['PT_windows'] for k in ('ffn_250','bf16_250','a9_250'))==44
    archives=[];members=0
    for case in ('ffn_250','bf16_250','a9_250'):
        entry=next(x for x in c['items'] if x['case']==case)
        archive=Path(entry['local']);assert archive.stat().st_size==entry['bytes']
        assert file_sha(archive)==entry['sha256']==p['cases'][case]['original_archive']['sha256']
        expected=entry['member_sha256'];seen={}
        with tarfile.open(archive,'r|gz') as tf:
            for member in tf:
                if member.name in expected:
                    assert member.isfile() and member.name not in seen
                    with tf.extractfile(member) as f:seen[member.name]=sha(f.read())
        assert seen==expected and len(seen)==entry['verified_report_members']
        members+=len(seen)
        archives.append(dict(case=case,path=str(archive),sha256=entry['sha256'],verified_members=len(seen)))
    q=p['qualified_pre_layout_prices']['ffn_250'];idle=q['modes']['idle_source_stopped']
    core=dict(status=q['status'],process=q['process'],clock_MHz=250,PVT=q['PVT'],
        area_raw_um2=q['area_um2'],area_factor=1.,area_mm2=q['area_mm2'],
        waiting_total_W=idle['mean_core_power_mW']/1000,waiting_leakage_W=idle['mean_leakage_mW']/1000,
        waiting_reference_seed=17,timing_pass=True,setup_slack_ns=q['data_setup_ns'],hold_slack_ns=q['data_hold_ns'],
        modes={},unmodeled_TIE_power_W=None,unmodeled_TIE_cells=q['unmodeled_tie_count'],
        measured_boundary=q['boundary'],physical_chip_price=False)
    for mode,label,T in [('GU','GU_active',16),('Wd','Wd_active',32)]:
        z=q['modes'][label];ns=z['window_ns']/z['operations_per_window'];dots=z['complete_DOT64_per_window']/z['operations_per_window']
        gross=z['gross_pJ_per_DOT64']*dots
        assert dots==128 and math.isclose(gross,z['mean_core_power_mW']*ns,rel_tol=1e-10)
        assert ns/4 in (18,34)
        core['modes'][mode]=dict(T=T,frame_cycles=int(ns/4),frame_ns=ns,DOT64_per_frame=128,
            mean_core_power_mW=z['mean_core_power_mW'],gross_pJ_per_DOT64=z['gross_pJ_per_DOT64'],gross_pJ_per_frame=gross,
            incremental_pJ_per_frame=gross-core['waiting_total_W']*ns*1000,
            deployment_activity='synthetic3seed;idle seed17 only')
    old_path=project/'architecture_tlm/module_refresh_20261107/FFN_PROFILE.json'
    old=json.loads(old_path.read_bytes())['versions']['250MHz']['core']
    assert old['PVT']=='TT1.2V25C' and old['modes']['GU']['frame_cycles']==19
    gate=project/'project_archives/tlm_energy225_20261108/gate'
    r=json.loads((gate/'RESULT.json').read_bytes());b=json.loads((gate/'BUDGET.json').read_bytes())
    active=r['kernel_active'];wall=r['time_ns'];cores=r['short_FFN_contract']['physical_cores']
    new_busy=sum(active[n]*core['modes'][k]['frame_ns'] for k,n in [('GU','GU_frames'),('Wd','Wd_M128_frames')])
    new_gross=sum(active[n]*core['modes'][k]['gross_pJ_per_frame']/1e9 for k,n in [('GU','GU_frames'),('Wd','Wd_M128_frames')])
    waiting_ns=cores*wall-new_busy;assert waiting_ns>=0
    new_wait=waiting_ns*core['waiting_total_W']/1e6
    previous=b['FFN_core_calibration']
    fma=p['qualified_pre_layout_prices']['bf16_250'];fma_old=json.loads((project/'architecture_tlm/sram1216_20261106/250MHz/vendor_attention/CALIBRATION.json').read_bytes())['TT250_units']['db_fma16_c4']
    candidate=dict(schema='isolated28nm_component_tariffs_not_whole_chip',default_enabled=False,FFN_core=core,
        BF16_FMA16_C4=dict(area_mm2=fma['area_mm2'],clock_MHz=250,process=fma['process'],
            continuous_gross_pJ_per_FMA=fma['modes']['continuous']['gross_pJ_per_DOT64']/64,
            idle_hold_W=fma['modes']['idle_hold']['mean_core_power_mW']/1000,
            idle_toggle_W=fma['modes']['idle_toggle']['mean_core_power_mW']/1000,
            unmodeled_TIE_power_W=None,mixed_wrapper_energy='not measured; retain explicit integration estimate'),
        A9_ready=False,other_blocks_28nm_ready=False,all_process_TLM_ready=False)
    comparison=dict(scope='component comparison;process/voltage/pipeline change together',
        FFN=dict(old55=old,new28=core,area_reduction_percent=100*(1-core['area_mm2']/old['area55_mm2']),
            GU_energy_reduction_percent=100*(1-core['modes']['GU']['gross_pJ_per_DOT64']/old['modes']['GU']['gross_pJ_per_DOT64']),
            Wd_energy_reduction_percent=100*(1-core['modes']['Wd']['gross_pJ_per_DOT64']/old['modes']['Wd']['gross_pJ_per_DOT64'])),
        fixed_trace_FFN_reprice=dict(scope='same55nm cold-layer activity and wall time; not28nm system timing',
            wall_ns=wall,cores=cores,frames=active,old_core_total_mJ=previous['total_mJ'],
            new_modeled_core_active_gross_mJ=new_gross,new_modeled_core_wait_mJ=new_wait,new_modeled_core_total_mJ=new_gross+new_wait,
            old_core_area_mm2=previous['area55_mm2'],new_core_area_mm2=cores*core['area_mm2'],
            energy_reduction_percent=100*(1-(new_gross+new_wait)/previous['total_mJ']),
            whole_chip_area_mm2=None,whole_chip_energy_mJ=None,new_TPOT_ms=None),
        BF16_matched_continuous=dict(old55_area_per_FMA16_mm2=fma_old['area55_mm2'],new28_area_per_FMA16_mm2=fma['area_mm2'],
            old55_gross_pJ_per_FMA=fma_old['groups']['continuous']['gross_pJ_per_operation'],
            new28_gross_pJ_per_FMA=fma['modes']['continuous']['gross_pJ_per_DOT64']/64),
        no_change_to_55nm_defaults=True,no_jobs_submitted=True)
    save('CANDIDATE_COMPONENTS.json',candidate);save('COMPARISON.json',comparison)
    save('SOURCE_INDEX.json',dict(files={str(x.relative_to(project)):sha(x.read_bytes()) for x in (inputs,owner/'POWER_RESULTS_20261108_ZH.md',owner/'HANDOFF_ZH.md',collection,verification,old_path)},
        archives=archives,gate_result_sha256=sha((gate/'RESULT.json').read_bytes()),gate_budget_sha256=sha((gate/'BUDGET.json').read_bytes()),public_boundary='indexes/numerical tariffs only;no PDK/netlist/raw source copied'))
    save('VALIDATION.json',dict(status='PASS_CONSUMER_REVIEW',PT_windows=44,main_archives_verified=3,report_members_verified=members,
        power_units_and_frame_normalization=True,no_0p81_for28nm=True,failed_A9_excluded=True,
        first_party_owner_report_retained=True,new_RTL_PT=False,new_TLM_run=False,default_changed=False))
    print(json.dumps(dict(verified_members=members,FFN_reprice=comparison['fixed_trace_FFN_reprice'],
        BF16=comparison['BF16_matched_continuous']),ensure_ascii=True))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--workspace',type=Path,required=True);run(ap.parse_args().workspace)
