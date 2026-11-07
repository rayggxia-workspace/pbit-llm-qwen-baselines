"""Read-only TT250 evidence catalog. No whole-model aggregation or defaults."""
from pathlib import Path
from collections import Counter
import hashlib,json,math

PROJECT=Path('C:/Users/86134/Documents/a_P_BIT')
WD=Path(__file__).resolve().parents[4]
OUT=WD/'architecture_tlm/sram1216_20261106/250MHz'
OUT.mkdir(exist_ok=True)
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,x):(OUT/name).write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())

ffn=PROJECT/'architecture_tlm/array_baselines_20261106/frequency_variants/tt12_25c_250mhz/power_20261106/results/SUMMARY.json'
report=ffn.with_name('REPORT_ZH.md')
audit=PROJECT/'project_archives/attention_resynth_tt250_20261106/AUDIT_PENDING_20261107.json'
atnext=PROJECT/'architecture_tlm/module_handoff/attention_resynth_tt250_20261106/NEXT_STEPS_20261107_ZH.md'
att100=PROJECT/'architecture_tlm/module_handoff/attention_resource_rtl_20261107/HANDOFF_ZH.md'
sram=PROJECT/'project_archives/ffn_sram_batch204_20261106/runtime/base/architecture_tlm/unified_v6/shared_memory.py'
dram=PROJECT/'project_archives/ffn_sram_batch204_20261106/runtime/base/profiles/derived8533.yaml'
summary=load(ffn);a=load(audit)
assert summary['status']=='ALL8_REPORTS_COLLECTED' and summary['collected_cases']==8
assert (summary['clock_MHz'],summary['corner'],summary['voltage_V'],summary['temperature_C'])==(250,'TT',1.2,25)
checked=[]
for record in summary['archives']:
    p=Path(record['local']);assert p.stat().st_size==record['bytes'],p
    assert sha(p)==record['sha256'],p
    checked.append(dict(case_index=record['case_index'],local=p.relative_to(PROJECT).as_posix(),
        bytes=record['bytes'],sha256=record['sha256'],member_SHA_count=record['archive_members_SHA_verified']))

rows=summary['rows']
modules=[]
for case in sorted({r['case'] for r in rows}):
    selected=[r for r in rows if r['case']==case]
    assert len({r['area55_mm2'] for r in selected})==1
    modules.append(dict(module=case,kind=selected[0]['kind'],
        status='collected_originals_SHA_verified_lower_level_characterization',
        clock_MHz=250,PVT='TT_1.2V_25C',area55_mm2=selected[0]['area55_mm2'],
        measured_rows=[{k:r[k] for k in ('profile','mode','whole_core_mW','pJ_per_unit','unit','seeds','setup_ns','hold_ns','flags')} for r in selected],
        accepted_as_system_profile=False,
        note='full_tt12 includes local RNG/front/backend; do not add its components again' if case=='full_tt12' else 'component or comparison array; not a whole-chip price'))
attention=[]
for item in a['summary']['cases']:
    if item['period_ns']!=4:continue
    status=next((r for r in a['cases'] if r['top']==item['top'] and r['period_ns']==4),{})
    # Different modules have different result formats; no universal-window count
    # is promoted to an acceptance decision. Preserve the original report gate.
    windows=[]
    for result in item.get('result_files',[]):
        data=result.get('data')
        if isinstance(data,dict):windows.extend(data.get('windows',[]))
    attention.append(dict(module=item['top'],clock_MHz=250,period_ns=4,PVT='TT_1.2V_25C',
        job=str(item['job']),job_receipt=status.get('sacct',''),
        status='metadata_present_original_archive_acceptance_pending',
        result_file_count=len(item.get('result_files',[])),json_windows_visible=len(windows),
        result_schema_note='SparQ modules may use other files;zero windows here does not mean no simulation',
        missing_windows=['seed1009/backpressure','seed1009/idle_hold','seed1009/idle_toggle'] if item['top']=='db_fma64_c4' else [],
        accepted_as_system_profile=False,TT100_pair_not_SS100=True))
