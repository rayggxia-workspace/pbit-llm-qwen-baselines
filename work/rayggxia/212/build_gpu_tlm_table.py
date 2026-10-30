"""Format existing sealed GPU observations and the FMA2 TLM budget; no new run."""
import csv,hashlib,json,shutil
from pathlib import Path
root=Path('C:/Users/86134/Documents/a_P_BIT')
w=root/'tmp/gpu-decode-issue212-20261029'
tlm=root/'tmp/tlm-breakdown-issue210-20261029/architecture_tlm'
gpu=w/'results/gpu_decode_energy_20261029/remeasure_20261030'
old=tlm/'component_budget_audit_20261029/results/REPORT_ZH.md'
fma=tlm/'digital_energy_20261029/results/fma_default_20261029/REPORT_ZH.md'
rows=list(csv.DictReader((gpu/'NSYS_MODULES.csv').open(encoding='utf-8-sig')))
whole=list(csv.DictReader((gpu/'PAIRED_WHOLE.csv').open(encoding='utf-8-sig')))
names={'Embedding':'词嵌入','QKV_projection':'Q/K/V投影','QK_RMSNorm':'Q/K RMSNorm','RoPE':'RoPE',
 'KV_append':'KV当前位置写入','Attention_core':'融合Attention（含QK、Softmax、PV及头展开）',
 'Wo_projection':'Attention输出投影Wo','Layer_RMSNorm':'层RMSNorm','FFN_gate_up':'FFN输入投影Wg/Wu',
 'FFN_SwiGLU':'FFN SiLU＋逐元素乘积','FFN_down':'FFN输出投影Wd','Residual_add':'残差相加',
 'Final_RMSNorm':'末尾RMSNorm','lm_head':'输出词表层lm_head'}
repo='https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/'
gpu_commit='8ea8d0f4fe2b8baed6562edc87319c4561121fba';tlm_commit='b516e1d9e7523e69d15be38627c2a82ac71be4c7'
lines=['# GPU实测与概率架构TLM：能量、功率、时间、面积统一表','',
 '整理日期：2026-10-30；Issue212补充，TLM数据只读引用Issue210。只汇总已有结果，没有重跑GPU、TLM、训练或电路仿真。','',
 '## 1. 总体对照','',
 '模型形状均为后训练Qwen3-4B、36层、batch＝1、decode，不含prefill。GPU运行原始BF16模型；TLM是随机FFN＋QK筛选＋准确Softmax＋PV采样候选，**这里不是Ising Softmax，也未完成同质量验收**。因此表格并列展示成本，不直接宣布加速比或节能倍率。','',
 '|平台/运行方式|上下文起点|时间ms/次|能量mJ/次|平均功率W|面积mm²与边界|',
 '|---|---:|---:|---:|---:|---|']
labels={'native_greedy':'GPU原始HF连续生成','static_KV_graph':'GPU静态KV＋Graph固定前向'}
for mode,label in labels.items():
 for c in ['2048','8192']:
  r=next(x for x in whole if x['mode']==mode and x['context']==c)
  lines.append(f"|{label}|{int(c)//1024}K|{float(r['ms']):.3f}|{float(r['J'])*1000:.2f}|{float(r['W']):.2f}|共用同一750mm² GPU裸片|")
