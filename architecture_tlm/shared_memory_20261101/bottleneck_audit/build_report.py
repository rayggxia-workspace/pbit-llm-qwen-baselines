"""Build the Issue227 audit from immutable result bytes; no model/EDA rerun."""
import argparse,collections,csv,hashlib,io,json,math
from pathlib import Path

def read(p): return json.loads(p.read_bytes())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def traffic(x):
    return {k:{z:v.get(z,0) for z in ('read_bytes','write_bytes','issued_bytes','issued_address_sum','issued_address_xor')} for k,v in x['memory']['by_kind'].items()}
def words(x): return {k:x['memory']['SRAM']['counts'].get(k,0) for k in ('read_words','write_words','read_physical_bytes','write_physical_bytes','logical_read_bytes','logical_write_bytes')}
def stage(x,name): return next(p for p in x['audit']['phases'] if p['stage']==name)
def aggregate_actor(p,prefix):
    c=collections.Counter();n=0
    for actor,counts in p['actors'].items():
        if actor.split(':')[0]==prefix:n+=1;c.update(counts)
    return dict(actors=n,state_sum_ns=dict(c))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--task',type=Path,required=True);a=ap.parse_args()
    out=a.task/'architecture_tlm/shared_memory_20261101/bottleneck_audit';w=a.task/'work/rayggxia/227';out.mkdir(parents=True,exist_ok=True)
    fullp=a.archive/'whole_lanesofficial_packed24/results/RESULT.json';full=read(fullp)
    assert full['status']=='completed' and full['model']['layers']==36 and len(full['phases'])==507
    assert full['kernel_active']=={'GU_frames':218880,'NL_frames':1751040}
    assert full['actions']['samples']==73728 and full['actions']['argmax_compares']==151936
    assert full['memory']['final_pending']==0 and full['memory']['final_response_occupied']==0
    assert full['simulated_chip_cycles']==6699185 and math.isclose(full['simulated_ms'],66.99185)
    wp=sum(v.get('read_bytes',0) for k,v in full['memory']['by_kind'].items() if k.endswith('_weights'))
    assert wp==5354946560
    totals=collections.Counter();layers=[]
    for layer in range(36):
        pp=[p for p in full['phases'] if p['layer']==layer];assert len(pp)==14
        r={'layer':layer,'total_ms':sum(p['duration_ns'] for p in pp)/1e6}
        for name in ('QKV','attention','O','GU','NL_Wd'):
            vals=[p for p in pp if p['stage']==name];assert len(vals)==1
            r[name+'_ms']=vals[0]['duration_ns']/1e6;totals[name]+=r[name+'_ms']
        r['other_ms']=r['total_ms']-sum(r[n+'_ms'] for n in ('QKV','attention','O','GU','NL_Wd'));totals['other']+=r['other_ms'];layers.append(r)
    lm=next(p['duration_ns']/1e6 for p in full['phases'] if p['stage']=='lm_head')
    assert math.isclose(sum(r['total_ms'] for r in layers)+lm+0.00070,full['simulated_ms'],abs_tol=1e-9)
    sio=io.StringIO(newline='');cw=csv.DictWriter(sio,fieldnames=list(layers[0]),lineterminator='\n');cw.writeheader();cw.writerows(layers);(out/'LAYER_TIMES.csv').write_text(sio.getvalue(),encoding='utf-8',newline='\n')
    cases={p.parent.name:read(p) for p in (a.archive/'bottleneck_audit/results').glob('*/RESULT.json')};assert len(cases)==11
    assert all(x['status']=='completed' for x in cases.values())
    base=cases['baseline'];pilot=read(a.archive/'lanesofficial_packed24/results/RESULT.json')
    for field in ('phases','actions','kernel_active','compute_macro_busy_sum_ns','work_spec_sha256','memory','DRAM'):
        assert base[field]==pilot[field],('instrumentation altered baseline',field)
    sweep=[];sources=[]
    for name,x in sorted(cases.items()):
        rp=a.archive/'bottleneck_audit/results'/name/'RESULT.json';sources.append(dict(case=name,path=str(rp),sha256=sha(rp),bytes=rp.stat().st_size))
        assert x['memory']['final_pending']==0 and x['memory']['final_response_occupied']==0
        for phase in x['audit']['phases']:
            assert phase['elapsed_ns']>=0
            for actor,c in phase['actors'].items():assert sum(c.values())<=phase['elapsed_ns']+1e-5,(name,actor)
        if name in ('scene3','lm_prefix'):continue
        assert x['actions']==base['actions'] and x['kernel_active']==base['kernel_active']
        assert traffic(x)==traffic(base),(name,'different external work/addresses')
        if name!='return_bypass':assert words(x)==words(base),(name,'different SRAM word counts')
        sweep.append(dict(case=name,time_us=x['simulated_ms']*1000,improvement_percent=(1-x['simulated_ms']/base['simulated_ms'])*100,
            resources=x['actual_resources'],phases_us={p['stage']:p['elapsed_ns']/1000 for p in x['audit']['phases']},
            identical_actions_and_address_traffic=True,sram_words=words(x)))
    for layer in range(3):assert len([p for p in cases['scene3']['audit']['phases'] if p['layer']==layer])==14
    drivers=[]
    for phase in base['audit']['phases']:
        name=phase['stage']
        if name not in ('QKV','attention','O','GU','NL_Wd'):continue
        rec=dict(stage=name,elapsed_us=phase['elapsed_ns']/1000,compute=phase['compute_delta'],kernels=phase['kernels_delta'],metrics=phase['metrics'],actors=phase['actors'])
        prefix='digital' if name in ('QKV','O') else 'GU' if name=='GU' else 'NL' if name=='NL_Wd' else 'Attention'
        rec.update(aggregate_actor(phase,prefix))
        capacity=(16 if name=='GU' else 256 if name=='NL_Wd' else 8 if name=='attention' else 1)*phase['elapsed_ns']
        rec['state_capacity_fraction']={k:v/capacity for k,v in rec['state_sum_ns'].items()}
        if name in ('QKV','O'):rec['MAC_work_over_nominal_capacity']=phase['compute_delta']['ordinary_MAC_ideal_ns']/phase['elapsed_ns']
        drivers.append(rec)
    tests=dict(unchanged_baseline_exact=True,all_nine_matched_runs_same_actions_and_external_addresses=True,
        SRAM_word_counts_same_except_intended_return_bypass=True,all_11_results_completed_and_queues_drained=True,
        all_36_layers_14_phases=True,GU_frames=218880,NL_frames=1751040,samples=73728,argmax=151936,
        weight_bytes=wp,unit_tests=28,unit_test_scope='3 observational-audit +25 prior mechanism/clock/DMA tests; no new PPL or physical STA')
    submission=read(w/'BOTTLENECK_SUBMISSION.json');collect=read(w/'BOTTLENECK_COLLECT.json')
    assert not collect['queue'] and not collect['failed_logs']
    payload=dict(status='completed',scope='B1 Qwen3-4B shapes /2K/r32/k128/S64/chip100/8chDDR4-1866/8MiB; representative address replay, not numerical inference',
        full=dict(path=str(fullp),sha256=sha(fullp),time_ms=full['simulated_ms'],cycles=full['simulated_chip_cycles'],blocks_ms=sum(r['total_ms'] for r in layers),lm_head_ms=lm,phase_totals_ms=dict(totals),
            min_layer_ms=min(r['total_ms'] for r in layers),max_layer_ms=max(r['total_ms'] for r in layers)),
        source=dict(job=submission['job'],root=submission['root'],source_archive_sha256=submission['source_archive_sha256'],config_sha256=submission['config_sha256'],input_sha256=submission['input_sha256'],binary_sha256=submission['binary_sha256']),
        tests=tests,cases=sweep,driver_accounting=drivers,scene3_phases=[dict(layer=p['layer'],stage=p['stage'],elapsed_us=p['elapsed_ns']/1000) for p in cases['scene3']['audit']['phases']],
        cold_lm_prefix=dict(outputs=4096,time_us=cases['lm_prefix']['simulated_ms']*1000,phase=cases['lm_prefix']['audit']['phases'][0]),sources=sources,
        accounting_rule='Actor blocked states include overlapped arithmetic; ideal work/nominal capacity is not measured switching. Concurrent core sums and parent Attention/child QK durations must not be added to wall time. No-DDR-demand is not DRAM bus idle.')
    put(out/'RESULTS.json',payload)
    # Preserve the already produced full receipt; it is a summary, not raw simulation.
    fullverified=read(out/'FULL_VERIFIED.json');assert fullverified['source_result_sha256']==sha(fullp)
    put(out/'VALIDATION.json',tests)
    put(out/'RAW_RESULT_INDEX.json',dict(full=payload['full'],source=payload['source'],sources=sources,large_artifacts='retained on existing personal server/local project_archives; private input and module_handoff not published'))
    # Transparent tables: full-model timing comes from the full run, waits from
    # layer0 and all3 representative scenes, not claimed as per-core36-layer tracing.
    lines=['# 当前TLM逐层瓶颈与等待审计（Issue227，2026-11-01）','',
    '**还有同类问题，而且已经用对照运行确认。当前应优先优化供数路径和任务分配，继续堆MAC不是首选。**','',
    '此前优化分别检查了总字节、名义带宽或局部核时延，没有连续核对“请求发出→返回缓冲→目标SRAM→操作数读取→计算”。接口等待统计不足是这次漏查的原因；不能以“已有模拟器”推定调度已经最优。','',
    '## 1. 本次实际完成了什么','',
    f'- 完整36层＋lm_head实跑：**{full["simulated_ms"]:.6f} ms/token，{full["simulated_chip_cycles"]:,}个100MHz片上周期**；Slurm3673。36层合计57.012840ms，逐层1.569520–1.601080ms；507相位、工作量和末尾队列排空核验通过。',
    '- 另以Slurm数组3688完成11个CPU审计任务：9个同工作量单层资源配置、三场景连续3层、完整地址布局下冷启动lm_head前4096输出。没有GPU训练、数值PPL或新EDA。',
    '- 3项新增观测回归＋原25项机制检查通过；观测器与未加观测的原单层逐字段完全一致。完整36层统计时间，等待状态展开范围为单层及3场景，不能写成36层每个核都做过逐状态跟踪。',
    '- 固定B1、Qwen3-4B后训练模型形状、2K上下文、SparQ r32/k128、每query64个V样本、现有GU/NL核66拍服务合同、8MiB/512bank SRAM、8通道DDR4-1866名义119.424GB/s。采样参数沿既有交接，本次未调整。','',
    '## 2. 总览：各模块到底卡在哪里','',
    '|模块|36层累计，ms|占整token|单层/单次参考|判定与依据|','|---|---:|---:|---|---|']
    descriptions={
      'QKV':('约400µs','供数为主。单层MAC理想76.8µs，占额定计算容量19.1%；驱动380.57µs处在操作数读取区间，部分与算术重叠。'),
      'attention':('约107µs','粗QK计算/读入与筛选宏为主；采样＋V路径仍有排队。不是统一外存带宽耗尽。'),
      'O':('约266µs','供数为主。MAC理想51.2µs，容量占用19.2%；264.17µs落在操作数读取区间。'),
      'GU':('约477µs','权重装入与采样计算混合。16核额定容量中52.6%是核服务，37.4%等待当前tile就绪。'),
      'NL_Wd':('约326µs','突发装载、重复读码、任务尾批。256核只分到320个输出任务，第二批只有64个。'),
      'other':('约6µs','Norm、RoPE、残差、gather及相位边界；当前总占比较小。')}
    for name in ('QKV','attention','O','GU','NL_Wd','other'):
        t=totals[name];d=descriptions[name];lines.append(f'|{name}|{t:.6f}|{100*t/full["simulated_ms"]:.2f}%|{d[0]}|{d[1]}|')
    lines += [f'|lm_head|{lm:.6f}|{100*lm/full["simulated_ms"]:.2f}%|末端一次|同一数字矩阵供数路径；理想1.8992ms，实际9.97831ms。不可漏算词表层。|','',
    '上表other只含36个block；embedding及final norm另0.000700ms，合计66.991850ms。每个block的精确值见末表和LAYER_TIMES.csv。','',
    '## 3. 等待的具体位置','',
    '**QKV、O和lm_head：** 当前数字阵列2048 MAC/拍，2048个BF16权重/拍需要4096B/拍；单个operand缓冲只跨128个128bit 1RW bank，最多2048B/拍。算术峰值与局部读口先天不匹配。再加返回FIFO写/读、目标填充和操作数读取共用物理bank，QKV的31.45728MB操作数理想独占端口读153.6µs，实际读380.57µs。数字MAC翻倍没有缩短时间；减少为512路才开始略慢。MAC不是此配置下的首要缺口。',
    '',
    'QKV完整阶段401.92µs中，外存存在在途请求约292.30µs；约109.62µs既无在途请求也无待发描述符。O对应194.67/71.98µs。这证明前端并未持续给DRAM供工作；“外存名义119GB/s”不能自动等于每一阶段119GB/s。上述计时是端点需求状态，不能冒充DDR数据总线利用率。独立冷启动lm_head前4096输出268.96µs，其中读取251.89µs、初始就绪等待12.54µs、argmax4.48µs，与该判断一致，但没有把4096输出的等待直接乘成完整词表。','',
    '**GU：** 6080核帧/层×660ns，总核服务4.0128核·ms；16核与476.75µs阶段形成7.628核·ms容量。核服务52.6%、就绪等待37.4%、x码读取2.5%、跨K相加4.0%，其余包括编码、启动和尾批。该权重阶段已发49.545216MB，约103.92GB/s，接近DDR可交付能力。不能承诺只加GU核就线性提速；可先研究更早的有限tile预取、输出任务均衡及小规模增加核数的配对扫描。','',
    '**非线性＋Wd：** 一层48640帧，256核时核服务占额定容量37.7%、就绪等待33.3%、码读取4.0%，还有启动/尾批等未分配容量。320个输出8通道任务固定分两波，第二波只用64/256核；160核同样只需两波，且两波都满。实际160核将就绪等待总量从28.418核·ms降到1.596核·ms，阶段332.89→239.85µs；核帧和数学动作完全没减。这是已有资源摆放/装载竞争问题，不是算法工作量突然变少。每帧读取128B g/u码，320个输出任务重复读同一组约19KiB码，逻辑读达到6.22592MB/层；可做片区广播/只读本地复用。固定权重尺度元数据还存在逐小帧读取，适合按64×64 tile锁存复用；这些优化均需要登记真实新增电路成本。','',
    '**Attention：** 每个KV组4个query头，8组并行。粗QK每组32维×2048位置×4头，64MAC/拍的理想计算40.96µs，16个8KiB块的流水排空再约2.24µs，实际约43.89µs；选后精确QK约11.25µs。feature top-k1.64µs、SparQ normalize17.30µs、token top-k8.15µs是现有明确宏合同，尚未做完整RTL吞吐标定，三者合计27.09µs，不应当算成外存等待。最终采样/V部分约数至十余µs，地址队列、唯一V缓存、SRAM读口、加法反馈均有事件级约束。当前泛化的sampler_V_pipeline标签还含早期直接DMA等待，因此不能把其全部时长直接叫Ising采样时间；源码/观测JSON保留具体边界。','',
    'V读取已经按实际唯一地址合并，不是先读全部V；4头采样时间仍按交接串接，V消费可并行。后续可单独比较“4头同时采样”的有限资源版本，但必须保留合格p-bit供给、V队列/反馈，不应免费改成同时完成。','',
    '**阶段与层边界：** 当前执行器在阶段结束等待未完成的访存，存在GU全部输出完成后才启动NL/Wd的屏障。已有前两tile和下一层QKV等预取，却没有完整的GU→非线性→Wd tile流水。GU期间预取部分down权重值得试，但要计有限驻留容量以及与GU抢外存；当前GU已约104GB/s，不能把预取视为零竞争。跨层也必须等残差/Norm依赖，36层不可能直接全并行。','',
    '## 4. 实际资源消融（同一单层，非整机预测）','',
    '|只改变的条件|单层µs|比基线缩短|结果解释|','|---|---:|---:|---|']
    explanations={
      'baseline':('当前配置','参照'),
      'mac4096':('MAC2048→4096','0收益，供数限制'),
      'mac512':('MAC2048→512','少到一定程度才开始计算受限'),
      'credit512':('在途256→512，返回容量32→64KiB','小幅改善，不能解释全部等待'),
      'credit1024':('在途256→1024，返回容量32→128KiB','仍只有小幅改善'),
      'nl160':('NL核256→160','阶段更均衡，单层快5.85%，非线性/Wd快27.95%'),
      'vector128':('向量区64→128bank，容量不增','Wd变快、GU变慢，整层几乎抵消'),
      'fabric2x':('共享fabric配额320→640 word/拍','基本无收益；512个1RW bank仍是物理上限，不能真的同时授予640'),
      'return_bypass':('回传经有界弹性入口直接写目标，省SRAM FIFO写读','数字投影显著改善；弹性入口/路由未完成PPA标定，不是免费硬件')}
    for name in ('baseline','mac4096','mac512','credit512','credit1024','nl160','vector128','fabric2x','return_bypass'):
        r=next(c for c in sweep if c['case']==name);e=explanations[name];lines.append(f'|{e[0]}|{r["time_us"]:.2f}|{r["improvement_percent"]:+.2f}%|{e[1]}|')
    lines += ['',
    '9组算术/采样/核帧、外存各类读写字节及地址指纹完全一致；除有意省去FIFO写读的bypass外，SRAM物理读写word总数也相同，争用计数/时间可不同。三场景连续运行4.748680ms，逐层仍呈相同瓶颈类别。各个对照收益不能相加；没有把最优单层乘36冒充新完整token。','',
    '## 5. 尚未闭合、可能让当前结果偏乐观的地方','',
    '1. 这个shared后端并没有重新调用完整随机源服务TLM：FFN沿已测核服务并登记R8逻辑需求，Attention沿交接采样事件；本地PRNG充足属于接口假设。不能据R8计数宣布真实随机源吞吐、反馈广播或功耗已经包含。',
    '2. 普通2048路数字矩阵阵列、共享非线性/格式转换/TopK/normalize的完整队列及STA没有全部标定；有限SRAM/DMA已展开，若宏内部共享更少的单元，时间还会增加。当前不是所有模块都已电路闭合。',
    '3. 当前只有chip100和legacy_mixed实现，QK/PV仍含10ns、140ns、70ns等合同值。500MHz/256GB/s必须逐接口转换：保持周期数意味着改ns并校验端口与在途深度；不能只改时钟标签。现有SRAM库也不能直接当成500MHz宏。此前25–35ms只是假设预测，不是本次实跑结果。',
    '4. DMA弹性入口、控制/互连、全局时钟与DDR PHY的能量/面积仍有未标定项。本次只做等待/资源审计，不发布新的全芯片PPA，更没有新的PPL。','',
    '## 6. 下一步优先顺序','',
    '1. 先组合验证160个NL核＋有限直接返回路径＋按片区码复用，重新跑3场景及完整36层；先修供数不先堆MAC。',
    '2. 对数字矩阵采用流式operand供给/更早的双缓冲补货，并检查每核实际读口；再看1024/2048 MAC是否足够。',
    '3. 独立扫描GU核数和有限GU→Wd流水；对QK64MAC/组、筛选宏/4头采样分别做资源消融，避免只看总Attention时间。',
    '4. 把当前观测器保留为常规输出：实际发出带宽、需求空窗、每核tile就绪等待、码读/权重读和尾批负载。接口供数审计与总能量表一起更新，防止同一问题再次被名义峰值掩盖。','',
    '## 7. 36层逐层结果（ms；等待性质由展开样本＋相同实现判断）','',
    '|层（从0计）|QKV|Attention|O|GU|NL/Wd|其他|合计|','|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in layers:lines.append('|'+str(r['layer'])+'|'+'|'.join(f'{r[k]:.5f}' for k in ('QKV_ms','attention_ms','O_ms','GU_ms','NL_Wd_ms','other_ms','total_ms'))+'|')
    lines += ['',
    '## 8. 可追溯入口','',
    '- 同目录RESULTS.json：真实消融、driver状态、3场景、lm前缀；FULL_VERIFIED.json：完整run验收；VALIDATION.json；RAW_RESULT_INDEX.json：原件位置、字节SHA。',
    '- 正式执行实现architecture_tlm/unified_v6/shared_decode.py、shared_memory.py；新增shared_audit.py只观察等待、audit_decode.py设置有限对照资源、test_shared_audit.py验证零时序扰动。',
    '- 完整run source15f6d5ca8ff2e5950778016dc57bfd1e71a99c17ef244d54c371531d3d571ae5；RESULT '+sha(fullp)+'。',
    '- 审计source '+submission['source_archive_sha256']+'；input '+submission['input_sha256']+'；DDR config '+submission['config_sha256']+'；bridge '+submission['binary_sha256']+'。',
    '- 私有交接/代表输入保留既有授权存储，不复制上传；Git保存通用源代码、汇总及SHA索引。实际发布状态见work/rayggxia/227/BOTTLENECK_PUBLICATION.json。PR228待审未合并，Issue227继续保留后续优化项。','']
    (out/'REPORT_ZH.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    print(json.dumps(dict(full_ms=full['simulated_ms'],audit_cases=len(cases),matched_cases=len(sweep),validation='PASS',output=str(out)),ensure_ascii=False))

if __name__=='__main__':main()