assert len(attention)==9
missing=[
 dict(module='PV4_per_head',status='needs100MHz_gate_X_fix_then_TT250_characterization',reason='old bf_vacc16 is not newPV128'),
 dict(module='QK_shared_mode_wrapper',status='TT250_not_yet_bound',reason='SS100 slice passes;4ns wrapper and realK supply remain to verify'),
 dict(module='FP32_final_reduction32',status='TT250_unit_price_and_II_not_yet_bound',reason='check existing fp32ADD evidence first; do not assume new simulation needed'),
 dict(module='SRAM_banked_fabric',status='250MHz_clock_port_schedule_not_integrated',reason='existing macro data is available; no proof for new304bank/decoder/fabric timing'),
 dict(module='DMA_and_return_path',status='TT250_profile_not_yet_bound',reason='keep finite existingDRAM backend and explicit clock boundaries'),
 dict(module='format_norm_RoPE_residual',status='TT250_profile_not_yet_bound',reason='inventory existing evidence before requesting additional RTL'),
 dict(module='GU_T8_NL_Wd_T32',status='shortT_TT250_PPA_not_characterized',reason='full_tt12 isC20/T64; do not relabel as shortT or scale energy by frequency')]
sources=[ffn,report,audit,atnext,att100,sram,dram]
catalog=dict(schema='isolated_tt250_evidence_catalog_v1',date='2026-11-07',owner='rayggxia',issue=225,pr=248,
    stage='partial_module_catalog_only_no_complete_TLM',clock_MHz=250,period_ns=4,
    PVT=dict(corner='TT',voltage_V=1.2,temperature_C=25),
    area_rule='project65flow raw x0.81 once for55-equivalent; values here already scaled; no power/latency scaling',
    full_SC_cycles=66,full_SC_frame_ns=264,full_SC_samples=64,
    ffn_and_array_modules=modules,attention_legacy_modules=attention,missing_or_unbound=missing,
    attention_archive_status=dict(collector_job='38617015',status='TIMEOUT',
        partial_archive_bytes=a['files']['REPORTS.tar.gz']['bytes'],complete_archive_sha_available=False,
        FMA64_job='38617005',FMA64_status='TIMEOUT_12of15_PT_windows_present'),
    independence=dict(modifies_100MHz=False,imported_by_100MHz=False,sets_global_default=False,
        run_function_provided=False,new_jobs=False,new_RTL_PT=False),
    whole_model_outputs=dict(time_ms=None,energy_mJ=None,power_W=None,die_area_mm2=None),
    source_manifest_sha256=summary['source_manifest_sha256'],verified_archives=checked,
    source_files=[dict(path=p.relative_to(PROJECT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sources])
save('MODULE_CATALOG.json',catalog)
save('ASSEMBLY_STATUS.json',dict(status='not_ready_for_complete_model',frequency_MHz=250,PVT=catalog['PVT'],
    ordinary_FMA_lanes=None,ordinary_FMA_candidates_only=[320,640],FFN_core_count=None,
    shared_QK_schedule=None,PV_implementation=None,SRAM_clock_and_fabric=None,
    capacity_reference_KiB=1216,capacity_validated_for250=False,
    DRAM_policy='externalLPDDRderived8533 reference retained; external bandwidth does not scale with core clock',
    complete_TLM_provided=False,whole_model_outputs=catalog['whole_model_outputs'],
    prohibitions=['no100MHz_result_overwrite','noSS100_TT250_causal_claim','no100_time_divide2.5',
        'no100_power_times2.5','noT64_toT8_T32_PPA_relabel','no512lane_QK_lease_from320lane_pool',
        'nofullSC_plus_component_double_count','nopartial_archive_as_accepted_full_archive']))
print(json.dumps(dict(ffn_modules=len(modules),verified_archives=len(checked),
    archive_members_total=sum(x['member_SHA_count'] for x in checked),attention_modules=len(attention),
    missing_or_unbound=len(missing),whole_TLM_provided=False)))
