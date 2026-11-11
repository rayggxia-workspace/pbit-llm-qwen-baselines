"""Unified250MHz complete decode, with finite SRAM/DMA and native LPDDR option."""
from pathlib import Path
import argparse, collections, csv, hashlib, json, time
from bootstrap import bootstrap,sha

def save(path,value):
    Path(path).write_bytes((json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8'))

def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--runtime',type=Path,required=True);p.add_argument('--dependencies',type=Path,required=True)
    p.add_argument('--backend',choices=('analytic','native'),default='native')
    p.add_argument('--cores',type=int,choices=(2,3),default=3)
    p.add_argument('--ingress-kib',type=int,choices=(16,24),default=16)
    p.add_argument('--sram-profile',choices=('reference1216','compact1088','compact960'),default='compact960')
    p.add_argument('--seed',type=int,choices=(17,503,1009),default=17)
    p.add_argument('--scope',choices=('full','layer','prefix','ffn'),default='full')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--inputs',type=Path,help='captured inputs; defaults to runtime/inputs')
    p.add_argument('--attention-source',type=Path,help='pinned finite-supply owner execution package')
    a=p.parse_args();identity=bootstrap(a.runtime,a.dependencies,a.attention_source)
    from whole250.model import make_model
    from whole250.pricing import price
    load=lambda path:json.loads(Path(path).read_bytes())
    if a.backend=='native':
        from architecture_tlm.digital_baselines_20261104.backend import RamulatorBackend
        cfg=a.runtime/'base/profiles/derived8533.yaml'
        profile=next(x for x in load(a.runtime/'base/profiles/PROFILES.json') if x['name']=='derived8533')
        assert sha(cfg)==profile['sha256']
        binary=a.runtime/'base/liblpbridge.so'
        identity.update(memory_config_sha256=sha(cfg),bridge_sha256=sha(binary))
        backend=RamulatorBackend(binary,cfg,profile['period_ns'],256)
    else:
        from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
        backend=AnalyticDRAM(latency_ns=30,bandwidth_GBs=136.4606)
    a.out.mkdir(parents=True,exist_ok=False);started=time.time()
    try:
        inputs=a.inputs or a.runtime/'inputs'
        representative=load(inputs/'representative.json');samples=load(inputs/'SAMPLES.json')
        identity['input_sha256']={n:sha(inputs/n) for n in ('representative.json','SAMPLES.json')}
        h,m=make_model(backend,cores=a.cores,ingress_kib=a.ingress_kib,sram_profile=a.sram_profile,mode='ising',ffn='sc',samples=samples,
            layers=36,include_lm=a.scope=='full',seed=a.seed,attention_input=representative)
        if a.scope!='full':m.model['layers']=1
        class PrefixDone(Exception):pass
        phase=m.phase
        def progress(stage,generators,layer):
            value=phase(stage,generators,layer)
            print(json.dumps(dict(event='phase_completed',stage=stage,layer=layer,
                simulated_us=h.now/1000,wall_seconds=time.time()-started)),flush=True)
            if a.scope=='prefix' and stage=='O':raise PrefixDone()
            return value
        m.phase=progress
        if a.scope=='ffn':
            m.phase('GU',[m.sc_gu(0)],0);m.phase('NL_Wd',[m.sc_down(0)],0)
            result=dict(model=m.model,actions=dict(m.actions),kernel_active=dict(m.kernel_active),phases=m.phases)
        else:
            try:result=m.run()
            except PrefixDone:
                result=dict(model=m.model,actions=dict(m.actions),kernel_active=dict(m.kernel_active),phases=m.phases)
                if a.scope!='prefix':raise
        result.update(status='completed',case='unified250_GU16_Wd32_C%d'%a.cores,scope=a.scope,
            backend=a.backend,seed=a.seed,time_ns=h.now,simulated_ms=h.now/1e6,
            simulated_chip_cycles=h.now/4,clock_contract=dict(m.clock.report(),scope='whole-model overlay'),
            memory=h.report(),phases=m.phases,compute=dict(m.compute),source_identity=identity,
            resource_contract=m.resource_contract,resource_audit=m.resource_audit,
            ordinary_pool_contract=m.ordinary_pool_contract,matrix_audit=m.ordinary_pool_audit,
            unified_clock_contract=m.unified_clock_contract,compact_memory=m.compact_memory,
            short_FFN_contract=m.short_FFN_contract,common_FFN_stages=m.common_stats,
            ingress_capacity_contract=m.ingress_capacity_contract,
            whole_token=a.scope=='full',numeric_inference=False,new_PPA=False,
            explicit_front=m.explicit_front,ordinary_contract=m.ordinary_pool_contract,
            projection_supply_audit=m.ordinary_pool_audit,
            wall_seconds=time.time()-started)
        assert not h.mem.queue and not h.events
        assert not result['memory']['final_pending'] and not result['memory']['final_response_occupied']
        if a.backend=='native':
            result['native']=backend.finish(h.now)
            assert result['native']['counts']['logical64_completed']*64==sum(
                result['memory']['counts'].get(n,0) for n in ('dram_read_bytes','dram_write_bytes'))
        # Audit executed frames and exact count boundaries, independently of wall time.
        for row in m.common_stats:
            assert row['frames']==(6080 if row['mode']=='GU' else 3040)
            expected=m.short_FFN_contract['GU_frame_ns' if row['mode']=='GU' else 'Wd_frame_ns']
            assert row['sample_core_ns']==row['frames']*expected
            assert row['peak_core_reserved_results']<=2
        if a.scope in ('layer','full','ffn'):
            L=36 if a.scope=='full' else 1
            assert result['kernel_active']['GU_frames']==6080*L
            assert result['kernel_active']['Wd_M128_frames']==3040*L
            assert result['actions']['GU_logical_R8_ports']==6080*L*64*16
            assert result['actions']['NL_logical_R8_ports']==3040*L*64*3*32
        phases=collections.Counter()
        for row in m.phases:phases[row['stage']]+=row['duration_ns']
        result['phase_totals_ms']={k:v/1e6 for k,v in phases.items()}
        budget=price(result)
        config=dict(model=result['model'],scope=a.scope,cores=a.cores,seed=a.seed,
            short_FFN_contract=result['short_FFN_contract'],SRAM_profile=a.sram_profile,
            ingress_KiB=a.ingress_kib,backend=a.backend,input_sha256=identity['input_sha256'])
        result['configuration_sha256']=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        save(a.out/'RESULT.json',result);save(a.out/'BUDGET.json',budget)
        save(a.out/'ENERGY_LEDGER.json',budget['energy_ledger'])
        with (a.out/'ENERGY_LEDGER.csv').open('w',encoding='utf-8',newline='') as f:
            fields=('resource_id','area55_mm2','activity_or_service_uJ','residence_before_root_gating_uJ',
                    'root_gating_savings_uJ','residence_after_root_gating_uJ','total_uJ','billing','basis')
            writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(budget['energy_ledger']['components'])
        save(a.out/'VALIDATION.json',dict(status='PASS',energy_sum_closed=budget['energy_ledger']['numerical_sum_closed'],
            FFN_gross_idle_equivalence_checked=True,FFN_predecessor_reference_used=False,
            core_frames=dict(result['kernel_active']),frame_cycles=dict(GU=m.short_FFN_contract['GU_frame_cycles'],Wd=m.short_FFN_contract['Wd_frame_cycles']),
            configuration_sha256=result['configuration_sha256'],scope=a.scope,all_physical_costs_measured=False))
        save(a.out/'SEAL.json',dict(result_sha256=sha(a.out/'RESULT.json'),budget_sha256=sha(a.out/'BUDGET.json'),
            source_identity=identity,status='completed',configuration_sha256=result['configuration_sha256'],
            files_sha256={name:sha(a.out/name) for name in ('RESULT.json','BUDGET.json','ENERGY_LEDGER.json','ENERGY_LEDGER.csv','VALIDATION.json')}))
        print(json.dumps(dict(status='completed',scope=a.scope,cores=a.cores,ms=result['simulated_ms'],
            area55_mm2=budget['totals']['covered_area55_mm2'],energy_mJ_proxy=budget['totals']['proxy_total_mJ_at4pJ'],
            wall_seconds=time.time()-started)),flush=True)
    finally:
        if hasattr(backend,'close'):backend.close()

if __name__=='__main__':main()