lines+=['|TLM FMA2：片上已计价部分|2K|57.445|92.989|1.619|147.889，已计价55nm等效面积|',
 '|TLM：再加旧外存能量代理|2K|57.445|447.200|7.785|整系统面积未知，不能仍标147.889|','',
 'GPU连续生成每次256步×3，包含argmax与KV增长；2K缓存从2048到2303，8K从8192到8447。固定前向不含逐步生成/argmax。预热连测的真实生成另为2K25.728ms/5604.42mJ、8K25.891ms/8325.92mJ，保留在原报告，不能把全部批次差异归因于温度。',
 '', 'GPU能量包含GPU及关联板载显存电路，不含主机CPU/系统DRAM；750mm²只含GPU裸片，不含GDDR7芯片、封装或PCB。面积来自[NVIDIA官方白皮书表3](https://images.nvidia.cn/aem-dam/Solutions/geforce/blackwell/nvidia-rtx-blackwell-gpu-architecture.pdf#page=48)，不是我们量测。',
 '', 'TLM外存354.211677mJ/次、6.166060W沿用64pJ/B＋50mW代理，**不是经DRAMPower校准的HBM实测**。147.889mm²和92.989mJ仅为已计价部分，缺项仍未知；面积已按本项目原始工艺×0.81折算一次，GPU面积不套此系数。','',
 '## 2. GPU各模块实测','',
 '**时间**是静态KV＋原SDPA完整前向内的kernel累计时间（Nsight）；**能量/功率**是全部36层同类操作隔离回放的整卡读数（三重复），并非原位模块独立电源轨测量。执行顺序、缓存和空闲条件不同，不能把分项能量或时间简单相加当作上表整机数据，也不能用此表时间除回放能量得到原位模块功率。',
 '', '|模块|2K ms|2K mJ|2K回放W|8K ms|8K mJ|8K回放W|独立面积|',
 '|---|---:|---:|---:|---:|---:|---:|---|']
for key,label in names.items():
 a=next(x for x in rows if x['context']=='2048' and x['category']==key)
 b=next(x for x in rows if x['context']=='8192' and x['category']==key)
 lines.append(f"|{label}|{float(a['nsys_kernel_ms']):.4f}|{float(a['replay_J'])*1000:.2f}|{float(a['replay_W']):.2f}|{float(b['nsys_kernel_ms']):.4f}|{float(b['replay_J'])*1000:.2f}|{float(b['replay_W']):.2f}|共享，未拆分|")
lines+=['','FFN、Attention、投影与归一化共享SM、计算单元、寄存器、缓存及互连，没有各自独占的物理面积。不能按时间/能量占比切分750mm²；独立面积未知不表示零。Attention维持融合整体，不伪造QK/Softmax/PV各自实测能量。',
 '', '计量：预热长窗计数器与功率积分最大差0.662%，冷却后功率跃迁窗口最大差6.941%；NVML现代GPU功率为1秒均值，边界效应方向相符，未做任意时移校正，也没有外部电表精度认证。除约2us词嵌入外，另外26项Nsight/Torch Profiler kernel时间差均<1%。',
 '', '## 3. TLM各物理计价模块（采用FMA2新单价）','',
 '这是已计价账本，按同一57.445385ms/token换算平均功率。共享硬件面积只计一次，不按36层复制。列中的“未独立价”保持未知。数字MAC采用实测FMA2小核的能量映射，但500MHz完整集成阵列尚未验收；该表没有重新执行时序。','']
