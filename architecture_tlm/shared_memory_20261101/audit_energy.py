"""Reconcile immutable old SRAM counters against actual library event prices."""
from pathlib import Path
import argparse,hashlib,json,math

def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def compute(s,anchor):
    actions=s['actions'];seconds=s['metrics']['elapsed_ns']*1e-9
    def price(name,reads,writes,capacity):
        rw=math.ceil(reads/16);ww=math.ceil(writes/16);macros=math.ceil(capacity/4096)
        return dict(module=name,read_physical_bytes=rw*16,write_physical_bytes=ww*16,
            read_words=rw,write_words=ww,capacity_bytes=capacity,macros=macros,
            dynamic_mJ=(rw*anchor['Eread_internal_pJ']+ww*anchor['Ewrite_internal_pJ'])*1e-9,
            leakage_mJ=macros*anchor['leakage_ce_off_uW']*1e-3*seconds)
    sr=s['SRAM'];t=sr['traffic']
    shared=price('shared_SRAM',t['read_physical_bytes'],t['write_physical_bytes'],sr['physical_bytes'])
    loc=s['FFN_contract']['local_state']
    cim=price('local_CIM_SRAM_base',0,actions['SC_local_weight_program_byte'],loc['weight_hold_bytes'])
    digital=price('digital_local_buffers',actions['digital_local_operand_read_byte']+actions['digital_local_activation_read_byte'],
        actions['digital_local_operand_write_byte']+actions['digital_local_activation_write_byte'],
        s['digital_operand_contract']['operand_capacity_bytes']+s['digital_operand_contract']['activation_peak_bytes'])
    dma=price('DMA_response_buffers',actions['digital_DMA_response_buffer_read_byte']+actions['SC_DMA_response_buffer_read_byte'],
        actions['digital_DMA_response_buffer_write_byte']+actions['SC_DMA_response_buffer_write_byte'],s['tile_pipeline']['shared_response_capacity_bytes'])
    for row in [shared,cim,digital,dma]:row['energy_mJ']=row['dynamic_mJ']+row['leakage_mJ']
    assert math.isclose(shared['energy_mJ'],1000*(s['energy_J']['SRAM_internal']+s['energy_J']['SRAM_leakage']),rel_tol=1e-10)
    return [shared,cim,digital,dma]

