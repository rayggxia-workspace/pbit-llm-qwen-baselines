from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[4]
D=ROOT/'architecture_tlm/current_handoff_budget_20261106'
r=json.loads((D/'RESULTS.json').read_bytes());x=r['central'];a=r['original_reference'];y=r['state152_control']
rows='\n'.join(f"|{name}|{v['area55_mm2']:.3f}|{v['energy_mJ']:.3f}|{v['average_W']:.3f}|" for name,v in x['groups'].items())
text=f'''# 最新模块交接后的概率方案功耗与面积预算

2026-11-06；Issue225/PR248。结论：按选定640路普通FMA及96KiB GU宽状态候选，已覆盖片上面积约**{x['covered_area55_mm2']:.2f}mm²**。暂用50ms/token计价窗口，片上约**{x['onchip_mJ']:.2f}mJ/token、{x['onchip_average_W']:.3f}W**，含4pJ/bit外存约**{x['system_mJ_at4pJ']:.2f}mJ/token、{x['system_average_W_at4pJ']:.2f}W**。

这是逐项动作与已有单价的重计价，不是新组合已完成原生整机TLM。640映射与96KiB分批目前分别有原生前缀结果，640完整lm_head/整token、两者在488bank上的联合调度仍待核；50ms只是接近旧封存时延的功率计价窗口。

## 1. 本次实际采用什么

|模块|本次计价|当前证据|
|---|---|---|
|普通数字池|640路、40个FMA16切片、K并行8、4context、outputtile320/Ktile128、提前补货|用户已选；首层至O六项原生对照完成，完整宿主待接入|
|末端归约|仍128个FP32加法器；每输出由63次ADD变7次|不减少物理加法器面积；动态动作按新K分组重算|
|FFN|12个公共C20/T64核、64位跨K；GU状态96KiB候选|三seed两层通过1%性能门槛，完整pair仍待结果|
|SRAM|1952KiB、488个4KiB宏、norm两槽32KiB、无额外空闲|不再用旧2.5MiB或502bank面积；未新增外围PPA|
|Attention|独立512路QK、SparQ K128、Ising赢家保持S64、PV ADD，8×128KiB缓冲|64KiB/组仍是方案；QK复用普通池未实现，均不预扣|
|其他|24KiB真实DMA入口、格式转换、向量和本地保持代理|沿已有价格及缺项边界，不重复加FFN RNG/SNG|

条件保持Qwen3-4B后训练形状、B1/2K、36层、100MHz、含embedding与完整lm_head、原LPDDR5派生8533时序背景。外存4pJ/bit是聚合能量假设，不是新LPDDR实测。面积沿本项目raw×0.81口径，已折算项不再乘。

## 2. 各部分总表

|片上部分|覆盖面积mm²|条件mJ/token|50ms窗口平均W|
|---|---:|---:|---:|
{rows}
|**片上合计**|**{x['covered_area55_mm2']:.3f}**|**{x['onchip_mJ']:.3f}**|**{x['onchip_average_W']:.3f}**|
|片外存储，4pJ/bit|不计入片上面积|{x['external_mJ_at_pJ_per_bit']['4']:.3f}|{x['external_mJ_at_pJ_per_bit']['4']/50:.3f}|
|**已计系统合计**|片上约{x['covered_area55_mm2']:.2f}|**{x['system_mJ_at4pJ']:.3f}**|**{x['system_average_W_at4pJ']:.3f}**|

面积57.57中已包含独立QK约7.836mm²，没有因为讨论过共享便将其删除。普通FMA池本身9.79481mm²，另有末端归约1.18719mm²。FFN的比较器、数字随机源及SNG已包含在C20核价，不再增加第二份相同成本。

## 3. 相对旧预算，哪里真的下降

|配置|覆盖面积mm²|片上mJ/token|含外存mJ/token|时间口径|
|---|---:|---:|---:|---|
|旧1024路/2.5MiB/152KiB状态|{a['area55_mm2']:.3f}|{a['onchip_mJ']:.3f}|{a['total_mJ']:.3f}|旧完整三seed封存约{a['time_ms']:.2f}ms|
|640路/2008KiB/152KiB状态|{y['covered_area55_mm2']:.3f}|{y['onchip_mJ']:.3f}|{y['system_mJ_at4pJ']:.3f}|假定50ms计价|
|640路/1952KiB/96KiB候选|{x['covered_area55_mm2']:.3f}|{x['onchip_mJ']:.3f}|{x['system_mJ_at4pJ']:.3f}|假定50ms计价|

当前96KiB候选的面积比旧预算减少约{-x['area_change_vs_original_percent']:.2f}%。其中普通FMA实例64→40切片省5.87689mm²，SRAM640→488个宏省4.09081mm²；归约物理实例、独立Attention及FFN核数保持。

面积减少不会使能量等比例下降。普通BF16 MAC总数仍为1,332,674,560，单次活动价仍为6.61243pJ，不能把其动态能量乘640/1024；减少的是实例保持功耗及部分调度开销。末端归约ADD由29,312,640变3,256,960，按每ADD单价收费。SRAM没有按容量缩小比例折扣动态读写；GU跨K读写量保持，分批新增输入码读取按已测两层差值外推收费。

norm流式每token多读392192B、SRAM增加装载写，headnorm共同展开每层512B读取；这两项已计，外存约5.41139GB/token。外存仍占系统能量约{x['external_mJ_at_pJ_per_bit']['4']/x['system_mJ_at4pJ']*100:.1f}%，所以面积减少约15%而总能量只小幅变化是合理的。

## 4. 功率依赖最终联合时间

50ms不是新测得的TPOT。保持同一活动量，45ms场景约{r['time_sensitivity'][0]['system_average_W_at4pJ']:.2f}W、55ms场景约{r['time_sensitivity'][1]['system_average_W_at4pJ']:.2f}W；该区间只展示时间敏感性，不是预测置信区间。外存若取6.6或8pJ/bit，同50ms窗口分别约{(x['onchip_mJ']+x['external_mJ_at_pJ_per_bit']['6.6'])/50:.2f}W、{(x['onchip_mJ']+x['external_mJ_at_pJ_per_bit']['8'])/50:.2f}W。没有把完整DRAM背景再叠加到聚合每bit价格上。

## 5. 仍需补齐的关键项

1. **联合整机调度**：640/8-K/提前补货＋96KiB分批＋488bank一起回放完整token及lm_head，不能相加各模块前缀时间。
2. **新增外围增量**：640跨步供数/结果槽背压/归约连接、96KiB状态owner/input-hit仲裁和新bank译码/互连尚未独立PPA；当前57.57是已覆盖模块预算，不是含PHY/IO/CTS的最终die。
3. **数值与活动适配**：640改变FP32求和分组，未继承逐位等价或PPL；C20仍按已有部分PT活动窗口价，没有因另一路T32或前8/后32的PPL结果擅自更换硬件T64能量。

Attention64KiB/组、共享QK、激活128KiB、CIM24槽、DOT8融合均未计入当前收益。旧随机源与SRAM单价已有数据；这里缺的是新连接/控制及联合活动，不是要从零重做所有随机源或SRAM。

重算：`python -B architecture_tlm/current_handoff_budget_20261106/estimate.py`。INPUTS绑定12个原件SHA并保存小型派生价表；RESULTS含16个能量/面积分项、两个状态方案和时间敏感性。没有新训练/PPL/RTL/PT，也未提交新原生任务；仅只读收取原norm任务已完成的封存结果，未干预其他模块任务。
'''
(D/'REPORT_ZH.md').write_bytes(text.encode())
print('report generated')