fmatext=fma.read_text(encoding='utf-8-sig')
table=fmatext.split('## 新默认逐模块表',1)[1].split('## 如何接入',1)[0].strip()
lines+=[table,'']
entries=[line.split('|')[1:-1] for line in table.splitlines() if line.startswith('|')][2:]
energy=sum(float(r[1]) for r in entries);area=sum(float(r[4]) for r in entries if r[4]!='未独立价')
assert abs(energy-92.988617)<.0001 and abs(area-147.889088)<.0001
lines+=['**已计价片上小计：92.988617mJ/token、1.618731W、147.889088mm²。** 不包括完整CIM外围、全部转换/向量算子、NoC/时钟控制等缺项；随机源和比较器有合并表征的端点不能凭空再拆成两份独立实测。',
 '', '## 4. TLM整token时间花在哪里','',
 '|串行阶段（含供数、存储等待与排队）|ms/token|', '|---|---:|',
 '|FFN，含输出转换和残差|25.209667|', '|QKV与O投影|16.356659|',
 '|Attention核心|8.952024|', '|lm_head与argmax|6.815673|',
 '|其余归一化、RoPE、残差及显式存储|0.111362|', '|合计|57.445385|','',
 '这五个串行阶段可相加；GPU上表则是kernel忙时，不能直接逐行算“加速倍数”。TLM共享数字MAC本身忙时仅1.576103ms，外存DMA忙时39.802997ms、共享SRAM fabric忙时15.286006ms；这些资源可能重叠，不能相加。FMA2改变能量与面积，不改变这组原时序。',
 '', '## 5. 比较时保留的区别','',
 '- GPU分项是软件功能；TLM分项是物理资源账本。QKV、Wo、筛选QK、lm_head在TLM中共用数字MAC，不能给每个软件功能各加一份面积。',
 '- GPU融合Attention准确执行；TLM减少K/V读取和PV运算。当前TLM为筛选＋准确Softmax＋PV采样，没有Ising的完整整机占比。',
 '- 本TLM为既有500MHz目标/32个64×64随机阵列/2048 MAC每拍/8MiB SRAM配置，含空闲动态减少90%的情景；不是每项RTL都已在500MHz签核的芯片。后续局部新结果不在本表中擅自替换。',
 '- 两侧尚未完成同质量、同端到端优化程度、同外存与物理缺项边界的验收；本文件用来定位成本，不把未知项默认为零。','',
 '## 6. 原始报告与版本','',
 f'- GPU科学结果：[{gpu_commit[:8]}原报告]({repo}{gpu_commit}/results/gpu_decode_energy_20261029/remeasure_20261030/REPORT_ZH.md)，Slurm3440/3443；模型revision1cfa9a7208912126459214e8b04321603b3df60c，输入/权重/源码SHA保留于原manifest。',
 f'- TLM FMA2源码与公开说明：[{tlm_commit[:8]}]({repo}{tlm_commit}/architecture_tlm/digital_energy_20261029/FMA_DEFAULT_UPDATE_ZH.md)；本机完整分项：`{fma}`。',
 f'- 原TLM阶段与存储账本：[原审计报告]({repo}{tlm_commit}/architecture_tlm/component_budget_audit_20261029/results/REPORT_ZH.md)。其144.544740mJ/156.118460mm²是**更新前历史价格**，不能替换本文件FMA2的92.988617mJ/147.889088mm²。',
 '', '输入文件SHA-256：','', '|文件|SHA-256|','|---|---|']
for f in [gpu/'NSYS_MODULES.csv',gpu/'PAIRED_WHOLE.csv',old,fma]:
 lines.append(f"|{f.name}（{f.parent.name}）|`{hashlib.sha256(f.read_bytes()).hexdigest()}`|")
filename='GPU_AND_TLM_MODULE_COMPARISON_ZH_20261030.md'
relative=Path('architecture_tlm/component_budget_audit_20261029/results')/filename
dest=w/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
mirror=root/'architecture_tlm/component_budget_audit_20261029/results';mirror.mkdir(parents=True,exist_ok=True)
shutil.copyfile(dest,mirror/filename)
for source,name in [(old,'TLM_PRE_FMA_AUDIT_ZH.md'),(fma,'TLM_FMA2_REPORT_ZH.md')]:
 p=mirror/name
 if p.exists():assert p.read_bytes()==source.read_bytes()
 else:shutil.copyfile(source,p)
assert dest.read_bytes()==(mirror/filename).read_bytes()
sha=hashlib.sha256(dest.read_bytes()).hexdigest()
helper=w/'work/rayggxia/212/build_gpu_tlm_table.py';helper.write_bytes(Path(__file__).read_bytes())
elements=[dict(path=str(p.relative_to(w)).replace('\\','/'),mode='100644',type='blob',content=p.read_bytes().decode('utf-8')) for p in [dest,helper]]
(Path(__file__).parent/'GPU_TLM_TABLE_TREE.json').write_text(json.dumps(elements,ensure_ascii=False),encoding='utf-8',newline='\n')
print(json.dumps(dict(report=str(mirror/filename),formal=str(dest),sha256=sha,tlm_energy_sum_mJ=energy,tlm_area_sum_mm2=area,files=[e['path'] for e in elements])))
