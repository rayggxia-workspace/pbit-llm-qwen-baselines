"""Verify local replay provenance and assemble the selected6-core budget."""
from pathlib import Path
import hashlib,json,math,runpy

WD=Path(__file__).resolve().parents[2]
PROJECT=WD.parents[1]
HERE=Path(__file__).parent
WORK=WD/'work/rayggxia/225/ffn6_100mhz_20261107'
OWNER=PROJECT/'architecture_tlm/module_handoff/ffn_common_k64_m128_tx16_tz32_20261107'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_bytes((json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
def text(p,v):Path(p).write_bytes(v.encode())

def main():
    p=load(OWNER/'profile.json');old=load(WD/'architecture_tlm/attention_candidate_20261107/RESULTS.json')['candidate']
    qk=load(WD/'architecture_tlm/qk_supply_100mhz_20261107/RESULTS.json')['area']
    sources=load(OWNER/'SOURCES.json')['files']
    for r in sources:assert sha(Path(r['path']))==r['sha256'],r['path']
    rows=[];raw={};checks=['15 owner sources SHA match']
    for n in (5,6,8,12):
        folder=WORK/('replay_c%d'%n);r=load(folder/'RESULT.json');seal=load(folder/'SEAL.json')
        assert sha(folder/'RESULT.json')==seal['result_sha256']
        assert sha(HERE/'model.py')==r['source_sha256']['model.py']
        runner=HERE/'replay.py' if n==5 else WORK/'executed_sources/replay_c6_c8_c12.py'
        assert sha(runner)==r['source_sha256']['replay.py']
        assert r['status']=='completed' and r['contract']['active_cores']==n
        assert r['contract']['GU_samples']==16 and r['contract']['Wd_samples']==32
        assert r['SRAM']['capacity_bytes']==1216*1024 and r['SRAM']['physical_banks']==304
        assert not r['memory']['final_pending'] and not r['memory']['final_response_occupied']
        assert [s['frames'] for s in r['stages']]==[6080,3040]
        assert [s['peak_owned_state_groups'] for s in r['stages']]==[76,20]
        raw[n]=r
    reference=raw[12]
    for n,r in raw.items():
        assert r['physical_map']==reference['physical_map'],'no SRAM remapping/free ports'
        assert r['actions']==reference['actions'],'sample/work conservation'
        for tag,values in reference['memory']['by_kind'].items():
            for key in ('issued_bytes','issued_address_sum','issued_address_xor'):
                assert values.get(key,0)==r['memory']['by_kind'][tag].get(key,0),(n,tag,key)
        for key in ('dram_read_bytes','dram_write_bytes'):
            assert r['memory']['counts'].get(key,0)==reference['memory']['counts'].get(key,0)
        # Input-cache hit rates legitimately change with worker count.
        assert r['SRAM']['counts']['write_words']==reference['SRAM']['counts']['write_words']
        core_area=p['cost']['old_SS100_C20_area55_mm2_per_core']*n
        total=qk['candidate55_proxy_mm2']-old['areas55_mm2']['FFN_common_core']+core_area
        rows.append(dict(cores=n,GU_us=r['stages'][0]['elapsed_ns']/1000,
            Wd_us=r['stages'][1]['elapsed_ns']/1000,FFN_us=r['time_us'],
            change_vs12_percent=(r['time_us']/reference['time_us']-1)*100,
            core_area55_proxy_mm2=core_area,total_area55_proxy_mm2=total,
            SRAM_read_words=r['SRAM']['counts']['read_words'],
            GU_input_cache_loads=r['stages'][0]['input_cache_loads'],
            Wd_input_cache_loads=r['stages'][1]['input_cache_loads']))
    checks+=['four replay result/source seals match; CLI-only earlier runner preserved',
        'actual5/6/8/12 worker instances and sample16/32 contracts',
        'same1216KiB304bank physical maps', 'same MAC/sample work and external address multiset',
        'same SRAM writes; changed input-cache reads retained',
        '6080GU/3040Wd frames and76/20KiB owned-state peaks', 'finite queues drained']
    B=136.4606;tile=8192;GU_ns=180;Wd_ns=340
    minimum=math.ceil(B*Wd_ns/tile)
    assert minimum==6 and 5*tile/Wd_ns<B<6*tile/Wd_ns
    bands=[dict(cores=n,GU_weight_GBs=n*tile/GU_ns,Wd_weight_GBs=n*tile/Wd_ns) for n in (4,5,6,8,12)]
    per_frame_headroom_ns=minimum*tile/B-Wd_ns
    # Reference corpus/shape and all old run archives unchanged. The live fast
    # estimator is deliberately fixed under the separately documented P2.
    untouched={};changed={}
    for name in ('sram1216','sampling_latency','attention_candidate_20261107'):
        for path,record in load(WD/f'work/rayggxia/225/{name}/SOURCE_MANIFEST.json').items():
            if not path.startswith('architecture_tlm/'):continue
            if sha(WD/path)==record['sha256']:untouched[path]=record['sha256']
            else:changed[path]=dict(old=record['sha256'],new=sha(WD/path))
    assert list(changed)==['architecture_tlm/sampling_latency_20261106/fastsim.py']
    tt=load(WD/'work/rayggxia/225/tt250_catalog_20261107/SOURCE_MANIFEST.json')
    for path,record in tt.items():
        if path.startswith('architecture_tlm/sram1216_20261106/250MHz/'):
            assert sha(WD/path)==record['sha256']
    fast=runpy.run_path(str(WD/'architecture_tlm/sampling_latency_20261106/fastsim.py'),run_name='fast_scope_check')
    profile=load(WD/'architecture_tlm/sampling_latency_20261106/COMPLETED_CURRENT_PROFILE.json')
    assert abs(fast['estimate'](profile,64,64)['including_lm_head_ms']-profile['including_lm_head_ms'])<1e-9
    for bw in (10,100):
        try:fast['estimate'](profile,64,64,bw)
        except ValueError:pass
        else:raise AssertionError('invalid bandwidth scan')
    checks+=['minimum6 at ideal peak136.4606GB/s proved',
        '31 old100MHz artifacts unchanged; live fastsim-only P2 fix isolated',
        'six250MHz catalog files unchanged', 'fixed-bandwidth reference preserved;10/100 rejected']
    sram=load(WD/'architecture_tlm/sram1216_20261106/AREA_BREAKDOWN.json')['SRAM_attribution']
    assert sum(x['capacity_KiB'] for x in sram)==1216
    six=next(r for r in rows if r['cores']==6)
    areas=dict(old['areas55_mm2']);areas['FFN_common_core']=six['core_area55_proxy_mm2']
    areas['QK_supply_staging_and_FIFO_proxy']=qk['transpose_register55_proxy_mm2']
    assert math.isclose(math.fsum(areas.values()),six['total_area55_proxy_mm2'],abs_tol=1e-8)
    selected=dict(configuration='current100_FFN6_GU16_Wd32_sharedQK',clock_MHz=100,
        default_cores=6,fallback_cores=8,reference_cores=12,GU_samples=16,Wd_samples=32,
        GU_II_cycles=18,Wd_II_cycles=34,target_acc_bits=19,external_result_bits=20,
        crossK_bits=64,resident_weight_slots=32,result_credits_per_core=2,state_ports=2,
        GU_state_KiB=96,SRAM_KiB=1216,SRAM_4KiB_banks=304,default_factory='architecture_tlm.ffn6_100mhz_20261107.model.make_model',
        attention='current100 combined32 + actual bank QK supply',
        price='old C20 per-core proxy; new C19 PPA not measured',
        native_whole_token_replayed=False,historical_reference_changed=False,TT250_changed=False)
    save(HERE/'PROFILE.json',selected)
    out=dict(selected=selected,area55_proxy_mm2=six['total_area55_proxy_mm2'],areas55_proxy_mm2=areas,
        old12core_area55_mm2=qk['candidate55_proxy_mm2'],core_rows=rows,
        bandwidth=dict(external_peak_GBs=B,per_frame_weight_bytes=tile,GU_frame_ns=GU_ns,
            Wd_frame_ns=Wd_ns,minimum_cores_at_peak=minimum,minimum_cores_at110GBs=math.ceil(110*Wd_ns/tile),
            Wd_extra_serial_frame_budget_ns=per_frame_headroom_ns,rows=bands,
            boundary='ideal sustained weight stream; extra nonoverlapped preparation, readback and state traffic can raise requirement'),
        SRAM=dict(selected_KiB=1216,changed=False,attribution=sram,
            GU_peak_owned_KiB=76,Wd_peak_owned_KiB=20,GU_reserved_KiB=96,
            optional_future_state80_KiB=dict(capacity_saving_KiB=16,macro_area_saving55_mm2=4*.03322622205*.81,
                implemented=False,note='requires new repack/port validation; only0.108mm2,not part of this selection')),
        validation=dict(status='PASS',checks=checks),
        execution_scope='four cold full-shape FFN replays; real bank events; analytic external136.4606GB/s30ns; not native whole token',
        whole_token_time_ms=None,new_C19_PPA=False,new_PPL=False,
        source_SHA256={str(f.relative_to(PROJECT)):sha(f) for f in [OWNER/'profile.json',OWNER/'SOURCES.json',HERE/'model.py',HERE/'replay.py']},
        reviewed_fast_estimator_change=changed)
    save(HERE/'RESULTS.json',out);save(HERE/'VALIDATION.json',out['validation'])
    current=WD/'architecture_tlm/sram1216_20261106/CURRENT_100MHZ.json';save(current,selected)
    rowtext='\n'.join('|%d|%.2f|%.2f|%.2f|%.2f|%.2f|'%(r['cores'],r['GU_us'],r['Wd_us'],r['FFN_us'],r['change_vs12_percent'],r['total_area55_proxy_mm2']) for r in rows)
    srtext='\n'.join('|%s|%d|%s|'%(r['name'],r['capacity_KiB'],
        {'八组Attention局部缓冲':'QK转置8KiB已在此内；本次不改Attention',
         '普通数字权重双缓冲':'640路普通池及投影tile不变',
         'CIM权重驻留槽':'32×8KiB，维持加载重叠和原写并行',
         '激活与量化码':'由模型宽度、码/尺度元数据和残差决定',
         'FFN跨K宽状态':'GU峰值76KiB、Wd20KiB按阶段复用；非每核分配',
         '归一化参数双缓冲':'逐层预取双槽，与FFN核数无关',
         'DMA相关SRAM预留':'保留返回信用和搬运接口；24KiB实际保持另列价格'}[r['name']]) for r in sram)
    text(HERE/'README_ZH.md',f'''# 当前100MHz：FFN六核、前16／后32

2026-11-07，Issue225/PR248，用户确认先用6核。新入口本目录`model.make_model`默认6核，并组合当前100MHz共享QK/有限转置供数；8核保性能回退，12核旧对照。宿主选择索引为`architecture_tlm/sram1216_20261106/CURRENT_100MHZ.json`。旧冻结运行、原参考入口和250MHz目录不改。

## 6核是不是最小

按每帧驻留8KiB、Wd32服务34拍＝340ns，单核每秒可消费24.094GB权重。5核120.47GB/s，6核144.56GB/s，当前外存峰值136.4606GB/s。因此**6是匹配峰值的理论最小整数核数**；GU16的18拍仅需3核即可匹配，约束来自Wd。不是全系统已经持续跑到标称峰值的承诺。若有效带宽只有110GB/s，理想5核即可；若单帧有额外不能重叠的准备开销，6核仅容许约{per_frame_headroom_ns:.2f}ns，8核更宽裕。

## 实际做的本地对照

完整Qwen3-4B形状：GU6080帧、Wd3040帧，保留36层地址分配；只执行第0层冷FFN，不重跑整token。物理1216KiB/304bank/16B1RW、32权重槽、两state口/两结果信用保持，外存为136.4606GB/s、30ns解析服务，非新原生LPDDR。seed17相同工作/外存地址多重集。

|核数|GU µs|Wd µs|FFN含metadata µs|相对12核 %|整机覆盖面积代理mm²|
|---:|---:|---:|---:|---:|---:|
{rowtext}

6核没有比8/12核慢；它的输入码缓存重复装载更少。GU最大76个输出状态组、Wd20个，与核数无关。访存顺序改变会改变缓存读次数，已按实际事件保留，未强行宣称所有SRAM读量相等。5核用于检验理论下限，不能因单个局部结果直接确定所有原生调度的最小核数。四配置全部排空/逐帧及工作量、地址sum/xor检查通过，详见RESULTS。

## SRAM先保持不变

|归属|KiB|本次为何保留|
|---|---:|---|
{srtext}
|合计|1216|304颗4KiB物理宏，容量与端口未减少|

**减半计算核不等于减半权重缓冲。** 若将32槽或其写口也减半，会减少权重预取深度/装载并行，可能让6核吃不满。核内计数器、两结果槽等随核数删除，已含在每核面积中，不再从SRAM重复扣减。跨K64位状态保存的是不同输出的部分和，不是只给当前6个核各存一份。

状态区96→80KiB是未来可试的独立小优化：本轮峰值76KiB，约能省16KiB及0.108mm²；但重排物理bank会改变前端端口竞争。本轮未实施，不为这点小收益扰动刚选定的6核配置。

## 数制、面积与范围

输入16层；后级4×2×4共32格。GU除16、Wd除32，目标本地C19、GU精确18bit、Wd19bit；符号扩展回原20bit传输，跨K仍64bit。TLM仅描述合同/时间，不冒充实际模型数值或C19 RTL。C19实测PPA仍空，按旧完整C20单核价预算，GF64/SNG已含其中，不再额外加源价或全核乘0.95。

当前覆盖面积约{six['total_area55_proxy_mm2']:.2f}mm²（原12核41.56），其他Attention/640FMA/1216KiB和QK小缓冲预算不变。动态操作及权重次数不按6/12打折；减少的是复制核及背景成本，短采样活动另算。完整整token时间本轮留空，不把旧约54ms改名成6核原生结果。

复现：`python -B architecture_tlm/ffn6_100mhz_20261107/replay.py --project C:/Users/86134/Documents/a_P_BIT --cores 6 --out <新目录>`。分析为`python -B architecture_tlm/ffn6_100mhz_20261107/analyze.py`，依赖已有同SHA冻结runtime/输入/owner目录；Git仅提交小型配置、结果、源和索引。6/8/12执行时runner仅CLI choices与后来5核诊断有差别，原执行runner字节和各SEAL均已留存。无新服务器/GPU/RTL/PT或新数字电路台账run。

顺带修复PR248审核指出的旧fastsim误用：固定profile校准带宽，仅支持采样数扫描；显式改为100/10GB/s现在报错，不能让新带宽同时抵消两侧memory项。固定136.4606GB/s结果保持。核数扫描使用本目录实际worker actor，不通过修改校准profile来抵消核数代价。
''')
    text(HERE/'.gitattributes','* -text\n')
    print(json.dumps(dict(status='PASS',cores=6,area55=six['total_area55_proxy_mm2'],FFN_us=six['FFN_us'],checks=len(checks),bandwidth_min_cores=minimum)))
if __name__=='__main__':main()
