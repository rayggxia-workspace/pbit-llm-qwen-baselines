from pathlib import Path
import hashlib,json,importlib.util,math
ROOT=Path(__file__).resolve().parents[1]
def main():
    result=json.loads((ROOT/'results/RESULTS.json').read_text())
    rows=result['matrix_cases']
    def find(name,mode,**kw):
        return next(r for r in rows if r['name']==name and r['mode']==mode and r['seed']==17 and not r['stalls'] and all(r.get(k)==v for k,v in kw.items()))
    report=['# Prefill控制原型：实现、回放与下一步', '',
     'Issue225 / PR266。新增独立RTL控制原型，保留现有decode默认配置。实际运行位置为本机Verilator；未提交Slurm。', '',
     f'本轮{result["runs"]}个进程回放、{result["checks"]}项检查通过。GU/Wd通过原有真实采样、门控和整数归约RTL；输出逐项与实际采样事件的独立整数oracle比较。', '',
     '## 已实现的控制机制', '',
     '- 16项矩阵阶段命令FIFO，满队列正常握手等待；输出组/K块依赖、32行状态租约、动态空闲核派发。',
     '- 每核8KiB权重装入一次，连续处理最多32行；每行独立输入码、尺度、采样与结果标签。最后一行捕获后释放CIM，双结果槽与下游累加解耦。',
     '- 共享16KiB DMA返回池、4路64B请求/返回、乱序响应、CIM写入完成才归还credit；取消时排空已承诺事务。',
     '- 两路32通道的读/对齐/加法/写回流水线，64个4KiB单1RW bank，256KiB物理状态空间；bank冲突、同地址依赖及输出回压均会停顿。',
     '- Prompt sequencer遍历全部prompt行和层，final norm/LM head只服务最后位置，随后给出decode起始位置；已接收服务在取消时排空。', '',
     '## 权重复用的周期与流量', '',
     '下表为6核、8输出组、2个K块、32行、无外部随机停顿的合成矩阵阶段。逐行重载列由实测M=1任务周期乘32得到；它是相同控制工作量的确定性外推，不是新全模型时延。', '',
     '|阶段|逐行重载周期（32×M1）|驻留32行实测周期|周期比|权重读取量|',
     '|---|---:|---:|---:|---|']
    for mode,label in [(0,'GU16'),(1,'Wd32')]:
        a=find('reuse',mode,m=1);b=find('reuse',mode,m=32)
        report.append(f'|{label}|{a["cycles"]*32:,}|{b["cycles"]:,}|{a["cycles"]*32/b["cycles"]:.2f}×|4MiB → 128KiB（−96.875%）|')
    report+=['', '相同输出行和采样预算下，复用减少的是权重加载次数，采样/数学工作量不减少。测试中每个阶段完成16块驻留权重、512行tile结果、2048个状态beat。', '',
     '## 核数扫描', '',
     '采用更长的24输出组、2个K块、32行，减少8组小形状的尾部影响；固定全部其他资源。周期是实际RTL结果，250MHz时间只做单位换算。', '',
     '|核数|GU16周期|Wd32周期|两阶段合计（µs @250MHz）|',
     '|---:|---:|---:|---:|']
    for cores in [4,5,6]:
        a=find('steady_groups',0,cores=cores);b=find('steady_groups',1,cores=cores)
        report.append(f'|{cores}|{a["cycles"]:,}|{b["cycles"]:,}|{(a["cycles"]+b["cycles"])/250:.3f}|')
    g=find('steady_groups',0,cores=6);w=find('steady_groups',1,cores=6)
    extra=(31744000*(g['row_gap_min']-18)+15872000*(w['row_gap_min']-34))/250e6/6
    sizing=ROOT.parent/'prefill_core_sizing_20261127'
    spec=importlib.util.spec_from_file_location('old_budget',sizing/'rockchip_match.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    prices=json.loads((sizing/'AREA_REVIEW_INPUTS.json').read_text())
    updates=[]
    for name in ['MiniCPM3-4B','Qwen3-4B']:
        count=old.counts(old.shape(name));loads=(count['gu_frames']+count['wd_frames'])//32
        for cores in [4,5,6,7,8]:
            base=old.estimate(name,cores=cores,bw=27,prices=prices)
            compute=(count['gu_frames']*g['row_gap_min']+count['wd_frames']*w['row_gap_min'])/250e6/cores
            scenarios=[('current_DMA_min256',256,256),('one_packet_per_cycle128_candidate',128,128),('CIM_write32_candidate',32,32)]
            if cores in [4,5,6]:
                mg=find('steady_groups',0,cores=cores);mw=find('steady_groups',1,cores=cores)
                scenarios += [('measured_profile_load_min',mg['load_min'],mw['load_min']),('measured_profile_load_max',mg['load_max'],mw['load_max'])]
            for label,gu_load,wd_load in scenarios:
                program=(count['gu_frames']//32*gu_load+count['wd_frames']//32*wd_load)/250e6/cores
                ff=max(compute+program,*[base['ff_floors_s'][s] for s in ['state_ALU','state_SRAM','DRAM']])
                total=ff+sum(base['other_stages_s'].values())
                assert total>=ff and loads*32==count['gu_frames']+count['wd_frames']
                updates.append({'model':name,'cores':cores,'scenario':label,
                 'GU_load_cycles':gu_load,'Wd_load_cycles':wd_load,'old_budget_s':base['total_s'],
                 'row_control_compute_s':compute,'load_service_s':program,
                 'FFN_component_budget_s':ff,'total_component_budget_s':total})
    update={'status':'component_budget_backannotation_not_full_prefill_replay',
     'clock_MHz':250,'prompt_tokens':128,'effective_DRAM_GBs':27,
     'observed_minimum_row_interval':[g['row_gap_min'],w['row_gap_min']],
     'inputs_sha256':{str(sizing/n):hashlib.sha256((sizing/n).read_bytes()).hexdigest() for n in ['rockchip_match.py','AREA_REVIEW_INPUTS.json']},
     'other_stages':'Unchanged prior digital INT8/attention/norm/staging/head service budgets; not integrated in this RTL.',
     'DMA_minimum':'128 packets per8KiB and current per-core allocation/offer II2 =>256cycles; no external latency or contention folded into this minimum.',
     'cases':updates}
    (ROOT/'results/BUDGET_UPDATE.json').write_text(json.dumps(update,indent=2)+'\n',encoding='utf-8')
    report+=['', '小形状里6核可能比5核略慢：固定组租约、尾部和加载仲裁都会影响利用率，不能仅按核数反比预测。以上长组扫描用于检查趋势，最终核数仍应在完整层任务中决定。', '',
     '## 比原解析预算更明确的地方', '',
     f'1. 实测无回压时，GU16/Wd32相邻行接收间隔最短为{g["row_gap_min"]}/{w["row_gap_min"]}拍，而旧计算核预算使用18/34拍。差值来自当前worker的LOAD、CLEAR、DRAIN、CAPTURE和任务接收控制。按此前MiniCPM3-4B/128输入工作量，仅这项差异在6核理想均分下增加约{extra:.6f}秒，不能继续把旧1.228秒当作已验证TTFT。',
     f'2. 此回放中，首行接收相对dispatch的延迟：GU {g["load_min"]}～{g["load_max"]}拍、Wd {w["load_min"]}～{w["load_max"]}拍。它包含DMA发包、返回、写入和首行接收；不是SRAM自身访问周期。',
     '3. 现有DMA每核每次只推进一个64B包，bank的offer寄存器存在空拍；4个返回端口也不是16个CIM写口的满速供给。因此32拍只是CIM端写口下限，不能作为这份DMA的8KiB实际装载时延。4×64B端口的理想64GB/s与现有发包/转发空拍后的最高32GB/s应分开，实际平均还取决于核/包bank分布。',
     '4. 状态流水线的双路II=1已由RTL验证：两路各1024个beat，总2048个beat在1027拍完成；强制同bank需2050拍，连续更新同地址需4096拍。随机输出回压下仍逐位一致。', '',
     f'输入码通过外部valid/ready服务供给，测试会插入有限等待，但未将激活SRAM具体bank接入。按6核满载、GU每行80B/Wd每行128B计算，接口目标约为{6*80*250e6/g["row_gap_min"]/1e9:.2f}/{6*128*250e6/w["row_gap_min"]/1e9:.2f}GB/s，另需尺度元数据；这是下一步存储映射的供数要求，不是本轮已验证的激活SRAM带宽。', '',
     '## 回填此前128输入预算', '',
     '仅将实测最短行间隔与现有DMA每块256拍装载下限回填此前组件模型，其余数字/Attention/归一化/编码等预算不变。这是更明确的组件预算，仍不是完整prefill回放。136GB/s并未混入本对照，外存仍为此前27GB/s有效情景。', '',
     '|MiniCPM3-4B核数|原组件预算（s）|回填行间控制与现有DMA下限（s）|',
     '|---:|---:|---:|']
    for x in updates:
        if x['model']=='MiniCPM3-4B' and x['scenario']=='current_DMA_min256':
            report.append(f'|{x["cores"]}|{x["old_budget_s"]:.3f}|{x["total_component_budget_s"]:.3f}|')
    report += ['',
     '上表256拍仍是装载下限；6核长组回放的实际装载区间为376～389拍，不能把1.545秒写成已测整机时间。进一步将各核数下实测装载区间回填，得到以下组件敏感值：', '',
     '|MiniCPM3-4B核数|实测装载区间回填后的组件预算（s）|',
     '|---:|---:|']
    for cores in [4,5,6]:
        lo=next(x for x in updates if x['model']=='MiniCPM3-4B' and x['cores']==cores and x['scenario']=='measured_profile_load_min')
        hi=next(x for x in updates if x['model']=='MiniCPM3-4B' and x['cores']==cores and x['scenario']=='measured_profile_load_max')
        report.append(f'|{cores}|{lo["total_component_budget_s"]:.3f}–{hi["total_component_budget_s"]:.3f}|')
    report += ['',
     '六核仍是1～2秒目标内的候选。若要对齐此前约1.4秒参考，优先压缩装载等待；7/8核在256拍下限情景中更快，但未做相应核数RTL回放，不能据此确认实际达标。每核改为每拍一包、进一步用满CIM写口的候选敏感值单列在BUDGET_UPDATE中，尚未实现。', '',
     '## 验证覆盖', '',
     '三seed 17/29/43，均覆盖正常与随机停顿、GU/Wd、T8/16/32/64/128、1/8/32行及3行尾块、组槽复用、双结果槽强制填满、16KiB DMA credit填满、命令队列填满、取消排空及取消后重启。另有40/152个K块长归约、24输出组核数扫描。源码与执行文件SHA绑定在RUN_MANIFEST及SOURCE_BINDINGS中。', '',
     '## 与完整prefill的关系', '',
     'Prompt sequencer和矩阵阶段控制器目前分开验证；服务延迟由测试握手驱动。GU/Wd分别接收合成输入码，尚未将GU输出经过模型codec后连接Wd。数字Attention/GEMM、统一激活物理映射及完整层任务展开未接入此原型。因此本轮没有完整4B prefill时间、PPL或新功耗/面积结果。', '',
     '建议保留此控制结构，下一步接入现有数字计算服务和层任务展开；同时优先优化DMA每核连续发包及行间控制空拍，再回放完整prefill。无需更换整个全局控制器，也不应为了补加载等待直接堆更多概率核。', '',
     '所有SRAM为明确的同步端口行为模型，未完成此新256KiB组织和控制器的综合/STA/PT。21位局部计数、64位状态、既有group codec及分层PRNG不变，未将FP24或新S/S2数值候选混入控制对照。']
    (ROOT/'REPORT_ZH.md').write_text('\n'.join(report)+'\n',encoding='utf-8',newline='\n')
    bindings={}
    for kind in ['state','prompt','matrix']:
        b=json.loads((ROOT/'results'/('build_'+kind)/'BUILD.json').read_text())
        bindings[kind]={'source_sha256':b['source_sha256'],'tool':b['tool'],
                        'verilate_code':b['verilate_code'],'link_code':b['link_code'],
                        'verilate_command':b['verilate'],
                        'representative_compile_command':b['compile'][0]['command']}
    (ROOT/'results/SOURCE_BINDINGS.json').write_text(json.dumps(bindings,indent=2)+'\n',encoding='utf-8')
    print('Report written; minimum row intervals',g['row_gap_min'],w['row_gap_min'])

if __name__=='__main__':main()
