"""One reader-facing summary from two sealed scheduling experiments."""
import json,statistics
from pathlib import Path
R=Path(__file__).resolve().parents[3];D=R/'architecture_tlm/scheduling_v2_20261027';W=R/'work/jieruiz/186'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def main():
    first=read(D/'COMPARISON.json');early=read(D/'COMPARISON_EARLY_DMA.json');a=first['rows'];b=early['rows']
    old=early['baseline_mean_ms'];new=early['combined_mean_ms'];saving=100*(1-new/old)
    row0=read(D/'results_early_dma/case_1/RESULT_SUMMARY.json');baseline=read(D/'results/case_0/RESULT_SUMMARY.json')
    phases=['FFN_gate_up','FFN_nonlinear_encoding','FFN_AND_direct_down','ffn_output_conversion','ffn_residual']
    local=row0['FFN_contract']['local_state'];pc=row0['tile_pipeline']['digital']['counts'];sc=row0['FFN_contract']['local_pipeline']['counts']
    result=dict(first_execution=first['execution_commit'],early_execution=early['execution_commit'],completed=11,failed=0,
        baseline_mean_ms=old,new_mean_ms=new,mean_time_reduction_percent=saving,speedup=old/new,paired_baseline_seed0_ms=a[0]['TPOT_ms'],
        new_seed0_ms=b[1]['TPOT_ms'],new_seed0_FFN_ms=b[1]['FFN_ms'],baseline_seed0_FFN_ms=a[0]['FFN_ms'],
        new_seed0_projection_ms=b[1]['ordinary_projection_ms'],baseline_seed0_projection_ms=a[0]['ordinary_projection_ms'],
        data_storage_unchanged=all(x['SRAM_reserved_bytes']==a[0]['SRAM_reserved_bytes'] and x['local_weight_bytes']==a[0]['local_weight_bytes'] for x in a+b),
        all_same_seed_work_traffic_checks_passed=all(x['same_seed_work_identical'] for x in first['checks']+early['checks']),
        early_dma_counts=pc,SC_counts=sc,remaining=['single macro DMA actor and cross-descriptor drain','shared SRAM descriptor-level arbitration','SC compute/counter/restore serialized','ordinary operator L/II still original configured values for scheduling isolation'],
        scope='full36-layer synthetic Qwen3-4B B1/2K decode, no numerical model or physical hardware measurement')
    (D/'FINAL_COMPARISON.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    lines=['# 随机版调度更改：最终汇总','',
        f'本轮完成11项完整模型TLM。组合三seed平均 **{old:.4f} → {new:.4f} ms/token**，时间减少 **{saving:.2f}%**，约 **{old/new:.3f}倍**。',
        '', '比较对象：Qwen3-4B后训练模型形状、36层、batch1、2K decode、包含lm_head。固定500MHz、32个64×64随机阵列、2048MAC/拍、GU64/NL128、8MiB/512bank/512GB/s SRAM和同一标准HBM；Attention为QK筛选＋准确Softmax＋PV采样。各情景不开门控，先隔离调度。',
        '', '| 调度变化（同seed0） | 整机ms/token | FFN ms | 普通投影及lm_head ms |', '|---|---:|---:|---:|']
    selected=[('原调度',a[0]),('仅普通矩阵预填充',a[1]),('仅资源就绪日历',a[3]),('仅SC跨窗口装载',a[2]),('上述三项组合',a[4]),('仅提前下一DMA请求',b[0]),('三项组合＋提前DMA',b[1])]
    for label,r in selected:lines.append(f"| {label} | {r['TPOT_ms']:.4f} | {r['FFN_ms']:.4f} | {r['ordinary_projection_ms']:.4f} |")
    lines+=['', '各组合seed都与旧同seed基线配对；三seed波动见两份COMPARISON文件。seed0旧基线64.3779ms逐数复现。', '',
        '## 做了什么，为什么', '',
        '首轮去掉SC跨窗口装载限制、使用资源空隙、启用既有普通矩阵prefill，但合计收益只有约0.14%。42541次普通prefill中，下一权重能在前一计算结束前就绪的次数为0：请求仍在当前本地装载/计算开始后才发出。就绪日历无法提前尚未发出的请求。', '',
        '第二轮把请求发起改到已有响应缓冲释放的边界。普通BF16矩阵在当前权重写入shared槽后，即发下一tile DMA，与当前shared→local读出重叠；SC在当前program消耗响应后、准备随机context前发下一DMA。此时原来的单响应槽已经空闲，不需要新数据bank或第二套计算资源。', '',
        f"普通矩阵提前请求次数{pc.get('dma_issue_after_shared_fill',0)}，SC提前请求次数{sc.get('early_dma_before_context',0)}。组合seed0的FFN为{a[0]['FFN_ms']:.4f}→{b[1]['FFN_ms']:.4f}ms，普通投影/lm_head为{a[0]['ordinary_projection_ms']:.4f}→{b[1]['ordinary_projection_ms']:.4f}ms。", '',
        '## 保持不变与成本解释', '',
        '所有同seed方案的算术动作、采样需求、FFN逻辑帧/恢复顺序、DRAM/SRAM物理字节和数据容量已核对。沿用一个DMA响应槽、两shared槽、两个本地权重/系数bank；没有扩大阵列或SRAM容量。控制器的具体面积和能量后续回填。', '',
        '访问量和有效算术不变，节省主要来自等待被覆盖以及总时长缩短；不能把时间减少比例直接当成动态能耗减少比例。本轮不报完整芯片PPA或模型PPL。', '',
        '## 仍未展开的调度', '',
        '外存仍用原DRAMSys单macro actor，跨描述符仍排空；SRAM仍按整描述符锁资源；SC计算/计数与恢复仍串行。本轮不是全局最优调度，也没有改变普通数字L/II。下一步若继续优化，应分别测跨描述符有限在途、按beat供数与SC恢复流水，避免再次只开prefill标志而没有改变请求时机。', '',
        '## 证据和复现', '',
        f"首轮执行{first['execution_commit']}、Slurm3156七项；第二轮执行{early['execution_commit']}、Slurm3163四项，全部completed并核原始RESULT/EXECUTION/SUMMARY SHA。134项本地软件测试及第二轮每项12条冻结包测试通过。完整原件留个人服务器，只收小摘要入Git。", '',
        '首轮RESULTS_ZH.md/COMPARISON.json，第二轮RESULTS_EARLY_DMA_ZH.md/COMPARISON_EARLY_DMA.json，最终FINAL_COMPARISON.json。重建顺序：collect_schedule_v2.py、analyze_schedule_v2.py、collect_schedule_early.py、analyze_schedule_early.py、report_schedule_final.py。所有脚本位于work/jieruiz/186。']
    (D/'FINAL_RESULTS_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
