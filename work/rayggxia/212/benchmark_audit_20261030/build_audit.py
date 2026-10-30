"""Derive a bandwidth/metric audit from archived results; no inference or TLM run."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tlm-root', type=Path, required=True)
    ap.add_argument('--gpu-root', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    fma_rel = 'architecture_tlm/digital_energy_20261029/results/fma_default_20261029/SUMMARY.json'
    fma_raw = (args.tlm_root / fma_rel).read_bytes()
    fma = json.loads(fma_raw)
    inputs = [{'path': fma_rel, 'sha256': digest(fma_raw), 'role': 'energy-only replay provenance; original timing unchanged'}]
    cases = []
    for rel, expected in fma['sources'].items():
        raw = (args.tlm_root / rel).read_bytes()
        assert digest(raw) == expected, rel
        d = json.loads(raw)
        m = d['model']
        h, ff, layers = m['hidden_size'], m['intermediate_size'], m['num_hidden_layers']
        q = m['num_attention_heads'] * m['head_dim']
        kv = m['num_key_value_heads'] * m['head_dim']
        matrix_counts = {'FFN_W8': 3 * layers * h * ff,
                         'QKV_BF16': layers * h * (q + 2 * kv),
                         'O_BF16': layers * q * h, 'lm_head_BF16': m['vocab_size'] * h}
        one_pass = matrix_counts['FFN_W8'] + 2 * sum(v for k, v in matrix_counts.items() if k != 'FFN_W8')
        traffic = d['DRAM']['traffic']
        assert one_pass == traffic['weights_logical_bytes'] == traffic['weights_physical_bytes']
        b = d['actions']['dram_read'] + d['actions']['dram_write']
        core_hz = d['config']['core_hz']
        peak = d['config']['dram']['theoretical_pin_bandwidth_GBs']
        assert peak == 256 and core_hz == 500_000_000
        selected_resources = ('dram_dma', 'sram_fabric', 'mac', 'vector', 'sc_local_program_bus', 'locality_accumulator', 'locality_stream')
        selected_stages = ('SC_locality_gu', 'SC_locality_down', 'SC_bucket_shift_reduce', 'SC_coefficient16_restore')
        cases.append({'seed': d['config']['seed'], 'ms': d['metrics']['TPOT_ms'],
                      'bytes': b, 'matrix_weight_bytes': one_pass,
                      'matrix_counts': matrix_counts, 'peak_GBs': peak,
                      'resource_busy_ms': {k: d['resource_busy_ns'][k] / 1e6 for k in selected_resources},
                      'stage_busy_ms': {k: d['stage_busy_ns'][k] / 1e6 for k in selected_stages}})
        inputs.append({'path': rel, 'sha256': expected, 'role': 'frozen full-model synthetic TLM result'})
    mean_ms = sum(c['ms'] for c in cases) / len(cases)
    mean_bytes = sum(c['bytes'] for c in cases) / len(cases)
    gpu_rel = 'results/gpu_decode_energy_20261029/remeasure_20261030/PAIRED_WHOLE.csv'
    gpu_raw = (args.gpu_root / gpu_rel).read_bytes()
    delivery_rel = 'results/gpu_decode_energy_20261029/remeasure_20261030/DELIVERY_SHA256.json'
    delivery = json.loads((args.gpu_root / delivery_rel).read_bytes())
    assert digest(gpu_raw) == delivery[gpu_rel]['sha256']
    assert len(gpu_raw) == delivery[gpu_rel]['bytes']
    rows = list(csv.DictReader(gpu_raw.decode('utf-8').splitlines()))
    gpu = {r['mode']: float(r['ms']) for r in rows if int(r['context']) == 2048}
    assert {'native_greedy', 'static_KV_graph'} <= gpu.keys()
    inputs.append({'path': gpu_rel, 'sha256': digest(gpu_raw), 'role': 'existing RTX5090 B1 measurements; native and static-KV separate'})
    peak_bound_ms = mean_bytes / 256 / 1e6
    diag = {'TPOT_ms': mean_ms, 'tokens_per_second': 1000 / mean_ms,
            'external_GB_per_token': mean_bytes / 1e9,
            'matrix_weight_GB_per_token': cases[0]['matrix_weight_bytes'] / 1e9,
            'external_bandwidth_GBs_over_entire_token': mean_bytes / mean_ms / 1e6,
            'token_average_fraction_of_peak': mean_bytes / mean_ms / 1e6 / 256,
            'peak_byte_transfer_lower_bound_ms': peak_bound_ms,
            'latency_divided_by_peak_transfer_bound': mean_ms / peak_bound_ms,
            'native_GPU_ms': gpu['native_greedy'], 'native_GPU_tokens_per_second': 1000 / gpu['native_greedy'],
            'static_graph_GPU_ms': gpu['static_KV_graph'], 'static_graph_GPU_tokens_per_second': 1000 / gpu['static_KV_graph'],
            'tlm_over_native_latency': mean_ms / gpu['native_greedy'],
            'tlm_over_static_graph_latency': mean_ms / gpu['static_KV_graph'],
            'digital_peak_MAC_per_s': 2048 * 500_000_000,
            'digital_peak_OP_per_s_2OP_MAC': 2 * 2048 * 500_000_000}
    sources = [
        {'id': 'flight', 'url': 'https://arxiv.org/html/2401.03868v1', 'sections': ['4.1', '6.1', '6.2.1', 'Table2', 'Table5'],
         'facts': 'U280 real implementation225MHz, HBM460GB/s plus DDR38GB/s; batch1; average3.5bit+pruning; VHK158 simulated; activations stay on chip, not full weights', 'raw_paper_SHA256': None},
        {'id': 'embedded', 'url': 'https://arxiv.org/html/2502.10659v1', 'sections': ['VII', 'TableII'],
         'facts': 'KV26064bit DDR4-2400=19.2GB/s, 300MHz, Llama2-7B W4/KV8, actual4.9tok/s, theoretical5.8 distinct', 'raw_paper_SHA256': None},
        {'id': 'hummingbird', 'url': 'https://arxiv.org/html/2507.03308v1', 'sections': ['V-A', 'V-C', 'TableV'],
         'facts': 'B1 short-context32:32, Llama3-8B W4/KV8, KV26019.2GB/s4.8tok/s; ZCU10434.1GB/s8.6tok/s; U25076.8GB/s19.4tok/s; source-defined bandwidth efficiency91-94%, not identical to our total-physical-bytes metric', 'raw_paper_SHA256': None},
        {'id': 'qwen', 'url': 'https://qwen.readthedocs.io/en/latest/getting_started/speed_benchmark.html', 'sections': ['Notes', 'Qwen3-4B'],
         'facts': 'B1 H20; counts(prompt+generation)/time; output2048; input1 BF16HF45.94/SGLang133.13; long-input1423.98 is not decode-only speed', 'raw_paper_SHA256': None},
        {'id': 'nvidia', 'url': 'https://www.nvidia.com/en-us/geforce/news/rtx-50-series-graphics-cards-gpu-laptop-announcements/',
         'facts': 'RTX5090 memory bandwidth1792GB/s; GPU memory path, not host DDR', 'raw_paper_SHA256': None},
        {'id': 'llmcompass', 'url': 'https://arxiv.org/html/2312.03134', 'version': 'v1 shown by retrieved HTML', 'sections': ['V-B'],
         'facts': 'traditional DRAM throughput-oriented example assumes aggregate1TB/s and large batch; throughput1.42x vsGA100 but latency9.21x worse; not low-bandwidth B1 speed evidence', 'raw_paper_SHA256': None}
    ]
    report = f'''# 解码速度与带宽口径核对：我们的17.4 token/s为什么较低

日期2026-10-30；Issue212 / PR214补充。复用封存结果及公开一手文献，没有新GPU、TLM、RTL、EDA或PPL实验，不改变现有默认和他人调度实现。

**结论：不能把差距主要解释成batch或55nm。相关FPGA工作中多项明确是B1；我们当前主要受外存供数、片上搬运/有限调度以及随机FFN处理链影响。工艺关系到实际可达时钟和PPA，但现有500MHz是尚未全面STA的目标，本结果没有额外施加一个“55nm慢若干倍”的惩罚。**

## 1. 先将能比较的指标分开

|对象|模型与权重|batch / 上下文|主要外存带宽|速度 / 证据|
|---|---|---|---|---|
|当前TLM封存候选|Qwen3-4B，FFN W8，其余矩阵BF16|B1 / 2K|HBM2峰值256GB/s|{1000/mean_ms:.2f}token/s、{mean_ms:.3f}ms；合成事务模型，500MHz目标|
|本项目RTX5090原生连续生成|同后训练Qwen3-4B原BF16|B1 / 从2K开始，生成256步|GDDR7峰值1792GB/s|{1000/gpu['native_greedy']:.2f}token/s、{gpu['native_greedy']:.3f}ms；已测|
|本项目RTX5090静态KV Graph|同原BF16|B1 / 固定2K|同上|{1000/gpu['static_KV_graph']:.2f}次/s、{gpu['static_KV_graph']:.3f}ms；固定前向，不是连续生成|
|嵌入式LLM加速器[1]|Llama2-7B，W4/KV8|单序列解码，最长1K|单64bit DDR4-2400，19.2GB/s|4.9token/s；真实板卡，300MHz|
|Hummingbird KV260[2]|Llama3-8B，W4/KV8|B1，prefill:decode=32:32|单64bit DDR4-2400，19.2GB/s|4.8token/s；真实板卡，300MHz|
|Hummingbird ZCU104[2]|同上|同上|两个64bit DDR4-2133接口，约34.1GB/s|8.6token/s；真实板卡，266MHz|
|Hummingbird U250[2]|同上|同上|四64bit DDR4-2400接口，76.8GB/s|19.4token/s；真实板卡，300MHz|

此57.45ms封存候选配置为500MHz、32×64×64随机tile、2048MAC/拍、8MiB SRAM；Attention是筛选＋准确Softmax＋PV采样，不是最新赢家保持/校正拒绝Ising，也不是所有新模块接入后的最终时序。

此表是口径核对，不是同模型/质量/面积的性能排名。Hummingbird的短上下文、W4和输入embedding卸载方式，与我们2K及混合位宽不同。它自报的91–94%带宽效率使用其模型大小/权重口径，不能与我们的物理总流量比例直接作同定义排名。

## 2. 带宽数来自哪里

DDR峰值=通道数×数据率(MT/s)×每通道有效数据位宽/8。已是MT/s时不再乘2；rank、bank、DIMM数量不自动等于独立通道。U250为4×2400×8=76.8GB/s；ZCU104使用PS和PL两条独立接口，合计约34GB/s，而不是只靠增加rank。

HBM的460GB/s、256GB/s分别是论文平台规格与我们的DRAMSys配置峰值。DDR与HBM同板并存时不能选较小的DDR数来解释HBM上的推理。RTX5090推理主要读GDDR7，不按主机DDR带宽计。[3][4]

FlightLLM[3]确实B1，U280真实实现225MHz；其HBM为460GB/s，另有38GB/s DDR。权重平均约3.5bit并结合稀疏化。其always-on-chip decode主要保留中间激活，不代表全部7B权重都常驻片上；VHK158部分为模拟器结果，不能混成两平台都已实测。没有从后续论文重列的约55token/s冒充原文单个确定配置的直接数值。

## 3. 我们到底用了多少带宽

三个原封存RESULT_SUMMARY的SHA逐项核验；独立按36层矩阵形状重算，W8 FFN+BF16 QKV/O/lm_head单遍字节数与逻辑/物理权重流量完全相同：{cases[0]['matrix_weight_bytes']:,}B，即5.355GB。没有因为T64/T128采样而重复读64/128遍权重。三seed平均总外存{mean_bytes/1e9:.6f}GB/token，权重占{cases[0]['matrix_weight_bytes']/mean_bytes*100:.2f}%。

|诊断量|值|含义|
|---|---:|---|
|配置峰值|256GB/s|DRAMSys HBM2 8通道×2伪通道|
|整token平均有效物理流量速率|{diag['external_bandwidth_GBs_over_entire_token']:.2f}GB/s|总物理字节/整token时间，约峰值{diag['token_average_fraction_of_peak']*100:.1f}%|
|纯搬运理想时间下限|{peak_bound_ms:.3f}ms|总字节/峰值；忽略所有其他限制|
|实际TLM时间|{mean_ms:.3f}ms|约为上述理想下限{mean_ms/peak_bound_ms:.2f}倍；不能将差额全算可消除浪费|
|外存DMA资源忙时|39.803ms|约69.3%的整token时长；不是等待在关键路径上的独占比例|
|共享SRAM fabric忙时|15.286ms|可与其他资源重叠，不能与上行相加|
|普通数字MAC资源忙时|1.576ms|配置2048MAC/拍×500MHz，峰值1.024TMAC/s，按2OP/MAC为2.048TOP/s|
|FFN GU采样/计数忙时|2.131ms|受采样、并行度和归约时序影响|
|FFN AND→Wd采样/计数忙时|5.800ms|与其他服务可能重叠|

原审计忙时来自同三seed报告，各行相互重叠；不能相加或直接从TPOT减去某行预测优化。外存/片上事务调度中仍有有限DMA响应槽、tile驻留与退休、共享端口、编程/恢复及反馈依赖。需要同字节流量的调度消融才能量化哪项可以回收。当前并未证明全局最优，也不能说只剩HBM极限。

## 4. batch、位宽、工艺分别解释什么

- **batch：** 上表涉及的嵌入式结果及FlightLLM是单请求/单batch，不是统一由大batch造成差距。LLMCompass[6]的传统DRAM吞吐方案是另一口径：总带宽1TB/s、尽可能大的batch；报告吞吐提高1.42倍，同时延迟差9.21倍。大batch不等于单用户出词快。
- **权重流量：** 当前混合存储平均约10.65bit/矩阵权重，不是全W8，更不是W4。即使只有4B参数，读取量仍可能大于W4的8B模型。低位是不同协议，不能直接继承其质量。
- **带宽：** 5090为1792GB/s，约是本TLM256GB/s的7倍；核心GHz或工艺节点不能代替这个差异。本项目GPU原生比TLM快{mean_ms/gpu['native_greedy']:.2f}倍；固定Graph快{mean_ms/gpu['static_KV_graph']:.2f}倍，后者不是连续生成吞吐。
- **工艺/频率：** 55nm影响500MHz能否落地、单元面积、能量与布线；但本TLM先假定500MHz，不能将其已出现的低吞吐归因为一次尚未建模的工艺降频。FPGA225–300MHz也能靠供数/数据流取得更高吞吐，频率不是充分指标。
- **随机计算：** 64/128采样及恢复/编程确实增加本地服务，不能全说成存储问题；但数字MAC忙时仅1.58ms也说明只扩大MAC并非当前最有依据的提速手段。不能从资源忙时单独证明全部延迟归因。

## 5. 官方GPU表还有一个常见误读

Qwen官方[5]使用B1，但Speed=(输入token+输出token)/总时间，输出2048token。Qwen3-4B/H20输入1时HF45.94、SGLang133.13token/s接近以decode为主的短prompt测试；输入63488时BF16 SGLang1423.98token/s包含大量prefill，绝不能倒数为0.70ms纯decode TPOT。我们的44.0token/s原生HF与官方短prompt HF约45.9处于同一量级，环境/上下文不同，不作为严格复现。

因此既存在batch混用，也存在prefill/decode、每层/整模型、低位/原精度、单芯片/整系统、实测/仿真的混用。逐项核对后，上表DDR结果不构成“5GB权重用20GB/s就能普通B1几十ms”的反例。

## 6. 下一步最有信息量的对照

保持当前模型、字节数、B1、FFN采样及计算资源，用相同标准DRAMSys重放4/8通道DDR4-2400/3200，再与现有HBM比较；优先记录实际各通道利用率、请求连续性、在途数、DMA/片上供数停顿及完整TPOT。只改变存储配置，不能同时更改位宽和batch后归因为DDR优化。

另一条独立消融才是改变tile重叠、局部端口/供数，或更新FFN模块；每次保存实际选择的版本。还需要相同资源/调度/存储的全数字对照，不能将不同频率或早期资源的旧基线混作本轮概率加速倍数。500MHz关键模块STA、PHY/controller、质量匹配仍单列。本次没有执行这些新情景，没有将搬运下限当作已达到的系统速度。

## 来源

[1] [Pushing up to the Limit…，§VII/TableII](https://arxiv.org/html/2502.10659v1)。

[2] [Hummingbird，§V/TableV](https://arxiv.org/html/2507.03308v1)。

[3] [FlightLLM，§4/§6/Table2/5](https://arxiv.org/html/2401.03868v1)。

[4] [NVIDIA RTX50官方规格说明](https://www.nvidia.com/en-us/geforce/news/rtx-50-series-graphics-cards-gpu-laptop-announcements/)。

[5] [Qwen官方速度测试及Notes](https://qwen.readthedocs.io/en/latest/getting_started/speed_benchmark.html)。

[6] [LLMCompass公开v1，§V-B](https://arxiv.org/html/2312.03134)。

自身来源：GPU科学8ea8d0f4，TLM FMA2仅重计价b516e1d9，原时序PR192；旁边GPU_AND_TLM_MODULE_COMPARISON_ZH_20261030.md保留原汇总。各输入原字节SHA及机器可读计算见同目录BANDWIDTH_AND_SPEED_AUDIT_20261030.json。外部来源采用指定版本URL/章节，未保存整篇原件SHA，未声称封存完整PDF。模板/自研宏估计不升级为实测芯片或同质量胜负。
'''
    result = {'scope': 'archived TLM/GPU and primary-literature metric audit; no new simulation',
              'owner': 'rayggxia', 'issue': 212, 'PR': 214, 'date': '2026-10-30',
              'inputs': inputs, 'source_script_sha256': digest(Path(__file__).read_bytes()),
              'cases': cases, 'diagnostics': diag, 'literature_sources': sources,
              'report_sha256': digest(report.encode('utf-8')),
              'limitations': ['Not iso-model/quality/area comparison to other papers', 'no new DDR4 full-model run',
                              'resource busy intervals overlap', '500MHz full RTL/physical closure unverified',
                              '37.3% is total-physical-bytes/whole-token time, not identical to source bandwidth utilization metrics']}
    args.output.mkdir(parents=True, exist_ok=True)
    md = args.output / 'BANDWIDTH_AND_SPEED_AUDIT_ZH_20261030.md'
    js = args.output / 'BANDWIDTH_AND_SPEED_AUDIT_20261030.json'
    md.write_bytes(report.encode('utf-8'))
    js.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({'ok': True, 'diagnostics': diag, 'report_sha256': digest(md.read_bytes()),
                      'json_sha256': digest(js.read_bytes()), 'verified_TLM_inputs': len(cases)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
