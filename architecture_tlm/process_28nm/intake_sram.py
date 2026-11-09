"""Bind the delivered real S0 SRAM macro; do not copy proprietary libraries."""
from pathlib import Path
from types import SimpleNamespace as NS
import argparse,ast,copy,hashlib,json,math,tarfile
from sram_characterization import budget
from whole_pricing import price

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];WS=ROOT.parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument('--delivery',type=Path,default=WS/'architecture_tlm/process_28nm/SRAM_CHARACTERIZATION_RESULTS_20261109.json')
    args=cli.parse_args();source=args.delivery;x=json.loads(source.read_bytes());source_sha=sha(source)
    assert x['area_scale']==1 and len(x['library_records'])==8 and len(x['power_windows'])==12
    s0=next(r for r in x['library_records'] if r['macro_id']=='S0' and r['VDD_V']==0.9)
    assert s0['depth']==256 and s0['data_bits']==128 and s0['ports']=='1RW'
    assert s0['lib_area_matches_lef'] and s0['area_scale']==1
    assert math.isclose(s0['width_um']*s0['height_um'],s0['area_um2'],abs_tol=1e-7)
    archive=WS/'sram28_char_20261109/results/38639794/reports.tar.gz'
    assert sha(archive)==x['archive_SHA256']
    verified=0
    with tarfile.open(archive,'r:gz') as tar:
        members={m.name:m for m in tar.getmembers() if m.isfile()}
        for r in x['power_windows']:
            suffix='/'.join(Path(r['raw_report']).parts[-2:])
            found=[m for n,m in members.items() if n.replace('\\','/').endswith(suffix)]
            assert len(found)==1,(suffix,len(found))
            assert hashlib.sha256(tar.extractfile(found[0]).read()).hexdigest()==r['raw_report_SHA256']
            assert r['setup_slack_ns']>=0 and r['hold_slack_ns']>=0 and r['seed']==17
            assert r['activity_coverage']==1 and r['macro_id']=='S0';verified+=1
    calibration=dict(status='REAL28NM_S0_MACRO_TT_PT_CHARACTERIZED',process='TSMC28HPC+',
        PVT='TT0.9V25C',area_multiplier=1,macro=s0['macro_name'],
        depth=256,data_bits=128,ports='1RW',area_mm2_per4KiB=s0['area_um2']/1e6,
        characterization_sha256=source_sha,archive_sha256=sha(archive),
        clk_to_Q_ns=s0['clk_to_Q_max_ns'],minimum_period_ns=s0['min_read_period_ns'],
        input_slew_ns=s0['slew_ns'],output_load_pF=s0['output_load_pF'],versions={})
    for mhz in (250,500):
        windows={r['mode']:r for r in x['power_windows'] if r['MHz']==mhz}
        off=windows['IDLE_CLK_OFF']['total_W'];on=windows['IDLE_CLK_ON']['total_W'];period=1000/mhz
        assert len(windows)==6 and period>s0['min_read_period_ns']
        cfg=json.loads((HERE/f'{mhz}MHz/WHOLE_CONFIG.json').read_bytes())
        s=cfg['SRAM'];s.update(macro_characterized=True,price_status=calibration['status'],
            read_pJ_per16B=windows['RD_RAND']['incremental_access_clock_off_baseline_pJ'],
            write_pJ_per16B=windows['WR_RAND']['incremental_access_clock_off_baseline_pJ'],
            leak_W_per4KiB=off,clock_on_idle_W_per4KiB=on,
            area_mm2_per4KiB=calibration['area_mm2_per4KiB'],timing_qualified=True,
            timing_scope='single real S0 macro near interface;bank fabric remains host timing model',
            price_baseline='increment over clock-off + full clock-off residency;idle banks assumed gated',
            characterization_sha256=source_sha,macro=s0['macro_name'],
            policy='measured16B1RW;1cycle return,II1 at4/2ns;no55nmprice',
            read_gross_pJ_per16B=windows['RD_RAND']['gross_access_pJ'],
            write_gross_pJ_per16B=windows['WR_RAND']['gross_access_pJ'])
        for mode,key in [('RD_RAND','read_pJ_per16B'),('WR_RAND','write_pJ_per16B')]:
            assert math.isclose(s[key]+off*period*1000,windows[mode]['gross_access_pJ'],abs_tol=1e-10)
        cfg['status']='REAL28_SRAM_BOUND_OTHER_PLATFORM_MACROS_RETAINED'
        dump(HERE/f'{mhz}MHz/WHOLE_CONFIG.json',cfg)
        calibration['versions'][str(mhz)]=copy.deepcopy(s)
        # The actual ledger must reproduce one whole PT window, including idle.
        for mode,reads,writes in [('RD_RAND',4096,0),('WR_RAND',0,4096)]:
            one=copy.deepcopy(s);one['bank_count']=1
            probe=dict(clock_MHz=mhz,time_ns=4096*period,kernel_active={},
                SRAM=dict(counts=dict(read_words=reads,write_words=writes),
                    physical_banks=1,word_bytes=16,capacity_bytes=4096))
            measured=budget(probe,one)['ordinary_total_mJ']*1e9
            assert math.isclose(measured,windows[mode]['gross_window_pJ'],abs_tol=1e-6)
    dump(HERE/'SRAM_CALIBRATION_20261109.json',calibration)

    base=ROOT/'work/rayggxia/225/process28_whole_20261109'
    probes=[]
    for name in ('closed250_v3','closed500_v3','closed500_sram2_v3'):
        folder=base/name;r=json.loads((folder/'RESULT.json').read_bytes())
        before={n:sha(folder/n) for n in ('RESULT.json','BUDGET.json','SEAL.json')}
        for n,v in json.loads((folder/'SEAL.json').read_bytes()).items():
            if isinstance(v,str) and len(v)==64 and (folder/n).is_file():assert sha(folder/n)==v
        mhz=r['clock_MHz'];cfg=json.loads((HERE/f'{mhz}MHz/WHOLE_CONFIG.json').read_bytes())
        r['macro_config']=cfg
        binding=json.loads((HERE/f'{mhz}MHz/BINDINGS.json').read_bytes())
        m=NS(common_cores=r['FFN_cores'],sampler_pool=NS(slots=4),norm_pool=NS(slots=4),top_pool=NS(slots=4))
        z=price(m,r,binding);s=z['SRAM_calibration'];assert s is not None
        assert all(v['component']!='SRAM28' for v in z['unpriced'])
        assert math.isclose(s['ordinary_total_mJ'],s['ordinary_incremental_mJ']+s['clock_off_residency_mJ'],abs_tol=1e-12)
        assert math.isclose(s['area_mm2'],2.851229052,abs_tol=1e-12)
        # Future explicit reads and the price proxy cannot both charge this work.
        explicit=copy.deepcopy(r);n=s['CIM_weight_extra_reads']
        explicit['SRAM']['counts']['read_words']+=n
        explicit['SRAM']['by_tag']['CIM_weight_presentation_read']={'read_words':n}
        same=budget(explicit,cfg['SRAM'])
        assert same['CIM_weight_read_mJ']==0
        assert math.isclose(same['total_including_CIM_mJ'],s['total_including_CIM_mJ'],abs_tol=1e-12)
        assert before=={n:sha(folder/n) for n in before}
        probes.append(dict(case=name,clock_MHz=mhz,time_ms=r['time_ns']/1e6,SRAM=s,
            original_sha256=before,known_component_area_mm2=z['covered_component_area_mm2'],
            known_component_energy_mJ=z['covered_component_energy_mJ'],
            remaining_unpriced=[v['component'] for v in z['unpriced']]))

    historical=HERE/'rough_estimate_20261109/RESULTS.json'
    old=json.loads(historical.read_bytes());full=[]
    for prev in old['cases']:
        mhz=prev['clock_MHz'];cfg=calibration['versions'][str(mhz)]
        r=dict(clock_MHz=mhz,time_ns=prev['time_ms']*1e6,
            kernel_active=dict(GU_frames=36*6080,Wd_M128_frames=36*3040),
            SRAM=dict(counts=prev['SRAM_counts'],physical_banks=240,word_bytes=16,capacity_bytes=960*1024))
        s=budget(r,cfg)
        de=s['total_including_CIM_mJ']-prev['SRAM_energy_mJ']
        da=s['area_mm2']-prev['SRAM_area_mm2']
        new=dict(clock_MHz=mhz,FFN_cores=prev['FFN_cores'],
            time_ms=prev['time_ms'],time_without_lm_head_ms=prev['time_without_lm_head_ms'],
            previous_area_mm2=prev['area_mm2'],previous_chip_energy_mJ=prev['chip_energy_mJ'],
            previous_SRAM_energy_mJ=prev['SRAM_energy_mJ'],
            SRAM_area_mm2=s['area_mm2'],SRAM_energy_mJ=s['ordinary_total_mJ'],
            CIM_weight_SRAM_proxy_mJ=s['CIM_weight_read_mJ'],SRAM_calibration=s,
            chip_energy_mJ=prev['chip_energy_mJ']+de,
            total_energy_mJ_at4pJbit=prev['total_energy_mJ_at4pJbit']+de,
            area_mm2=prev['area_mm2']+1.15*da,
            chip_average_W=(prev['chip_energy_mJ']+de)/prev['time_ms'],
            system_average_W_at4pJbit=(prev['total_energy_mJ_at4pJbit']+de)/prev['time_ms'],
            external_bytes=prev['external_bytes'],external_mJ=prev['external_mJ'],
            energy_scenarios_mJ={k:v+de for k,v in prev['energy_scenarios_mJ'].items()},
            retained_non_SRAM_energy_mJ=prev['chip_energy_mJ']-prev['SRAM_energy_mJ'],
            other_blocks_remain_previous_conditional_estimates=True,
            added_area_placement_factor=1.15)
        assert math.isclose(new['chip_energy_mJ'],new['retained_non_SRAM_energy_mJ']+s['total_including_CIM_mJ'],abs_tol=1e-12)
        assert math.isclose(new['energy_scenarios_mJ']['4.0'],new['total_energy_mJ_at4pJbit'],abs_tol=1e-12)
        full.append(new)
    result=dict(status='SRAM_REAL_MACRO_REPRICING_OF_PREVIOUS_CONDITIONAL_FULL_ESTIMATE',
        actual_full36_timing_run=False,clock250500_configs_bound=True,macro_power_windows_verified=verified,
        probes=probes,cases=full,source_sha256=dict(delivery=source_sha,archive=sha(archive),historical=sha(historical)),
        checks=['12raw_power_reports_SHA','macro_geometry_and_area_multiplier1','positive_TT_interface_slacks',
            'four_whole_PT_windows_reproduced_by_ledger','gross_increment_plus_residency_identity','CIM_read_dedup','old_SEAL_bytes_preserved',
            'onecycle_II1_preserved','no55nm_price_import'])
    result['integration_code_sha256']={n:sha(HERE/n) for n in
        ('intake_sram.py','sram_characterization.py','whole_pricing.py','whole_model.py','run_whole.py')}
    dump(HERE/'SRAM_INTAKE_20261109.json',result)
    for n in ('sram_characterization.py','whole_pricing.py','whole_model.py','run_whole.py','intake_sram.py'):
        ast.parse((HERE/n).read_text(),filename=n)
    print(json.dumps(dict(status='PASS',windows=verified,probes=len(probes),
        full_conditional=[{k:r[k] for k in ('clock_MHz','area_mm2','time_ms','chip_energy_mJ','total_energy_mJ_at4pJbit')} for r in full])))

if __name__=='__main__':main()
