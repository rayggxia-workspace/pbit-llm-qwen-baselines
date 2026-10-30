"""Focused literature review and arithmetic checks; no model/TLM execution."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--paper-dir', type=Path, required=True)
    ap.add_argument('--tlm-summary', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    papers = json.loads((args.paper_dir / 'PDF_MANIFEST.json').read_bytes())
    for p in papers:
        raw = (args.paper_dir / (p['name'] + '.pdf')).read_bytes()
        assert len(raw) == p['bytes'] and sha(raw) == p['sha256']
    raw = args.tlm_summary.read_bytes()
    assert sha(raw) == '1554eb70f8bc77473664d0abede19abd4ee0692a1722ca4b6c63ea64ae6765b9'
    m = json.loads(raw)['model']
    x_bytes = m['hidden_size'] * 2
    kv_bytes = 2 * m['num_key_value_heads'] * m['head_dim'] * 2
    assert (x_bytes, kv_bytes) == (5120, 4096)
    derived = {
        'HSA_table_I_SILO_output_per_full_request_second': 37.6 * 750 / 800,
        'HSA_table_I_LISO_output_per_full_request_second': 138.3 * 50 / 800,
        'HSA_table_II_SILO_total_tokens_per_second_derived': 116.55 * 0.636,
        'HSA_table_II_SILO_output_per_full_request_second_derived': 116.55 * 0.636 * 750 / 800,
        'HSA_table_II_LISO_total_tokens_per_second_derived': 247.38 * 0.636,
        'HSA_rough_1_3B_W4_weight_GB_excluding_metadata': 1.3e9 * 4 / 8 / 1e9,
        'HSA_rough_weight_only_floor_ms_at_51_2GBs': 1.3e9 * 4 / 8 / 51.2e9 * 1000,
        'Kelle_illustration_7B_W8_weight_sweep_ms_at_64GBs': 7e9 / 64e9 * 1000,
        'Kelle_illustration_B16_weight_only_aggregate_tokens_per_second_upper_bound': 16 * 64 / 7,
        'Qwen3_4B_BF16_x_bytes_per_layer_per_token': x_bytes,
        'Qwen3_4B_BF16_K_plus_V_bytes_per_layer_per_token': kv_bytes,
        'Qwen3_4B_store_x_instead_of_KV_capacity_ratio': x_bytes / kv_bytes,
        'Kelle_Llama2_7B_WT2_relative_PPL_change': 5.74 / 5.47 - 1,
        'Kelle_Llama2_7B_PG19_relative_PPL_change': 12.59 / 10.51 - 1,
    }
    md = '''# HSA与Kelle：较低外存带宽下为何仍较快，哪些适合我们

2026-10-30，Issue212 / PR214速度与带宽审计补充；只读PR213@759b6c0f的论文清单，不修改其作者成果。固定v1原PDF逐SHA核验并检查HSA表I/II、Kelle图10–14；无新模型/PPL/训练/GPU/Slurm/TLM/RTL/EDA。

**结论：HSA主要借助小模型、低位权重、RetNet与MVM数据流；Kelle主要借助batch、KV压缩/重算、独立存储并行。它们说明低带宽也能合理提速，但不是“B1搬5GB权重只需十几毫秒”的反例。**

## 可直接核对的条件

|项|HSA|Kelle|
|---|---|---|
|模型/数制|RetNet-1.3B，decode MXINT4权重/A8；prefill W8|多模型；主设置W8、A/KV16|
|外存|DDR5 51.2GB/s，模型参数|LPDDR4 64GB/s，CACTI设定|
|片上|四簇各有权重SRAM，共享激活SRAM，256PE|权重SRAM2MB/128GB/s；KV eDRAM4MB及激活256KB，eDRAM256GB/s|
|batch|边缘单序列decode；缓冲可容16不等于评测B16|主评测16；另有B1/B4消融|
|证据|28nm、500MHz后布局；外存行为另建模|45nm逻辑综合、65nm存储模型、1GHz目标；非整片实测|
|速度|表I长输入138.3、长输出37.6，总token/s含prompt|主图13/14是归一时延/能效，不能推出统一绝对token/s|

## HSA：减小搬运量，并让阵列适合单token向量计算

它不把大模型权重全部塞进片上。粗取1.3B×4bit，权重约0.65GB，51.2GB/s对应仅权重搬运下限12.70ms；不含尺度/未低位部分/状态/控制，不能当实际流量。这与我们5.355GB混合位宽权重不是同一任务。RetNet以固定大小递归状态替代普通随上下文增长的KV扫描，不能把其全部收益迁给不改结构的Qwen。

硬件上，prefill用二维矩阵复用；decode切成四簇MVM，激活本地复用、权重分路流入，部分和留在PE。权重二次幂尺度走移位/桶选择，与乘加合并，减少单独反量化；还优化了RMSNorm和RoPE流水。

最相关的是PoT尺度与本地归约：论文采用输出方向16个权重一组、4bit移位因子。**4bit尺度编码不是只准选四档，分组方向也不是我们64输入分组。** 不能借其质量结果替我们的固定四档验收。融合RMSNorm也须保持有限位宽、概率编码及非线性实际驱动一致，不能把缩放任意跨过sigmoid。

### 原文两张速度表应分开保留

表I的37.6是(50输入+750输出)/整请求时间，换成只数输出但仍含prefill为35.25输出token/s，仍不是纯decode TPOT的倒数。表II给116.55token/s/mm²、0.636mm²，乘积为74.1258总token/s，换同输出分母为69.49294。长输入两表也分别为138.3与反推157.33368。

PDF原页确认均存在，非HTML漏列。两表没有明确给出能完全对齐的配置解释；差异与低位配置变化相容，但不能据此替作者断言“表I一定W8”。继续引用时分别注明表、模式、直接值/算术反推，不把两表拼成一条已闭合测量。上一轮138.3/37.6引用的是表I，不是247/117面积归一指标。

## Kelle：先区分总吞吐和单请求出词速度

主评测B16使同一权重tile可服务多请求。用7B/W8≈7GB作忽略其他成本的演示：64GB/s读一轮需109.375ms；B1只有一个输出，而B16一轮有16个输出，合计上限146.29token/s。每请求仍受约109ms一轮的约束。**这是我们的说明性下界/上限，不是论文实测，也不是已知Kelle绝对速度。** 主文3.94倍是相对其Original+SRAM基线，非同模型GPU绝对速度。

KV方面，它淘汰低重要性条目；部分token保存输入x、使用时重新生成K/V。权重SRAM与KV eDRAM分开，图12把权重与KV准备并行，让新K/V及时消费，缩短临时状态生命周期。32bank布局、将重要性更新/最小值搜索并入计算、避免额外遍历，也有借鉴价值。历史KV仍需要保存；图中的短临时生命周期不表示整份KV消失。

收益不只来自调度：同面积基线阵列24×24，新方案32×32，PE数增加1.78倍，另有算法/存储改变。eDRAM低刷新收益不能照搬到无需刷新的SRAM。质量也有代价：表2的Llama2-7B WT2 PPL5.47→5.74，PG19 10.51→12.59；是整套配置效果，不是单独调度误差。

### 我们的GQA不能直接套“存x重算KV”省容量

同为BF16，当前Qwen3-4B每层每token：

```text
x：2560×2 = 5120 B
K+V：2×8个KV头×128×2 = 4096 B
```

因此直接存x反而多25%容量；若只保留部分KV头，差距更大。Kelle的2C×θ>C条件主要对应其MHA推导。若另外压缩x，或为了省外存并与权重tile复用结合，仍可能重新设计，但必须另算精度、重算QK-Norm/RoPE、位置和算力成本；不能声称现有方案自动节省。

## 对现有项目的选择

1. 优先借鉴两篇共同的数据流：独立权重/KV端口，本地保持部分和，分块预取，结果尽快被下一算子消费。与Issue198正在探索的Attention专用bank/pending合并方向一致，不重复实现或冒称其已跑性能。
2. HSA的PoT尺度移位和桶归约可作为我们多尺度FFN的数字参考；必须匹配尺度档数/分组方向/质量。无需为了模仿它而更换Qwen为RetNet。
3. 做B1/B4/B16时分别报告单请求TPOT和总吞吐；不能用batch掩盖B1变慢。
4. 暂不直接引入eDRAM/低刷新、MHA式存x重算或跨非线性的尺度移动。默认模型/硬件参数不因文献阅读改变。

Kelle的§6也用操作数/吞吐、字节/带宽估算服务时间，并在其激活生命周期分析中省略较小计算时间；不是所有拍数都由一个通用模拟器自动给出。我们可沿用事件/TLM层级，但仍要让端口、容量、重叠和宏参数可检查。两篇没有替我们证明55nm下同速、同PPA或同质量。

## 来源与复核

- [HSA v1原文](https://arxiv.org/pdf/2507.09010v1)：§II–IV，PDF第5页表I、第6页表II/V。原页截图与文字交叉核对。
- [Kelle v1原文](https://arxiv.org/pdf/2510.16040v1)：§4–8，PDF第7/8页图10–12，第10页图13/14与评测设置；质量表与正文文字核对。
- 本项目形状来自封存RESULT_SUMMARY，未加载模型/新评质量；3.94×不直接迁移、0.65GB/7GB为演示假设、表II推算与原表I分别保存。外部面积不套本项目×0.81规则。
- 固定PDF原字节SHA、大小及算术、当前Qwen形状SHA见同目录HSA_KELLE_REVIEW_20261030.json；不上传论文PDF、图片、模型或工艺库。原报告/PR213保持不变。
'''
    data = {'scope': 'two-paper reading and derived arithmetic, not new hardware/model execution',
            'date': '2026-10-30', 'issue': 212, 'PR': 214, 'owner': 'rayggxia',
            'papers': papers, 'visual_review': {'HSA': [5, 6], 'KELLE': [7, 8, 10]},
            'Qwen_shape': m, 'Qwen_shape_source': {'path': 'architecture_tlm/scheduling_v2_20261027/results_early_dma/case_1/RESULT_SUMMARY.json', 'sha256': sha(raw)},
            'calculations': derived, 'report_sha256': sha(md.encode('utf-8')), 'script_sha256': sha(Path(__file__).read_bytes()),
            'limitations': ['HSA Table I and II do not numerically close; cause not established',
                            'Output/full-request rate is not pure decode TPOT', 'Kelle absolute tokens/s unknown from normalized main figures',
                            '0.65GB and7GB are illustrative parameter-size estimates, not traffic traces',
                            'No new PPL/TLM/EDA; default unchanged; PR213 author files not modified']}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'HSA_KELLE_REVIEW_ZH_20261030.md').write_bytes(md.encode('utf-8'))
    (args.output / 'HSA_KELLE_REVIEW_20261030.json').write_bytes((json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'passed': True, 'paper_SHA_verified': 2, 'calculations': derived, 'report_sha256': data['report_sha256']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
