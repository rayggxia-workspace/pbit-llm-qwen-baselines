"""Readable Chinese comparison tables from verified compact result records."""
import argparse
import json
import statistics
from pathlib import Path

LABELS = {'bf16_dense':'准确 BF16 基线', 'int8_dense':'数字 W8 FFN＋准确 Attention',
          'sc_dense':'随机 FFN＋准确 Attention', 'sc_pv':'随机 FFN＋PV 采样',
          'sc_screen_exact':'随机 FFN＋筛选后准确计算', 'sc_screen_pv':'随机 FFN＋筛选后 PV',
          'sc_ising':'随机 FFN＋Ising', 'sc_screen_ising':'随机 FFN＋筛选后 Ising'}
ORDER = list(LABELS)


def render(directory):
    summaries = json.loads((directory/'summary.json').read_text())
    cases = json.loads((directory/'cases.json').read_text())
    index = json.loads((directory/'ARTIFACT_INDEX.json').read_text())
    by = {(r['backend'],r['context'],r['case'],r['engines']):r for r in summaries}
    lines = ['# LLaMA-1 7B：当前架构 TLM 结果', '',
        '模型与Qwen结果独立保存。32层、32Q/32KV MHA、hidden4096、FFN11008；原生512/1024/2048、单步decode。',
        '仿真从既有KV开始，排除prefill、主机、PHY及CTS；数字/随机核仍有未标定系数。',
        '真实BF16 QK来自核验过的公开WT2窗口；捕获前后输出逐位一致。随机种子只改变硬件地址选择。**没有新PPL或实测芯片/GPU能效。**', '',
        'SC方案：100MHz，默认8个64×64随机阵列、T4096、A8/64路本地PRNG共享、数字SiLU；所有方案统一8MiB校准SS SRAM、16 lane和2通道2rank 16GiB DDR4。准确基线不配置SC阵列。PV按原上下文1/16：32/64/128样本。', '',
        f"本次已汇总 **{len(cases)}/82** 项：`{index['completeness_by_backend']}`。缺项时表格只列实际完成结果。", '',
        '## 先看 TLM 实际发出的读取事务', '',
        '以下为2K、完整32层、默认8阵列的三种子均值。分母分别为所有K、所有V各读一次；候选K与物理K在本布局中相等。摘要另算，不藏在K比例里。', '',
        '| Attention路径 | 完整K读取比例 | 完整V读取比例 | 摘要流量 MiB/token | Link核心时间 ms/token |',
        '|---|---:|---:|---:|---:|']
    for case in ORDER[2:]:
        r = by.get(('link_Staggered',2048,case,8))
        if r:
            lines.append(f"| {LABELS[case].replace('随机 FFN＋','')} | {r['K_physical_fraction']:.2%} | {r['V_physical_fraction']:.2%} | {r['summary_MiB_per_token']:.2f} | {r['attention_ms_per_token']:.2f} |")
    lines += ['', '注意：这是新max4固定偏置/温度选择器的地址结果，不能沿用早期LLaMA均值筛选的26%或旧PPL。Ising宏的内部混合与PPA未校准。', '',
              '## 主能耗表：完整 DRAMSys 闭环', '',
              '此表使用Staggered和同一16GiB配置。core采用有来源的Micron电流限值情景，interface仍是未校准代理；整机还包含未标定数字/随机核系数。准确基线同样是ASIC TLM，不是GPU测量。', '',
              '| 2K完整模型方案 | 种子数 | 时间 ms/token | 整机 mJ/token | DRAM core mJ/token | SRAM mJ/token | 参数化面积 mm² |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for case in ORDER:
        r = by.get(('dramsys_Staggered',2048,case,8))
        values = [x for x in cases if (x['backend'],x['context'],x['case'],x['engines'])==('dramsys_Staggered',2048,case,8)]
        if r:
            sram = statistics.mean(x['energy_categories_mJ_per_token']['SRAM'] for x in values)
            lines.append(f"| {LABELS[case]} | {len(r['seeds'])} | {r['ms_per_token']:.2f} | {r['mJ_per_token']:.2f} | {r['DRAM_core_mJ_per_token']:.2f} | {sram:.2f} | {r['area_mm2']:.2f} |")
    if not any(r['backend']=='dramsys_Staggered' for r in summaries):
        lines.append('| 完整DRAMSys仍在运行 | — | — | — | — | — | — |')
    lines += ['', '读表时分开两件事：Attention替换应与相同随机FFN的`sc_dense`比较；随机FFN本身应与`bf16_dense`和`int8_dense`比较。不要把低位权重减少的流量全部归功于随机计算。',
              '没有随机地址选择的三种dense路径，其TLM计数/时序确定，所以只运行seed0；筛选/PV/Ising地址路径各运行0/1/2。这里没有用这些种子验证FFN数值噪声。', '']
    for base_case, changed in [('sc_dense','sc_screen_pv'),('bf16_dense','sc_screen_pv'),('int8_dense','sc_screen_pv')]:
        a=by.get(('dramsys_Staggered',2048,base_case,8)); b=by.get(('dramsys_Staggered',2048,changed,8))
        if a and b:
            lines.append(f"- {LABELS[changed]}相对{LABELS[base_case]}：整机时间变化 **{(b['ms_per_token']/a['ms_per_token']-1)*100:+.2f}%**，配置能耗变化 **{(b['mJ_per_token']/a['mJ_per_token']-1)*100:+.2f}%**。")
    lines += ['', '## 能量具体花在哪里', '',
              '同一2K Staggered场景的三种子均值，所有已配置项目都计入；DRAM包括core和interface代理。', '',
              '| mJ/token | BF16基线 | 随机FFN＋准确Attention | 随机FFN＋筛选PV |',
              '|---|---:|---:|---:|']
    category_labels = {'DRAM':'DRAM', 'SRAM':'片上SRAM动态＋漏电', 'SC_core_and_residence':'随机计算核＋权重驻留',
                       'FFN_RNG_and_distribution':'FFN随机源、种子与分发', 'Attention_logic_and_sampler':'Attention逻辑、筛选及采样器',
                       'Digital_projection_norm_control':'数字投影、归一化与共享控制/闲置'}
    for category,label in category_labels.items():
        cells=[]
        for case in ['bf16_dense','sc_dense','sc_screen_pv']:
            selected=[x for x in cases if (x['backend'],x['context'],x['case'],x['engines'])==('dramsys_Staggered',2048,case,8)]
            cells.append(f"{statistics.mean(x['energy_categories_mJ_per_token'].get(category,0) for x in selected):.2f}" if selected else '—')
        lines.append('| '+label+' | '+' | '.join(cells)+' |')
    lines += ['', '这些分类避免把共享DRAM背景全部算进Attention。若Attention读取大降而整机变化小，先看权重流量与FFN采样时长，而不是假定V没有减少。', '',
              '## 更多随机阵列能解决什么', '',
              '以下为2K的Link敏感性，使用相同8MiB SRAM；64阵列需要更大一次波次权重槽，参数化总面积若超过100mm²就标不可行。Link的外存能量、50mW背景是未校准参数，**不能代替上面的DRAMSys能量表**。', '',
              '| 随机FFN＋筛选PV | 阵列数 | 时间 ms/token | Link mJ/token | 面积 mm² | 满足100mm²预算 |',
              '|---|---:|---:|---:|---:|---|']
    for engines in [8,16,32,64]:
        r=by.get(('link_Staggered',2048,'sc_screen_pv',engines))
        if r:lines.append(f"| 比例采样＋真实地址 | {engines} | {r['ms_per_token']:.2f} | {r['mJ_per_token']:.2f} | {r['area_mm2']:.2f} | {'是' if r['area_feasible'] else '否'} |")
    lines += ['', '增加阵列减少串行采样波次数，通常不能按同样倍率减少总采样事件/核动态能量。T4096的代价不会因为PRNG共用而消失。', '',
              '## DRAM低功耗配对对照', '',
              '| 2K方案、seed0 | Staggered mJ/token | NoPowerDown mJ/token | Staggered时间变化 |',
              '|---|---:|---:|---:|']
    for case in ['bf16_dense','sc_dense','sc_screen_pv','sc_screen_ising']:
        matches={b:next((x for x in cases if (x['backend'],x['context'],x['case'],x['engines'],x['seed'])==(b,2048,case,8,0)),None) for b in ['dramsys_Staggered','dramsys_NoPowerDown']}
        a,b=matches['dramsys_Staggered'],matches['dramsys_NoPowerDown']
        if a and b:lines.append(f"| {LABELS[case]} | {a['mJ_per_token']:.2f} | {b['mJ_per_token']:.2f} | {(a['ms_per_token']/b['ms_per_token']-1)*100:+.3f}% |")
    lines += ['', '低功耗差异由同一配置族实际命令与驻留时间计算，不把DRAMPower结果再乘器件/rank数，不使用旧VPP-PD电流或置零诊断情景。', '',
              '## 筛选质量边界', '']
    masses=[x['offline_retained_attention_mass'] for x in cases if (x['backend'],x['context'],x['case'],x['engines'])==('link_Staggered',2048,'sc_screen_pv',8) and 'offline_retained_attention_mass' in x]
    if masses:
        lines.append(f"2K新筛选器的BF16 oracle保留attention mass均值为 **{statistics.mean(x['mean'] for x in masses):.2%}**，三种子中的最差单头为 **{min(x['minimum_head'] for x in masses):.2%}**。这说明筛选有信息损失，不能仅凭节省的读取量宣布质量相同。")
    lines += ['', '没有新完整WT2或后缀PPL；捕获只证明观察工具没有改原模型。A8共享、比例PV、新max4与Ising宏需要另做数值评估。Ising默认IID oracle仅用于地址，不能把表中采样周期当作真实器件已经达到的混合时间。', '',
              '## 文件、复现和验收', '',
              '- `cases.csv`：每个种子、上下文和阵列数的总表；`summary.json`为均值/标准差。',
              '- `cases.json`：能量/时间/访存、随机源和源码SHA等分项；`ARTIFACT_INDEX.json`保存服务器原始成果与trace的大小和SHA。',
              '- `../../README_ZH.md`说明架构、预算、单位、PPA边界和完整命令；`../../EXECUTION_MANIFEST.json`记录不可变执行源码。',
              '- 芯片时间是TLM的ms/token；`wall_seconds`是CPU运行模拟器花费的时间。不要混用。',
              '- 已验证：参数分配完整、untied embedding、MHA候选/物理K相等、V去重、样本守恒、有限SRAM、无随机流SRAM、Ising不重复计随机源、逐项能量闭合。',
              '- 长原始轨迹留已授权服务器；访问需要服务器权限。新代码不包含权重、工艺库或凭据。', '',
              '最终结论只能基于这套固定硬件与成本情景，不能直接宣布GPU能效倍率或全局最优架构。', '']
    (directory/'RESULTS_ZH.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('directory',type=Path)
    render(p.parse_args().directory)
