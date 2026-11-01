"""Reconcile sealed execution outputs without changing their original bytes."""
from pathlib import Path
import hashlib,json,math,argparse

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def main(root,workspace):
    out=root/'architecture_tlm/shared_memory_20261101';archive=workspace/'project_archives/shared_memory227_20261101';work=root/'work/rayggxia/227'
    summaries={};evidence=[];jobs=[];raw_results={}
    for receipt in sorted(work.glob('*_SUBMISSION.json')):
        d=load(receipt);phase=d['phase'];p=archive/phase/'results/RESULT.json'
        rec=dict(phase=phase,job=d['job'],remote_root=d['root'],source_archive_sha256=d['source_sha256'],
            binary_sha256=d['binary_sha256'],config_sha256=d['config_sha256'],input_sha256=(d.get('input_identity') or {}).get('sha256'),
            status='submitted_not_sealed_locally',files_sha256=d['manifest']['files_sha256'])
        if p.exists():
            log=next((archive/phase).glob('slurm-*.log'));assert '"status": "completed"' in log.read_text(),phase
            r=load(p);raw_results[phase]=r;rec['status']='completed_sealed';rec['result_sha256']=sha(p)
            m=r['memory'];sr=m['SRAM'];t=r['simulated_ms']
            assert m['final_pending']==m['final_response_occupied']==0
            assert m['counts']['descriptors']==m['counts']['descriptors_completed']
            assert m['counts']['peak_outstanding']<=m['global_credit']
            assert m['counts']['peak_response_bytes']<=m['response_bytes']
            assert sr['allocated_bytes']<=sr['capacity_bytes']
            summaries[phase]=dict(elapsed_ms=t,DRAM_core_mJ=r['DRAM']['core_total_mJ'],
                DRAM_command_mJ=r['DRAM']['command_component_mJ'],DRAM_background_refresh_mJ=r['DRAM']['background_refresh_other_mJ'],
                DRAM_ACT_mJ=r['DRAM']['components_mJ']['ACT'],
                SRAM_dynamic_mJ=sr['dynamic_mJ'],SRAM_leakage_mJ=sr['leakage_mJ'],SRAM_total_mJ=sr['dynamic_mJ']+sr['leakage_mJ'],
                DRAM_read_bytes=m['counts']['dram_read_bytes'],DRAM_write_bytes=m['counts']['dram_write_bytes'],
                SRAM_read_bytes=sr['counts']['read_physical_bytes'],SRAM_write_bytes=sr['counts']['write_physical_bytes'],
                effective_DRAM_GBs=(m['counts']['dram_read_bytes']+m['counts']['dram_write_bytes'])/t/1e6,
                phases_ms={row['stage']:row['duration_ns']*1e-6 for row in r['phases']},
                action_counts=r['actions'],kernel_frames=r['kernel_active'],wall_seconds=r['wall_seconds'])
            evidence.append(dict(phase=phase,path=str(p),sha256=sha(p),bytes=p.stat().st_size))
        jobs.append(rec)
    comparisons={}
    for other in ('serial_v2','staged_v2','no_prefetch_v2','official_v2'):
        if other in raw_results and 'single_v2' in raw_results:
            a=raw_results['single_v2'];b=raw_results[other]
            assert a['memory']['by_kind']==b['memory']['by_kind'],other
            keys=set(a['actions'])|set(b['actions'])
            assert all(a['actions'].get(k,0)==b['actions'].get(k,0) for k in keys-{'ordinary_prefetch_hits','GU_prefetch_hits'}),other
            comparisons[other]=dict(same_external_addresses_counts=True,same_arithmetic_and_sampler_work=True,
                async_direct_time_reduction_percent=100*(1-a['simulated_ms']/b['simulated_ms']),
                async_direct_SRAM_reduction_percent=100*(1-summaries['single_v2']['SRAM_total_mJ']/summaries[other]['SRAM_total_mJ']))
    if 'official_v2' in raw_results:
        a=raw_results['single_v2'];b=raw_results['official_v2']
        assert a['simulated_ms']==b['simulated_ms'] and a['memory']==b['memory']
        comparisons['power_only']=dict(time_and_all_SRAM_events_identical=True,
            original_mJ=a['DRAM']['core_total_mJ'],official_mJ=b['DRAM']['core_total_mJ'],
            reduction_percent=100*(1-b['DRAM']['core_total_mJ']/a['DRAM']['core_total_mJ']))
    v3=('official_v3','serialofficial_v3','stagedofficial_v3')
    if all(k in raw_results for k in v3):
        a=raw_results[v3[0]]
        for k in v3[1:]:
            b=raw_results[k];assert a['memory']['by_kind']==b['memory']['by_kind'] and a['actions']==b['actions']
            comparisons[k]=dict(same_external_addresses_counts=True,same_arithmetic_and_sampler_work=True,
                async_direct_time_reduction_percent=100*(1-a['simulated_ms']/b['simulated_ms']),
                async_direct_SRAM_reduction_percent=100*(1-summaries[v3[0]]['SRAM_total_mJ']/summaries[k]['SRAM_total_mJ']))
    # Vendor memspec is public; frozen local file identity is recorded even
    # though this installed vendor directory no longer has Git metadata.
    power=dict(original_prestby_W=128*(1.2*.044+2.5*.003),original_active_W=128*(1.2*.061+2.5*.003),
        official_prestby_W=128*1.2*.03375,official_active_W=128*1.2*.0395,
        official_source_sha256='3fcfb7f38f37f0e75b0b6e194fe823e22e3e994e88aef37ca70d43413dc6a380',
        timings_only_unchanged=True,devices=128,capacity_GiB=64,rank_bit=35,
        one_rank_capacity_GiB=32,one_rank_official_prestby_W=64*1.2*.03375,
        source_url='https://github.com/tukl-msd/DRAMSys/blob/master/configs/memspec/MICRON_4Gb_DDR4-1866_8bit_A.json',
        status='default_NoPowerDown_core_only; PHY/VDDQ excluded; low-power currents not validated')
    result=dict(scope='shared-address TLM, not numerical model inference or new EDA',model='Qwen/Qwen3-4B post-trained shape',
        model_revision='1cfa9a7208912126459214e8b04321603b3df60c',model_weights_loaded=False,
        scoring_dataset='N/A no PPL or task score; representative private candidate/address events from prior Issue198',
        seed17_results=summaries,paired_checks=comparisons,DDR_power_parameter_audit=power,
        evidence=evidence,job_index=jobs,
        limitations=['one seed single-layer conclusions only unless whole trace explicitly completed',
            '3 representative input scenes repeat by layer%3; not a new36-layer numeric capture',
            'K128/S64 traffic contract differs from K256 training; no quality inheritance',
            'digital500MHz/2048MAC per cycle remains a resource/latency contract, not500MHz STA signoff',
            'unpriced RNG, interconnect, ingress/control holdings, cross-K/encoding physical costs; no full-chip PPA claim',
            'DRAM initiator8bursts/10ns=51.2GB/s, bridge1ns/request=64GB/s ceiling, DDR119.4GB/s peak not achieved by assumption',
            'full parallel custom CIM readout is not ordinary SRAM read per sample',
            'original negative ACT parameter experiments retained only for timing comparisons and power-audit history'])
    write(out/'results/RESULTS.json',result)
    write(work/'EXECUTION_INDEX.json',jobs)
    lines=['# 共享存储调度与能耗核查（Issue227）','','**结论：共享端口/全局DMA额度已经落到同一事件时间线；片上存储主要要减搬运次数，DRAM则确实发现电流表不一致，需要修正。当前结果是存储与算子宏合同下的回放，不是芯片实测。**','','## 已完成的共享调度','',
        '同一DRAMSys控制器承接QKV/O/lm_head、GU、非线性-Wd及8个KV组；全局64个在途请求、8KiB返回FIFO和8burst/10ns发射口只实例化一次。128bit单端口SRAM按bank逐拍释放，不再把一个完整向量/描述符当作独占。双缓冲权重只在使用完后覆盖；采样期间权重驻留，不每次从普通窄口重读整组。','',
        '已有异步控制器/FR-FCFS继续由DRAMSys处理。本轮增加的是加速器DMA调度、真实返回/回压、物理bank归属、跨Attention→O、O→GU、Wd→下一层QKV的预取。参考[Gemmini的独立load/store/execute与DMA](https://github.com/ucb-bar/gemmini#dma)和[ONNXim按端口请求/返回队列](https://github.com/PSAL-POSTECH/ONNXim/blob/master/src/Simulator.cc)。','',
        '补齐的最新v3还显式执行DMA写回前的源SRAM读取（8×64B有界保持槽）、每tile权重尺度元数据读取、x编码输入读取、K/V append源、sampler分数读取。GU/NL部分和留在核内，跨K累计状态另列未知PPA；没有把采样比特流或整词表logits存入SRAM。','',
        '8MiB/512bank/100MHz保持容量不变，返回FIFO从16bank分散到128个现有bank；也检查每bank16KiB物理容量，未增加多端口。16bank的25.6GB/s读写合计导致返回数据先写后读只能约12.8GB/s。所有8MiB漏电/面积都计入，尚未用到的空间也不免费。','',
        '服务量子16保留连续地址，避免每64B轮换破坏行局部性。早期小探针的纯RR1反而慢约9%；负结果保留，不能将“更并行”直接写成“必然更快”。','','## 可比较的单层结果','',
        '下表同Qwen3-4B B1/2K形状，含embedding与一层完整依赖，不含lm_head；GU16/NL256、T64已测100MHz核，普通矩阵2048MAC/周期500MHz宏，Attention K128/S64、8KV组。外部读128.70MB/写69.63KB；同地址校验见RESULTS.json。','',
        '| v2对照 | 时间 ms | SRAM mJ | DRAM core mJ | 用途 |','|---|---:|---:|---:|---|']
    labels={'serial_v2':('整描述符返回屏障','旧电流表，仅调度对照'),'staged_v2':('异步＋额外staging','旧电流表，仅搬运对照'),
        'no_prefetch_v2':('异步，关闭跨阶段预取','旧电流表，仅预取对照'),'single_v2':('异步＋直接填充＋预取','旧电流表，仅调度对照'),
        'official_v2':('同一异步轨迹＋官方电流','仅改电流，时序/访问完全一致'),'w8_v2':('数字W8 FFN，Attention相同','非质量匹配，只隔离FFN实现')}
    for name,(label,note) in labels.items():
        if name in summaries:
            r=summaries[name];lines.append(f'| {label} | {r["elapsed_ms"]:.6f} | {r["SRAM_total_mJ"]:.6f} | {r["DRAM_core_mJ"]:.6f} | {note} |')
    if 'serial_v2' in comparisons:
        c=comparisons['serial_v2'];cs=comparisons['staged_v2'];cp=comparisons['no_prefetch_v2']
        lines+=['',f'相对整描述符屏障，同资源异步时间减少{c["async_direct_time_reduction_percent"]:.2f}%；相对额外staging，时间减少{cs["async_direct_time_reduction_percent"]:.2f}%、SRAM总能量减少{cs["async_direct_SRAM_reduction_percent"]:.2f}%。跨阶段预取本身仅减少{cp["async_direct_time_reduction_percent"]:.2f}%时间，主收益不是“预取”这个名称，而是消除串行屏障和重复拷贝。',
            '', '数字W8对照更快的事实保留；不能把容量/频率/精度不同的核对照转述为随机计算全面胜出。v2缺失的少量元数据/写回源访问已在v3补齐，不能将v2结果标成最新源码的完整验收。']
    lines+=['','### 最新v3与整模型执行状态','','v3已补齐元数据/写回源访问，统一使用官方电流表。下面是当前交付源码对应的配对，不与v2混算。','','| 配置 | Slurm | 状态 | 单层/整机时间ms | SRAM mJ | DRAM core mJ |','|---|---:|---|---:|---:|---:|']
    for j in jobs:
        if j['phase'].endswith('v3'):
            r=summaries.get(j['phase']);lines.append(f'| {j["phase"]} | {j["job"]} | {j["status"]} | {r["elapsed_ms"]:.6f} | {r["SRAM_total_mJ"]:.6f} | {r["DRAM_core_mJ"]:.6f} |' if r else f'| {j["phase"]} | {j["job"]} | 已提交，尚未封存 | — | — | — |')
    if all(k in comparisons for k in ['serialofficial_v3','stagedofficial_v3']):
        c=comparisons['serialofficial_v3'];s=comparisons['stagedofficial_v3']
        lines+=['',f'最新配对：相对串行屏障，异步直接填充时间减少{c["async_direct_time_reduction_percent"]:.2f}%；相对额外staging，时间减少{s["async_direct_time_reduction_percent"]:.2f}%、SRAM能量减少{s["async_direct_SRAM_reduction_percent"]:.2f}%。访问地址、算术/采样工作量一致，结果检查通过。']
    lines+=['','36层含lm_head作业使用同一全局时间线，不能直接把单层时间乘36作为完整结果。按单层实跑约4分钟CPU墙钟估计，完整回放约2–3小时；Slurm上限6小时，未申请GPU。结果生成/源码manifest、配置和输入SHA一起封存后再验收。','','## 存储能耗是否正常','',
        'SRAM单价未发现量纲错误：本库SS下每16B读10.0527pJ、写13.9599pJ，即0.6283/0.8725pJ/B；与[Horowitz原文Fig1.1.9](https://gwern.net/doc/cs/hardware/2014-horowitz-2.pdf)不同条件下8KiB/64bit约10pJ的量级不矛盾。不同节点/容量/PVT不能据此硬校准，本工艺库结果继续优先。旧21.304mJ可复算，其中响应缓冲约8.055mJ、数字本地缓冲约5.683mJ、共享SRAM约5.191mJ、CIM装载约2.375mJ。详细分项见[旧账复算](results/STORAGE_ENERGY_AUDIT_ZH.md)。','',
        '原DDR4 JSON同名Micron memoryId却覆盖了官方电流：例如IDD2N 44mA对官方33.75mA、IDD3N 61mA对39.5mA，IPP背景也不同，原ACT出现负值。已从已安装官方memspec读取原字节SHA并与[公开同型号表](https://github.com/tukl-msd/DRAMSys/blob/master/configs/memspec/MICRON_4Gb_DDR4-1866_8bit_A.json)核对；只替换mempowerspec，架构、时序和控制器保持。这个修正不会改善速度。','']
    if 'power_only' in comparisons:
        c=comparisons['power_only'];lines+=[f'同一5.462633ms/同地址/同SRAM事件的实际配对：DRAM核心总能量{c["original_mJ"]:.6f}→{c["official_mJ"]:.6f}mJ（减少{c["reduction_percent"]:.2f}%）；ACT −0.143175→+3.934063mJ，背景＋刷新47.337389→34.287722mJ。说明不能只修负ACT后机械宣布省很多：背景、激活、刷新和读命令都一起改变。','']
    lines+=['八通道/两rank/每rank八颗4Gb x8，合128颗、64GiB。官方表下预充待机下界5.184W，激活待机6.0672W；因此毫秒级运行的DRAM背景不能拿50mW代替。全局只计一次背景，不把每组Attention的整设备总能量重复相加。DRAMPower是命令＋状态＋所选电流表的估算，见[官方实现](https://github.com/tukl-msd/DRAMPower)。','',
        '当前所有模型地址低于rank位35（32GiB）；第二rank只有背景/刷新，没有数据访问。可以另做单rank32GiB对照，官方预充待机下界2.592W；这是减少实际器件数量的硬件选择，需要新配置/刷新回放，不把尚未运行的减半写成实测收益。低功耗策略、PHY/VDDQ及板级费用仍未闭合。','',
        '结论不是SRAM“天然贵得离谱”。当前主要改进方向是少一次完整拷贝、合理的bank映射、短时间结束以少交背景、匹配容量/通道的DRAM配置。官方电流表是可追溯起点，仍不等于板卡测量；公开表部分低功耗IPP值也需另核，当前NoPowerDown结果不使用那些状态。','','## 证据与下一步','',
        '16项本地机制检查通过；服务器每个冻结快照先跑其对应检查。原始结果/日志在project_archives/shared_memory227_20261101，各任务remote_root、source/archive/config/input/result SHA及代码逐文件SHA在[RESULTS.json](results/RESULTS.json)和work/rayggxia/227/EXECUTION_INDEX.json；不修改旧失败/探针或任何冻结作业。没有新RTL/PT/PPL，不新增数字电路run。','',
        '接下来先验收v3三组配对和完整36层，检查最后一个DMA、每bank容量、每种字节数以及唯一/重复V读。剩余主要物理未知是定制CIM并行读出外围、分发/保持与互联、跨K/数制宏及DRAM PHY；现有普通SRAM事件和DRAM核心不能替这些填0。[AttAcc §7.1](https://scale.snu.ac.kr/papers/2024-04-Conference-ASPLOS-AttAcc.pdf)同样分别标定逻辑、SRAM与外存来源，而不是依靠模拟器名称保证能量。','',
        '本实现作为unified_v6的显式共享后端候选：`python -m architecture_tlm --shared-memory ...`。原默认入口未改行为；没有另改其他成员任务或公开本地受限module_handoff包。']
    (out/'REPORT_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(sealed=list(summaries),paired_checks=comparisons),ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();main(a.root,a.workspace)
