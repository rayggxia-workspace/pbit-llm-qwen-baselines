"""Local paired attention transaction replay; original/native results stay frozen."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,math,sys,time

def read(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_bytes((json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
def module(name,path,package=False):
    spec=importlib.util.spec_from_file_location(name,path,submodule_search_locations=[str(path.parent)] if package else None)
    obj=importlib.util.module_from_spec(spec);sys.modules[name]=obj;spec.loader.exec_module(obj);return obj

def environment(project,checkout):
    global INPUTS_FOLDER
    runtime=project/'project_archives/ffn_sram_batch204_20261106/runtime'
    deps=project/'project_archives/sampling_latency225_20261106/dependencies'
    boot=module('qk225_boot',checkout/'architecture_tlm/sampling_latency_20261106/bootstrap.py')
    identity=boot.use_runtime(runtime,deps)
    INPUTS_FOLDER=project/'tmp/attention-compare-issue198-20261027/work/rayggxia/198/attention_tlm_20261105/runtime'
    expected=read(runtime/'EXECUTION_MANIFEST.json')['files_sha256']
    for name in ('SAMPLES.json','representative.json'):
        assert sha(INPUTS_FOLDER/name)==expected['inputs/'+name],name
    identity['input_sha256']={name:sha(INPUTS_FOLDER/name) for name in ('SAMPLES.json','representative.json')}
    owner=project/'architecture_tlm/attention_resource_compaction_20261107'
    module('qk225_owner',owner/'__init__.py',True)
    owner_model=module('qk225_owner.model',owner/'model.py')
    integrate=module('qk225_integrate',checkout/'architecture_tlm/attention_candidate_20261107/integrate.py')
    actor=module('qk225_supply',Path(__file__).with_name('model.py'))
    return runtime,owner_model,integrate,actor,identity

def one(runtime,owner,integrate,actor,case,groups,seed,feedback=4,credits=4):
    from architecture_tlm.sampling_latency_20261106.model import make_model
    from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
    backend=AnalyticDRAM(latency_ns=30,bandwidth_GBs=136.4606)
    h,m=make_model(backend,gu_samples=8,wd_samples=32,mode='ising',ffn='sc',
        samples=read(INPUTS_FOLDER/'SAMPLES.json'),layers=36,include_lm=True,
        seed=seed,attention_input=read(INPUTS_FOLDER/'representative.json'))
    integrate.install(m,owner.install,'combined32')
    if case=='supply':actor.install(m,feedback_cycles=feedback,operand_credits=credits)
    counts=dict(capacity=h.mem.capacity,banks=h.mem.nbank,word=h.mem.word,period_ns=h.mem.period)
    m.phase('attention',[m.attention_group(0,g) for g in range(groups)],0)
    report=h.report()
    assert not h.mem.queue and not report['final_pending'] and not report['final_response_occupied']
    assert not getattr(m,'qk_supply_active',set())
    end=h.now
    for k,v in counts.items():
        assert v==dict(capacity=h.mem.capacity,banks=h.mem.nbank,word=h.mem.word,period_ns=h.mem.period)[k]
    return dict(case=case,groups=groups,seed=seed,feedback_cycles=feedback,
        time_us=end/1000,chip_cycles=end/10,actions=dict(m.actions),memory=report,
        SRAM=h.mem.report(end),supply_audit=getattr(m,'qk_supply_audit',[]),
        compute=dict(m.compute),contract=getattr(m,'qk_supply_contract',None),
        scope='first Attention stage only; same representative indices and analytic external latency/bandwidth',
        PPL=False,PPA=False,native_LPDDR=False)

def summarize(rows,project,checkout,runtime):
    pairs=[]
    for g in (1,8):
        for seed in (17,503,1009):
            old=next(r for r in rows if r['case']=='macro' and r['groups']==g and r['seed']==seed)
            new=next(r for r in rows if r['case']=='supply' and r['groups']==g and r['seed']==seed and r['feedback_cycles']==4)
            for key in ('attention_QK_MAC','samples','unique_V','PV_ADD','FP32_to_S12'):
                assert old['actions'].get(key,0)==new['actions'].get(key,0),(key,old['actions'].get(key),new['actions'].get(key))
            for key in ('dram_read_bytes','dram_write_bytes'):
                assert old['memory']['counts'].get(key,0)==new['memory']['counts'].get(key,0),key
            for kind,values in old['memory']['by_kind'].items():
                for key in ('issued_bytes','issued_address_sum','issued_address_xor'):
                    assert values.get(key,0)==new['memory']['by_kind'][kind].get(key,0),(kind,key)
            rr=sum(r['transpose_read_bytes'] for r in new['supply_audit'])
            ww=sum(r['transpose_write_bytes'] for r in new['supply_audit'])
            assert rr==ww==g*32768
            assert max(r['max_ready_tiles'] for r in new['supply_audit'])<=2
            s0,s1=old['SRAM'],new['SRAM']
            delta_energy=s1['dynamic_mJ']-s0['dynamic_mJ']
            pairs.append(dict(groups=g,seed=seed,old_us=old['time_us'],supply_us=new['time_us'],
                delta_us=new['time_us']-old['time_us'],delta_cycles=new['chip_cycles']-old['chip_cycles'],
                delta_percent=(new['time_us']/old['time_us']-1)*100,
                additional_read_words=s1['counts']['read_words']-s0['counts']['read_words'],
                additional_write_words=s1['counts']['write_words']-s0['counts']['write_words'],
                additional_SRAM_dynamic_mJ=delta_energy,
                external_bytes_unchanged=True,actions_unchanged=True,
                group_services=[dict(kind=r['kind'],cycles=r['duration_ns']/10,
                    ideal_issue_cycles=r['ideal_issue_cycles'],feedback_wait_cycles=r['feedback_wait_ns']/10,
                    SRAM_operand_wait_cycles=r['operand_read_wait_ns']/10,
                    tile_wait_cycles=r['ready_wait_ns']/10) for r in new['supply_audit'] if r['group']==0]))
    eight=[p for p in pairs if p['groups']==8]
    mean=lambda key:math.fsum(p[key] for p in eight)/len(eight)
    # Use the old accepted byte-holding proxy, not an unverified new PV netlist.
    inp=read(checkout/'architecture_tlm/attention_candidate_20261107/INPUTS.json')
    per_byte=inp['owner_summary']['areas']['combined32']['added_staging_proxy_mm2']/2048
    reg_area=256*8*per_byte
    old_area=inp['owner_summary']['areas']['combined32']['covered_chip_budget_mm2']
    #128B staging loaded256 times/group; 9.374pJ/64B capture is existing DMA
    #holding-event proxy. Address/mux/transpose wires remain explicit parameters.
    capture_per64=9.374488888888889
    reg_capture_mJ=(8*(32768+131072)/64)*capture_per64*1e-9
    base=read(checkout/'architecture_tlm/sampling_latency_20261106/COMPLETED_RESULTS.json')
    return dict(scope='100MHz bounded Attention replay + explicitly conditional36-layer projection',
        pairs=pairs,mean8=dict(delta_us=mean('delta_us'),additional_SRAM_dynamic_mJ=mean('additional_SRAM_dynamic_mJ')),
        whole36_projection=dict(additional_time_ms=36*mean('delta_us')/1000,
            additional_SRAM_dynamic_mJ=36*mean('additional_SRAM_dynamic_mJ'),
            transpose_register_capture_proxy_mJ=36*reg_capture_mJ,
            note='increment against old shared-supply macro only; not a new whole-token native run'),
        area=dict(previous_shared_candidate55_mm2=old_area,transpose_register55_proxy_mm2=reg_area,
            candidate55_proxy_mm2=old_area+reg_area,SRAM_KiB=1216,capacity_added_KiB=0,
            included_scratch_KiB=8,register_bytes=2048,transpose_staging_register_bytes=1024,
            coarse_operand_FIFO_bytes=1024,proxy_mm2_per_byte=per_byte,
            unpriced=['transpose wiring and address/control mux','broadcast physical fanout/CTS'],
            already_scaled_081=True),
        energy_proxies=dict(register_capture_pJ_per64B=capture_per64,
            transpose_control_pJ_per_microtile=None,broadcast_pJ_per_vector=None),
        historical_whole_results_file_sha256=sha(checkout/'architecture_tlm/sampling_latency_20261106/COMPLETED_RESULTS.json'),
        new_whole_token_native_run=False,new_RTL_PT=False,new_model_PPL=False,
        external_bandwidth_GBs=136.4606,external_latency_ns=30,external_backend='analytic proxy, not native LPDDR',
        clock_MHz=100,feedback_cycles=4,
        assumptions=['four-Q K broadcast uses the same group candidate set',
            'coarse supply has four32B credits,128B FIFO/group; separate128B transpose staging/group',
            'fine supply uses existing FMA input register to hold at most one32B response',
            'scratch49152..50176 lies inside64KiB group; coarse-score reservation ends49152',
            'same query snapshots retained; existing Q distribution macro unchanged',
            'SRAM macro pJ/event and byte-holding register area/capture proxy, not integrated PPA'])

def main():
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();checkout=Path(__file__).resolve().parents[2]
    runtime,owner,integrate,actor,identity=environment(a.project,checkout)
    a.out.mkdir(parents=True,exist_ok=False);rows=[];start=time.time()
    for groups in (1,8):
        for seed in (17,503,1009):
            for case in ('macro','supply'):
                r=one(runtime,owner,integrate,actor,case,groups,seed);rows.append(r)
                write(a.out/('%s_g%d_s%d.json'%(case,groups,seed)),r)
                print(json.dumps(dict(case=case,groups=groups,seed=seed,time_us=r['time_us'],wall_s=time.time()-start)),flush=True)
    r=one(runtime,owner,integrate,actor,'supply',8,17,feedback=8);rows.append(r);write(a.out/'supply_feedback8_g8_s17.json',r)
    minimal=one(runtime,owner,integrate,actor,'supply',8,17,credits=1)
    write(a.out/'supply_credits1_g8_s17.json',minimal)
    result=summarize(rows,a.project,checkout,runtime)
    result['feedback8_sensitivity']=dict(time_us=r['time_us'],note='latency sensitivity only, not new physical design')
    result['credits1_sensitivity']=dict(time_us=minimal['time_us'],register_bytes=1024,
        note='no coarse FIFO, existing one-vector input capture; timing/area tradeoff')
    result['identity']=identity;result['wall_seconds']=time.time()-start
    sources=[Path(__file__),Path(__file__).with_name('model.py'),a.project/'architecture_tlm/qk_supply198_100mhz_20261107/transpose_check.py',
        a.project/'architecture_tlm/qk_supply198_100mhz_20261107/LAYOUT_CHECK.json',
        a.project/'architecture_tlm/attention_resource_compaction_20261107/model.py',INPUTS_FOLDER/'representative.json',INPUTS_FOLDER/'SAMPLES.json']
    result['source_sha256']={str(f.relative_to(a.project)):sha(f) for f in sources}
    write(a.out/'SUMMARY.json',result)
    write(a.out/'SEAL.json',dict(files_sha256={f.name:sha(f) for f in a.out.glob('*.json')}))
    print(json.dumps(dict(status='completed',mean8=result['mean8'],area=result['area'])),flush=True)
if __name__=='__main__':main()
