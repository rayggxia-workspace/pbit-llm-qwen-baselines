"""Regenerate compact tables from the frozen catalog; never runs EDA."""
import argparse
import json
from pathlib import Path
from .model import Catalog


def build():
    c = Catalog()
    lines = ['# 数字p-bit结果与实现比较', '',
             '2026-10-30，Issue95。本页由 `python -m architecture_tlm.random_service.digital_pbit.report --write` 生成。', '',
             '## 已测单路核：38427136', '',
             'SS1.08V125℃/TT1.2V25℃，100MHz、1fF输出负载，三seed均值。原面积保留，等效面积仅乘0.81一次。',
             '组合核的10ns是约束槽；寄存核II=1。不是最大频率/阵列签核。无PRNG/输入转换/CTS/SPEF。', '',
             '| 核 | PVT | raw面积 μm² | 等效面积 μm² | random μW | random pJ/调用 | idle μW | setup/hold ns |',
             '|---|---|---:|---:|---:|---:|---:|---:|']
    for d in c.data['designs']:
        r, idle = d['modes']['random'], d['modes']['idle']
        lines.append(f"| {d['top']} | {d['corner']} | {d['area_um2']:.2f} | {d['area_um2']*.81:.3f} | {r['total_uW']:.6f} | {r['pJ_per_call']:.6f} | {idle['total_uW']:.6f} | {d['setup_slack_ns']:.6f}/{d['hold_slack_ns']:.6f} |")
    lines += ['', 'TT LUT/寄存表/融合核的check_power告警保留。所有五活动模式及内部/切换/泄漏见 `catalog.json`。', '',
              '## 128节点TT100MHz：统一LOAD/SAMPLE窗口的条件估算', '',
              '以下全部不含PRNG；共享方案无独立8/9位阵列PPA，使用q9/valid及bit寄存的单核映射残差。',
              'free-running CE，没有ICG收益；译码/写入选择器/布线集成开销尚未计。共享方案面积不是完整宏面积。',
              '全复制K>1必须有上游x保持，且其面积/能量在上游计；否则不能直接采用该行。两边同样每SAMPLE拍需128个R8。', '',
              '| 方案 | LUT数 | 每配置样本K | 装载拍 | 总拍 | cell等效面积 mm² | 平均功率 mW | pJ/bit | 每节点有效MS/s |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    examples = []
    for k in [1, 64]:
        for kind, lanes in [('full_lut', 128), ('shared_lut_cached', 1), ('shared_lut_cached', 8), ('shared_lut_cached', 16)]:
            r = c.estimate_window(kind, lut_lanes=lanes, samples_per_configuration=k, inputs_held=True)
            examples.append(r)
            lines.append(f"| {kind} | {r['lut_replicas']} | {k} | {r['load_cycles']} | {r['total_cycles']} | {r['equivalent55_cell_area_mm2']:.6f} | {r['average_power_W']*1000:.4f} | {r['pJ_per_output_bit']:.4f} | {r['effective_per_node_Msample_s']:.4f} |")
    lines += ['', 'K=1全复制行复现实际融合核随机输入标定的128份复制；其余含共享/保持活动假设，不能写成新实测。',
              '共享先装满再并行采样：装载ceil(N/M)拍，首输出ceil(N/M)+1拍；不假定预取/双缓冲免费。',
              'q8仅1024bit但缺p=1端点，必须显式接受最大1/256误差；q9为1152bit且精确含0/1。',
              'q8暂无独立阵列PPA，沿用同q9+valid残差费，不按8/9比例伪造优惠。', '',
              '低频配置时真实ICG可能显著降低缓存保持功耗，但应补8/9位实际阵列表征后再回填。',
              '12/16位相关门控试验见 `../../attention_compare_20261027/regbank_20261029/REPORT_ZH.md`；不可按位宽直接缩成已测8位。', '',
              '这些费用不自动改变完整TLM默认；调用方还须计入随机源、输入转换、接口/上游存储、全局分发及未价集成项。', '']
    return '\n'.join(lines), examples


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write', action='store_true', help='regenerate RESULTS_ZH.md and EXAMPLES.json in this package')
    args = p.parse_args()
    text, examples = build()
    if args.write:
        here = Path(__file__).resolve().parent
        (here / 'RESULTS_ZH.md').write_bytes(text.encode('utf-8'))
        (here / 'EXAMPLES.json').write_bytes((json.dumps(examples, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        print('Wrote RESULTS_ZH.md and EXAMPLES.json (arithmetic only).')
    else:
        print(text)


if __name__ == '__main__':
    main()
