"""Render the literature-only Softmax reference; this does not run any EDA."""
from pathlib import Path
import csv
import hashlib
import io
import json

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'digital_circuit_simulation_registry'
DATA = OUT / 'references/softmax_20261028'
INPUT = ROOT / 'architecture_tlm/attention_compare_20261027/SOFTMAX_DIGITAL_SOURCES_20261028.json'
NAME = '08_Softmax文献功耗面积周期参考.md'


def dump(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def make():
    source_bytes = INPUT.read_bytes()
    source = json.loads(source_bytes)
    DATA.mkdir(parents=True, exist_ok=True)
    rows = []

    def add(key, label, sid, process, area, **kwargs):
        rows.append(dict(id=key, label=label, source_id=sid, process=process,
                         area_um2=area, area_mm2=area / 1e6, area_scale=1.0,
                         row_cycles=None, n=None, parallelism=None, format=None,
                         frequency_mhz=None, clock_period_ns=None,
                         frequency_role=None, power_mw=None, power_frequency_mhz=None,
                         row_time_us_from_cycles=None, row_time_us_at_100mhz=None,
                         storage_boundary=None, verification=None,
                         area_is_derived=False, power_is_derived=False, **kwargs))

    # Table III/IV of the already archived and visually reviewed final SoftGen PDF.
    softgen = [
        ('fixed32_lut_p1', 'fixed32 LUT，P1', 1, 1542, 59000, 250, None, 'NOREG'),
        ('fixed32_lut_p2', 'fixed32 LUT，P2', 2, 775, 85000, 250, None, 'NOREG'),
        ('fixed32_lut_p4', 'fixed32 LUT，P4', 4, 392, 138000, 250, None, 'NOREG'),
        ('fp16_dw_p8', 'FP16 DesignWare，P8', 8, 199, 283300, 250, 8.38, 'NOREG'),
        ('fp16_lut_p8_iso', 'FP16 LUT，同频，P8', 8, 201, 220178, 250, 6.87, 'NOREG'),
        ('fp16_lut_p8_max', 'FP16 LUT，最高频，P8', 8, 201, 279711, 294, 10.19, 'NOREG'),
        ('fixed32_lut_p2_reg', 'fixed32 LUT，P2，含REG', 2, 775, 828000, 250, None, 'REG'),
        ('fixed32_lut_p4_reg', 'fixed32 LUT，P4，含REG', 4, 392, 835000, 250, None, 'REG'),
    ]
    for key, label, p, cycles, area, freq, power, storage in softgen:
        add(key, label, 'softgen_2020', '45nm FreePDK45', area)
        rows[-1].update(n=512, parallelism=p, format='IEEE FP16' if key.startswith('fp16') else 'fixed32',
                        row_cycles=cycles, frequency_mhz=freq, clock_period_ns=1000 / freq,
                        frequency_role='published synthesis operating point', power_mw=power,
                        power_frequency_mhz=freq if power is not None else None,
                        row_time_us_from_cycles=cycles / freq, row_time_us_at_100mhz=cycles / 100,
                        storage_boundary=storage, verification='final PDF page7 TableIII/IV visually verified')

    for key, label, area, power in [('li_alpha1', 'Li2024，α1近似', 2336.0, .19),
                                    ('li_alpha4', 'Li2024，α4近似', 2492.4, .19),
                                    ('li_ref30', 'Li2024表内对照[30]', 3051.6, .23)]:
        add(key, label, 'li_scis_2024', '65nm CMOS，厂商/PVT未核实', area)
        rows[-1].update(format='fixed-point approximation; exact widths not verified',
                        frequency_mhz=200, clock_period_ns=5,
                        frequency_role='200MHz derived from reported 5ns clock; not row latency',
                        power_mw=power, power_frequency_mhz=200,
                        storage_boundary='unverified',
                        verification='publisher PDF indexed Table5/7; full PDF unavailable; not visually verified')

    add('ita_integer', 'ITA整数Softmax', 'ita_v1', '22nm GF22FDX FD-SOI', 5709)
    rows[-1].update(format='8-bit integer approximation', frequency_mhz=500, clock_period_ns=2,
                    frequency_role='accelerator target, SS 0.72V 125C, not standalone row throughput',
                    power_mw=.847, power_frequency_mhz=500,
                    storage_boundary='module inside ITA array; includes implementation-specific state',
                    verification='PDF page5 visually verified',
                    area_is_derived=True, power_is_derived=True,
                    area_derivation='0.173mm2 whole accelerator * rounded 3.3%; approximate; also reports28.7kGE',
                    power_derivation='60.5mW whole accelerator * rounded1.4%; approximate, TT0.80V25C')

    for proc, area, freq, power, pf in [(16, 11000, 909, 1.5, 500), (130, 180000, 285.71, 51, 80)]:
        add(f'consmax_baseline_{proc}', 'ConSmax v3内普通Softmax对照', 'consmax_v3', f'{proc}nm，commercial EDA', area)
        rows[-1].update(n=256, format='DesignWare baseline; exact widths not verified',
                        frequency_mhz=freq, clock_period_ns=1000 / freq,
                        frequency_role='area at reported Fmax; power tested at a different frequency',
                        power_mw=power, power_frequency_mhz=pf, storage_boundary='not fully verified',
                        verification='v3 PDF page7 TableI visually verified')

    # Preserve the five previously published points exactly; do not change the old source index.
    for old in source['shape512_rows']:
        hits = [x for x in rows if x['parallelism'] == old['P'] and
                x['row_cycles'] == old['cycles'] and x['area_mm2'] == old['area_mm2']]
        assert len(hits) == 1, old
    assert len(rows) == 14
    for row in rows:
        assert row['area_scale'] == 1.0
        if row['row_cycles'] is None:
            assert row['row_time_us_from_cycles'] is None and row['row_time_us_at_100mhz'] is None

    document = dict(schema_version=1, kind='literature_reference_not_project_simulation',
                    date='2026-10-28', owner='rayggxia', issue=198, pr=199,
                    survey_source_commit='e73e50abc414c7b5ebd442a5c0f515880260236e',
                    input_index_path=str(INPUT.relative_to(ROOT)).replace('\\', '/'),
                    input_index_sha256=hashlib.sha256(source_bytes).hexdigest(),
                    sources=source['sources'], rows=rows,
                    limitations=['null means unknown, not zero',
                                 'row_cycles is whole-vector cycles, clock_period_ns is one clock',
                                 'all areas use their original processes; no SHARK0.81 scaling',
                                 'power_frequency_mhz may differ from area/Fmax frequency',
                                 '100MHz times are arithmetic only, not new STA',
                                 'no new run, synthesis, STA, power, model, or server job'])
    dump(DATA / 'REFERENCE.json', document)
    fields = ['id', 'label', 'process', 'n', 'parallelism', 'format', 'storage_boundary',
              'row_cycles', 'frequency_mhz', 'clock_period_ns', 'frequency_role',
              'area_um2', 'area_mm2', 'area_scale', 'power_mw', 'power_frequency_mhz',
              'row_time_us_from_cycles', 'row_time_us_at_100mhz', 'verification', 'source_id',
              'area_is_derived', 'power_is_derived', 'area_derivation', 'power_derivation']
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore', lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    (DATA / 'REFERENCE.csv').write_bytes(stream.getvalue().encode('utf-8'))

    def fmt(value):
        return '未核实' if value is None else f'{value:g}'

    lines = ['# Softmax文献功耗、面积和周期参考（2026-10-28）', '',
             '这是文献参考，不是本项目新仿真。负责人rayggxia，Issue198 / 草稿PR199；保留原工艺值，不应用SHARK制造面积×0.81规则。', '',
             '整行周期表示处理一行输入至输出完成的拍数；时钟周期表示每一拍的ns。未知值写“未核实”，不填0，也不从Fmax或每元素吞吐反推整行延迟。', '',
             '## 512元素：45nm FreePDK45，布局前综合', '',
             '| 实现 | 输入/存储 | 整行周期 拍 | 频率 MHz | 时钟周期 ns | 面积 µm² | 功率 mW | 整行时间 µs，cycles/f |',
             '|---|---|---:|---:|---:|---:|---:|---:|']
    for x in rows[:8]:
        lines.append('| ' + ' | '.join([x['label'], '512 / ' + x['storage_boundary'],
            fmt(x['row_cycles']), fmt(x['frequency_mhz']), fmt(x['clock_period_ns']),
            fmt(x['area_um2']), fmt(x['power_mw']), fmt(x['row_time_us_from_cycles'])]) + ' |')
    lines += ['', 'fixed32/LUT是定点近似；FP16是IEEE half，非BF16。NOREG依赖外部片上输入存储，不含完整本地输入缓存；REG计内部输入寄存器。fixed32各行未取得总功率，Table IV的“Add.energy”是附加访存/寄存能量，不能填成总能量或功率。工艺电压/温度未核实，不与本项目SS/TT条件等同。', '',
              '整行时间统一按cycles/f计算；保留原周期与频率。原文延迟小数与该商存在差异，尤其294MHz行，不用印刷小数覆盖周期数据。若只换算到100MHz，上表依次为15.42、7.75、3.92、1.99、2.01、2.01、7.75、3.92µs；这是算术，不是新STA。', '',
              '来源：[Wei等，ASAP2020，最终PDF第7页Table III/IV](https://utw10244.utweb.utexas.edu/pubs/SoftMax___ASAP2020_June27.pdf)。本机原PDF SHA已保存于REFERENCE.json；原文表格已视觉核验。', '',
              '## 其他工艺与近似方案', '',
              '| 方案 | 工艺 | 输入长度N | 整行周期 拍 | 面积 µm² | 面积/时序频率 MHz | 时钟周期 ns | 功率 mW | 功耗测试频率 MHz |',
              '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for x in rows[8:]:
        lines.append('| ' + ' | '.join([x['label'], x['process'], fmt(x['n']),
            fmt(x['row_cycles']), ('≈' if x['area_is_derived'] else '') + fmt(x['area_um2']), fmt(x['frequency_mhz']),
            fmt(x['clock_period_ns']), ('≈' if x['power_is_derived'] else '') + fmt(x['power_mw']), fmt(x['power_frequency_mhz'])]) + ' |')
    lines += ['',
              '- Li2024采用定点指数/除法近似。5ns为单拍，不是整行延迟；200MHz由5ns求倒数。当前仅取得出版方PDF索引表5/7，原PDF下载失败；位宽、输入长度、PVT、缓冲范围和整行拍数待核。来源：[Science China原文](https://scis.scichina.com/en/2024/200404.pdf)，[DOI](https://doi.org/10.1007/s11432-024-4137-4)。',
              '- ITA为8bit整数近似。5709µm²由整核0.173mm²×3.3%估算，0.847mW由60.5mW×1.4%估算，两项比例均有取舍误差。论文另报28.7kGE，不能误当µm²。500MHz目标STA为SS/0.72V/125°C；功耗为TT/0.80V/25°C、500MHz。这里不是512元素独立核。来源：[ITA v1，第5页](https://arxiv.org/abs/2307.03493v1)。',
              '- ConSmax表中引用的是普通DesignWare Softmax对照，非ConSmax本体。工作负载256元素；面积在Fmax条件、功耗分别在500MHz/80MHz，不能混配成同频结果；位宽与整行周期待核。来源：[ConSmax v3，表I](https://arxiv.org/html/2402.10930v3)。', '',
              '## 文件与使用边界', '',
              '- [REFERENCE.csv](references/softmax_20261028/REFERENCE.csv)：14个点，可直接筛选工艺和周期。',
              '- [REFERENCE.json](references/softmax_20261028/REFERENCE.json)：单位、来源、PDF SHA、功耗频率、推算说明与未知值。',
              '- [完整调研](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/e73e50abc414c7b5ebd442a5c0f515880260236e/architecture_tlm/attention_compare_20261027/SOFTMAX_DIGITAL_SURVEY_ZH_20261028.md)：数字Softmax与Ising采样的比较范围和后续建议。',
              '- 不把文献参考放入records当成本机run，不改既有仿真数值或run总数，不自动改TLM能耗系数；位宽/精度、存储、输入规模、PVT和采样质量需匹配后比较。',
              '- 复现：仓库根运行 `python -B work/rayggxia/198/build_softmax_reference.py`。数据版本来自上轮已发布调研，文献原件仍在授权本机私有归档；本次没有新增EDA或模型实验。', '']
    (OUT / NAME).write_bytes('\n'.join(lines).encode('utf-8'))
    print(json.dumps(dict(points=len(rows), files=[NAME, 'references/softmax_20261028/REFERENCE.json',
                                                'references/softmax_20261028/REFERENCE.csv']), ensure_ascii=False))


if __name__ == '__main__':
    make()