def run(workspace,out):
    source=workspace/'tmp/tlm-breakdown-issue210-20261029/architecture_tlm'
    ap=source/'ppa_recalibration_20261027/ANCHORS.json';anchor=read(ap)['sram_E_SS']
    paths=[source/f'scheduling_v2_20261027/results_early_dma/case_{j}/RESULT_SUMMARY.json' for j in [1,2,3]]
    rows=[compute(read(p),anchor) for p in paths]
    average=[]
    for k in range(4):
        r=dict(rows[0][k])
        for field in ('read_physical_bytes','write_physical_bytes','read_words','write_words','dynamic_mJ','leakage_mJ','energy_mJ'):
            r[field]=sum(rr[k][field] for rr in rows)/3
        average.append(r)
    old=workspace/'tmp/module-estimate-issue225-20261031/architecture_tlm/module_estimate_20261031/INPUTS.json'
    expected=read(old)['baseline']['modules']
    for r in average:assert math.isclose(r['energy_mJ'],expected[r['module']]['energy_mJ_per_token'],rel_tol=1e-10),r['module']
    read_byte=anchor['Eread_internal_pJ']/16;write_byte=anchor['Ewrite_internal_pJ']/16
    # Exact external DDR configuration used in the already-verified bridge.
    chips=8*2*8;vdd=1.2;vpp=2.5
    ddr=dict(channels=8,ranks_per_channel=2,devices_per_rank=8,device_capacity_Gib=4,
        capacity_GiB=64,physical_devices=chips,read_write_data_bus_bits_per_channel=64,
        precharge_standby_W=chips*(vdd*.044+vpp*.003),
        active_standby_W=chips*(vdd*.061+vpp*.003),
        precharge_powerdown_W=chips*(vdd*.030+vpp*.003),
        self_refresh_W=chips*(vdd*.020+vpp*.003),
        disabled_low_power=True,old_50mW_proxy_is_this_DDR_model=False,
        one_rank_capacity_GiB=32,one_rank_precharge_standby_W=(chips//2)*(vdd*.044+vpp*.003),
        caveat='Current from actual source JSON. Refresh and state transitions add costs; not measurements or full DRAMPower replacement.')
    result=dict(status='PASS',scope='source-counter/library reconciliation plus datasheet-current sanity, no new PPA',
        SRAM_read_pJ_per_16B=anchor['Eread_internal_pJ'],SRAM_write_pJ_per_16B=anchor['Ewrite_internal_pJ'],
        SRAM_read_pJ_per_byte=read_byte,SRAM_write_pJ_per_byte=write_byte,
        SRAM_dynamic_pJ_per_bit=dict(read=read_byte/8,write=write_byte/8),
        average_rows=average,old_SRAM_total_mJ=sum(r['energy_mJ'] for r in average),
        copy_one_GB_write_plus_read_mJ=read_byte+write_byte,
        copy_5point4GB_write_plus_read_mJ=5.4*(read_byte+write_byte),
        DDR_current_sanity=ddr,DDR_power_status='old overridden current table, not vendor-validated; corrected official paired replay is in REPORT_ZH.md',
        source_identities=[dict(path=str(p.relative_to(workspace)),bytes=p.stat().st_size,sha256=sha(p)) for p in [ap,old]+paths],
        limitations=['SS library event energies, not full routed system costs','CEoff open-clock dynamic absent in library; not proven zero',
            'Full-parallel CIM readout/custom peripheral is outside ordinary SRAM price',
            '8ch/2rank DDR64GiB is overprovisioned for these model weights; rank/layout choices are hardware changes, not free simulator fixes',
            'DDR PHY/VDDQ not calibrated; negative ACT components must remain visible',
            'Horowitz numbers only order-of-magnitude sanity across different geometry/process/voltage, never calibration replacement'])
    out.mkdir(parents=True,exist_ok=True);(out/'STORAGE_ENERGY_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    text=['# 旧存储预算复算：单价与搬运次数分开（2026-11-01）','','**本页保留旧配置原账，DDR电流表后来发现与官方同型号不一致。修正和实际配对见上级REPORT_ZH.md；本页DDR数值不是新推荐值。**','','## 结论','',
        '**原约21.30mJ片上存储预算能由原始访问计数和工艺库事件价格复算，没有发现字节/字、pJ/nJ或频率重复换算错误。但其中相当部分来自多层搬运，应通过数据路径优化减少，而不是任意调低SRAM单价。**','',
        f'本项目4KiB/128bit SS宏每16B读取{anchor["Eread_internal_pJ"]:.4f}pJ、写入{anchor["Ewrite_internal_pJ"]:.4f}pJ；即读{read_byte:.4f}pJ/B、写{write_byte:.4f}pJ/B。每GB额外完整写入再读出约{read_byte+write_byte:.4f}mJ，5.4GB约{5.4*(read_byte+write_byte):.3f}mJ。位宽、容量、PVT和外围不同，不能拿其他工艺的一个MAC或SRAM数字直接替换。','',
        '| 原预算物理存储 | 动态mJ/token | 漏电mJ/token | 合计mJ/token |','|---|---:|---:|---:|']
    for r in average:text.append(f'| {r["module"]} | {r["dynamic_mJ"]:.6f} | {r["leakage_mJ"]:.6f} | {r["energy_mJ"]:.6f} |')
    text += ['', '## 多层搬运如何判断','',
        '原DMA响应槽在整块返回后、共享SRAM填充前保存数据；共享槽随后供本地operand/CIM装载。这些在旧生命周期下是不同存储，不是同一事件简单重复收费。改成有界返回FIFO逐beat写目标SRAM，才能删除对应整块staging事件。FIFO若仍落SRAM，读写仍应收；若流通旁路，弹性寄存器/路由是未定价项，不能说成本为0。','',
        '当前新模块严格禁止每采样重复读全部普通SRAM权重。GU/Wd采样中的时间部分和在核内寄存器，跨K状态/量化/输入保持需另记。SRAM端口从整描述符占用改为每拍bank仲裁，主要改变时间，不会自动减少同一组实际读写能量。','',
        '## DDR有一个比SRAM单价更大的口径问题','',
        f'实际八通道DDR4配置是2rank/通道、8颗x8器件/rank、4Gb/颗，共{chips}颗、64GiB。关闭PowerDown时，按VDD/VPP与IDD/IPP参数，预充电待机约{ddr["precharge_standby_W"]:.4f}W，激活待机约{ddr["active_standby_W"]:.4f}W；DRAMPower还加入刷新和访问状态。旧外存64pJ/B＋50mW是另一套代理，不能描述这套DDR设备。','',
        'DDR总背景应在整机同一时间线只计一次，不能把每个Attention组的整设备总能量相加，也不能把扣除matched-idle后的增量称完整DRAM能量。纯读64B、ACT/PRE、开行背景、刷新、低功耗和PHY必须区分。当前ACT组件含已知负项，保留原始报告，不能截成0来粉饰。','',
        f'一个合理的后续容量对照是同通道/相同时序的单rank，容量32GiB仍足够，待机电流下界约{ddr["one_rank_precharge_standby_W"]:.4f}W；这属于器件配置变化，需用完整地址范围/刷新/能量实际回放验证，不能直接宣布整机能量减半。','',
        '## 公开资料如何对照','',
        '- [Horowitz，ISSCC2014原文](https://gwern.net/doc/cs/hardware/2014-horowitz-2.pdf)：Fig1.1.9中8KiB/64bit缓存约10pJ、32KiB约20pJ、1MiB约100pJ，是不同条件的量级参照，不作为本55nm库校准。',
        '- [AttAcc，ASPLOS2024 §7.1](https://scale.snu.ac.kr/papers/2024-04-Conference-ASPLOS-AttAcc.pdf)：用公开SRAM数据校准FinCACTI，另取HBM访问依据，说明动作计数、存储结构与单价来源要分别核对。',
        '- [CACTI官方实现](https://github.com/HewlettPackard/cacti)：几何/端口/组织共同影响能量、时延和面积；应校准之后探索，不把容量简单乘每bit价格。',
        '- [DRAMPower官方实现](https://github.com/tukl-msd/DRAMPower)：命令和状态轨迹与memory specification决定能量；并非任意DRAM统一pJ/B。',
        '- [Accelergy官方实现](https://github.com/Accelergy-Project/accelergy)：用动作次数及动作能量表建立估算，支持本轮把单价校准和流量优化分开。','',
        '本轮没有新门级/PT仿真。原始三seed摘要、库参数索引及SHA在JSON，后续新事件调度结果另表，不改旧21.30mJ原件。']
    (out/'STORAGE_ENERGY_AUDIT_ZH.md').write_text('\n'.join(text)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:result[k] for k in ['status','old_SRAM_total_mJ','SRAM_read_pJ_per_byte','SRAM_write_pJ_per_byte','copy_5point4GB_write_plus_read_mJ','DDR_current_sanity']}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.workspace,a.out)
