"""Readable Chinese Llama-2 tables; all numbers come from verified report data."""
import argparse
import json
import statistics
from pathlib import Path


LABELS = {'bf16_dense': '准确 BF16 基线', 'int8_dense': '数字 W8 FFN＋准确 Attention',
          'sc_dense': '随机 FFN＋准确 Attention', 'sc_pv': '随机 FFN＋PV 采样',
          'sc_screen_exact': '随机 FFN＋筛选后准确计算', 'sc_screen_pv': '随机 FFN＋筛选后 PV',
          'sc_ising': '随机 FFN＋Ising', 'sc_screen_ising': '随机 FFN＋筛选后 Ising'}
ORDER = tuple(LABELS)
CATEGORIES = {'DRAM': 'DRAM core＋接口代理', 'SRAM': '片上 SRAM 动态＋漏电',
              'SC_core_and_residence': '随机计算核＋权重驻留',
              'FFN_RNG_and_distribution': 'FFN 本地随机源、种子与分发',
              'Attention_logic_and_sampler': 'Attention 逻辑、筛选与采样器',
              'Digital_projection_norm_control': '数字投影、归一化与共享控制/闲置'}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def render(directory):
    target = directory/'RESULTS_ZH.md'
    if target.exists():
        raise FileExistsError('refusing to overwrite rendered report: ' + str(target))
    summaries = read_json(directory/'summary.json')
    cases = read_json(directory/'cases.json')
    index = read_json(directory/'ARTIFACT_INDEX.json')
    baseline = read_json(directory/'BF16_BASELINE.json')
    if index['results'] != 116 or index['missing_cases'] or len(cases) != 116:
        raise ValueError('render only a validated, complete Issue 14 result set')
    by = {(r['backend'], r['context'], r['case'], r['engines']):r for r in summaries}

    def values(backend, context, case):
        return [x for x in cases if (x['backend'], x['context'], x['case'], x['engines'])
                == (backend, context, case, 8)]

    def category(context, case, name):
        selected = values('dramsys_Staggered', context, case)
        return statistics.mean(x['energy_categories_mJ_per_token'].get(name, 0) for x in selected)

    protocol = baseline['protocol']
    identity = index['model_identity']
    lines = ['# Llama 2 7B：原始模型基线与当前标准 TLM', '',
        '本目录独立于 Qwen 和 LLaMA-1。模型为 **Llama 2 7B Base**，32 层、32Q/32KV 的 MHA，hidden=4096、FFN=11008、head dimension=128；原生最长 4096 token。词嵌入和输出词表矩阵独立，QKV/MLP 无偏置，RMSNorm 的 ε=1e-5。', '',
        f"模型身份：`{identity['repository']}`，官方 revision `{identity['revision']}`。镜像只提供下载通道；权重、配置、分词器均由逐文件 SHA-256 固定。", '',
        '**这份报告包含两种不同证据：第一张表是原 BF16 模型在 GPU 上的完整语料 PPL；后续表格是单步 decode 的 ASIC TLM 时间、能量和面积估计。BF16 PPL 不代表随机 FFN、稀疏 Attention 或 Ising 的质量。**', '',
        f"已完成 **{len(cases)}/116** 项 TLM：Link {index['completeness_by_backend']['link_Staggered']} 项、DRAMSys Staggered {index['completeness_by_backend']['dramsys_Staggered']} 项、NoPowerDown 配对 {index['completeness_by_backend']['dramsys_NoPowerDown']} 项。", '',
        '## 1. 原 BF16 模型：完整 WikiText-2 滑窗 PPL', '',
        f"使用原始 BF16 模型、Transformers 4.45.2 SDPA、batch=1、seed={protocol['seed']}、stride={protocol['stride']}，关闭 TF32；交叉熵用 FP32，NLL 用 FP64 累加。原生 RoPE，每个窗口从位置 0 开始。输入不添加特殊 token，全文位置 1..N−1 各计分一次。", '',
        '| 原始 BF16 评估窗口 | PPL | 计分 token 数 | 总 NLL | 实际 GPU 评估时间 s | 显存 allocated 峰值 GiB |',
        '|---|---:|---:|---:|---:|---:|']
    for record in sorted(baseline['summary']['ppl'], key=lambda x:x['window']):
        lines.append(f"| {record['window']} | **{record['ppl']:.6f}** | {record['scored_tokens']:,} | {record['total_nll']:.6f} | {record['wall_seconds']:.2f} | {record['peak_allocated_bytes']/2**30:.2f} |")
    lines += ['',
        f"语料 SHA-256：`{baseline['summary']['data_sha256']}`；token ID SHA-256：`{baseline['summary']['tokenization']['token_ids_sha256']}`。原始文件、每窗口日志和完整环境在 `BF16_BASELINE.json` / `ARTIFACT_INDEX.json` 中索引。实际 GPU 为 `{baseline['environment']['gpu']}`；这里没有测 GPU 功耗。", '',
        'PPL 的 2K/4K 结果使用不同上下文条件，不能把二者差值解释为硬件效果。质量表不包含随机方案的新 PPL，也没有 HellaSwag 等任务分数。', '',
        '## 2. 统一硬件与模拟范围', '',
        '- 所有 TLM 都从已有 KV 开始，只执行 batch=1 的一个新 token，包含全部 32 层、词嵌入、QKV/输出投影、RMSNorm/残差和独立 lm_head；prefill、主机和实际 PHY/CTS 未计入。',
        '- 默认随机 FFN：8 个 64×64 阵列、100 MHz、W8/A8、每次矩阵 T=4096；gate/up 融合调度，数字 SiLU 与逐元素乘法，再随机 down 投影，残差接口保留 BF16。',
        '- 输入侧本地 PRNG 每 64 路共用一个 8-bit 随机字，分层根/子种子与 live/checkpoint 状态保留；按波次恢复，不缓存整段随机流。权重侧保持此前实现。',
        '- 统一 8 MiB 的校准 55nm SS SRAM，16 条 128-bit lane，80 MHz/16 GB/s 端口服务，有限容量与 ping-pong 槽、CDC 和 scatter DMA 均计时。',
        '- 2 通道、每通道 2 rank 的 16 GiB DDR4 DRAMSys，使用已审计的 Micron 电流限值情景及 Staggered/NoPowerDown 配对。接口能量仍是代理，DRAM core 不是芯片实测。',
        '- PV/Ising 样本数随原始长度取 L/16：512/1024/2048/4096 分别为 **32/64/128/256**；稀疏 V 按唯一索引读取，重复命中仍计加法。',
        '- QK 筛选使用 max4 固定偏置/温度，没有套用 Qwen 校准。MHA 各头拥有自己的 K/V，不存在 GQA 的跨 Q 头候选并集放大；摘要流量另列。', '',
        '真实 QK 由重新运行的原 BF16 模型捕获，捕获前后输出逐位一致。四种上下文取同一公开 WT2 段，起点 201979；前 2048 token ID 与 LLaMA-1 对照一致。每种上下文仅一个 decode 查询，不能代表所有文本或 decode 阶段。', '',
        '## 3. 主表：完整模型 DRAMSys 闭环', '',
        '以下为同一 Staggered 情景的结果。没有随机地址选择的三种 dense 路径只运行 seed0；PV/筛选/Ising 路径取 seed0/1/2 均值。面积是同一预算口径的参数化面积，未包含全部布局布线开销。']
    for context in (2048, 4096):
        lines += ['', f'### {context//1024}K 上下文', '',
            '| 完整模型方案 | 种子数 | 时间 ms/token | 整机 mJ/token | DRAM core mJ/token | SRAM mJ/token | 面积 mm² |',
            '|---|---:|---:|---:|---:|---:|---:|']
        for case in ORDER:
            row = by['dramsys_Staggered', context, case, 8]
            lines.append(f"| {LABELS[case]} | {len(row['seeds'])} | {row['ms_per_token']:.2f} | {row['mJ_per_token']:.2f} | {row['DRAM_core_mJ_per_token']:.2f} | {category(context,case,'SRAM'):.2f} | {row['area_mm2']:.2f} |")
    lines += ['',
        '**准确 BF16 基线这一行也是 ASIC TLM，不是 GPU 功耗。** 数字 W8 对照用于区分低位权重节省与随机计算本身的收益；Attention 改动先与相同随机 FFN 的 `sc_dense` 对比。', '',
        '| 上下文 | 随机 FFN＋筛选 PV 的对照基线 | 整机时间变化 | 整机能量变化 |',
        '|---|---|---:|---:|']
    for context in (2048, 4096):
        changed = by['dramsys_Staggered', context, 'sc_screen_pv', 8]
        for case in ('sc_dense', 'bf16_dense', 'int8_dense'):
            base = by['dramsys_Staggered', context, case, 8]
            lines.append(f"| {context//1024}K | {LABELS[case]} | {(changed['ms_per_token']/base['ms_per_token']-1)*100:+.2f}% | {(changed['mJ_per_token']/base['mJ_per_token']-1)*100:+.2f}% |")
    lines += ['',
        '正号表示增加，负号表示减少。这里没有预设随机计算一定更省；若采样时长和驻留能量过高，应按表中的实际分项处理。', '',
        '## 4. Attention 到底少读了什么', '',
        '物理 K/V 的分母分别为完整 K、完整 V 各读取一次；摘要没有藏在 K 比例里。Link 核心时间用来观察算术和访存调度，后面的整机能量仍以 DRAMSys 为主。']
    for context in (2048, 4096):
        lines += ['', f'### {context//1024}K：32 层物理读取与 Attention 时间', '',
            '| Attention 路径 | 完整 K 读取比例 | 完整 V 读取比例 | K MiB/token | V MiB/token | 摘要 MiB/token | 样本/头 | Link Attention ms/token |',
            '|---|---:|---:|---:|---:|---:|---:|---:|']
        for case in ORDER[2:]:
            row = by['link_Staggered', context, case, 8]
            label = LABELS[case].replace('随机 FFN＋', '')
            lines.append(f"| {label} | {row['K_physical_fraction']:.2%} | {row['V_physical_fraction']:.2%} | {row['K_MiB_per_token']:.2f} | {row['V_MiB_per_token']:.2f} | {row['summary_MiB_per_token']:.2f} | {row['samples_per_head']:.0f} | {row['attention_ms_per_token']:.2f} |")
    lines += ['',
        'PV 单独使用仍需完整 QK/Softmax，因此只直接减少 V 读取和 PV 运算。筛选先减少候选 K，随后可准确计算 PV 或继续按比例采样。Ising 宏替换概率/类别采样路径，内部随机更新与状态能量只计一次；它没有消除被保留候选的 QK。', '',
        '## 5. 能量花在哪里', '',
        '分类覆盖所有已配置能量项目，逐项和必须等于整机能量。Attention 逻辑一项不包含共享 DRAM/SRAM，不能当作整个 Attention 的独占能耗。']
    for context in (2048, 4096):
        lines += ['', f'### {context//1024}K Staggered：mJ/token', '',
            '| 能量分项 | BF16 基线 | 随机 FFN＋准确 Attention | 随机 FFN＋筛选 PV |',
            '|---|---:|---:|---:|']
        for name, label in CATEGORIES.items():
            cells = [f"{category(context,case,name):.2f}" for case in ('bf16_dense', 'sc_dense', 'sc_screen_pv')]
            lines.append('| '+label+' | '+' | '.join(cells)+' |')
        totals = [by['dramsys_Staggered', context, case, 8]['mJ_per_token']
                  for case in ('bf16_dense', 'sc_dense', 'sc_screen_pv')]
        lines.append('| **合计** | '+' | '.join(f'**{value:.2f}**' for value in totals)+' |')
    lines += ['',
        'FFN T4096 的串行周期会增加整机闲置、权重驻留和 DRAM 背景时间；降低随机源数量并不按相同比例降低矩阵采样事件数。低位权重的读取减少也不能全部归到随机机制。', '',
        '## 6. DRAM 低功耗策略的实际配对', '',
        '每一行配对均是相同模型、上下文、seed0、硬件和动态访问路径；只改变低功耗策略。', '',
        '| 上下文 | 方案 | Staggered mJ/token | NoPowerDown mJ/token | Staggered 能量变化 | Staggered 时间变化 |',
        '|---|---|---:|---:|---:|---:|']
    for context in (2048, 4096):
        for case in ('bf16_dense', 'sc_dense', 'sc_screen_pv', 'sc_screen_ising'):
            a = next(x for x in values('dramsys_Staggered', context, case) if x['seed'] == 0)
            b = next(x for x in values('dramsys_NoPowerDown', context, case) if x['seed'] == 0)
            lines.append(f"| {context//1024}K | {LABELS[case]} | {a['mJ_per_token']:.2f} | {b['mJ_per_token']:.2f} | {(a['mJ_per_token']/b['mJ_per_token']-1)*100:+.2f}% | {(a['ms_per_token']/b['ms_per_token']-1)*100:+.3f}% |")
    lines += ['',
        'DRAMPower 已按完整系统的 rank/device 配置累计，不再额外乘 rank 或器件数。本次未使用旧 VPP-PD 电流或将 VPP 置零的诊断配置。电流限值、接口能量代理和多 rank 电路未校准仍是能量精度边界。', '',
        '## 7. 筛选信息保留与质量边界', '',
        '| 上下文 | 筛选＋PV：BF16 attention mass 均值 | 三种子中最差单头 |',
        '|---|---:|---:|']
    for context in (2048, 4096):
        masses = [x['offline_retained_attention_mass'] for x in values('link_Staggered', context, 'sc_screen_pv')]
        lines.append(f"| {context//1024}K | {statistics.mean(x['mean'] for x in masses):.2%} | {min(x['minimum_head'] for x in masses):.2%} |")
    lines += ['',
        '- 保留 mass 只从同一条原 BF16 QK 轨迹离线计算，说明地址筛选有多少概率质量被留下，不能推出 PPL、生成质量或随机 FFN 联合推理效果。',
        '- 上述完整 WT2 PPL 只验证原 BF16 模型；本次没有替换全部 FFN/Attention 后的完整 WT2 PPL。需要独立数值评估 W8/A8、64 路 PRNG 共享、比例 PV、新筛选器及 Ising。',
        '- Ising 的 IID 数值 oracle 只驱动地址；宏内耦合、退火、混合时间和实际器件 PPA 尚未验证。所设宏延迟不是实测达到目标 softmax 误差所需的周期。',
        '- SRAM 已由工艺库数据校准，但随机计算核、比较器/PRNG、数字投影、路由、PHY 和布线仍含代理。现有 resident-weight 接口也不是 SRAM 可同时暴露所有权重的电路证明。',
        '- 调度采用有限容量、有限端口和保守串行 tile，没有宣称全局最优；本次没有阵列数量敏感性扫描，不能复用 LLaMA-1 的扫描数值当作本次结果。',
        '- 真实工作负载仅一段文本、每上下文一个 decode 查询，随机三种子主要验证地址/调度差异；不能作为真实 FFN 噪声或完整语料误差的三个独立试验。', '',
        '## 8. 复现与文件索引', '',
        f"- TLM/捕获不可变源码：`{index['code_commit']}`；BF16 PPL 源码：`{index['baseline_code_commit']}`。报告源码 SHA 保存在 `ARTIFACT_INDEX.json`，与执行源码分开记录。",
        '- `cases.csv`：116 项逐种子总表；`summary.json`：各上下文/方案均值及关键指标标准差；`cases.json`：能量、时间、访存、随机源、Ising、工作负载与源码分项。',
        '- `BF16_BASELINE.json`：实际 PPL、协议、模型/代码身份、环境及原始成果索引；`ARTIFACT_INDEX.json`：全部原始 TLM、轨迹、捕获校验及 BF16 文件的原字节大小、SHA-256 和服务器位置。',
        '- 本目录的 `../../README_ZH.md` 和 `../../EXECUTION_MANIFEST.json` 说明模型、命令、共享引擎依赖及不可变输入；长轨迹和权重留在已授权服务器，Git 只保存摘要/索引。',
        '- 已校验：116 个任务 key 完整唯一；模型/tokenizer/语料身份；原 BF16 捕获逐位一致；MHA 候选 K＝物理 K；V 物理读取＝唯一向量；L/16 样本及加法守恒；有限 8 MiB SRAM；无随机流 SRAM；Ising 不重复计算内部随机源；整机时间和能量闭合。',
        '- TLM 的 `ms/token` 是配置情景的芯片时间；`wall_seconds` 是模拟器 CPU 运行时间，PPL 表的 GPU 评估时间是第三种指标，三者不混用。', '',
        '所有能效判断只适用于本次明确配置与成本情景；不能据此宣称实测 GPU 倍率、芯片 PPA 或全局最优架构。', '']
    with target.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write('\n'.join(lines))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    render(parser.parse_args().directory)
