"""Apply the user's W4/W6/W8 expansion to the remote-agent design only."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
D=ROOT/'qwen3/training/sc_qat_20261023'

def edit(name,pairs):
    p=D/name;s=p.read_text(encoding='utf-8')
    for old,new in pairs:
        assert old in s,(name,old)
        s=s.replace(old,new)
    p.write_bytes(s.encode())

edit('REMOTE_AGENT_START_HERE_ZH.md',[
('前向采用确定性INT8权重','前向分别采用确定性INT4、INT6、INT8权重'),
('`scan.py`仅检查19项计划','`scan.py`仅检查57项计划'),
('真实W8导出','真实W4/W6/W8导出'),
('## 3. 实现下列五块，不要先开19个大任务','## 3. 实现下列五块，不要先开57个大任务'),
('W8假量化＋x共享采样','Wb假量化（b=4/6/8）＋x共享采样'),
('导出真正W8+固定表','导出真正Wb+固定表'),
('→ Wg8/Wu8 → FP32 g/u','→ Wg_b/Wu_b → FP32 g/u'),
('→ Wd8 → BF16输出','→ Wd_b → BF16输出'),
('权重确定性W8；本轮无双随机','权重确定性Wb（b=4/6/8）；本轮无双随机'),
('前向quantize/dequant得到W8','前向quantize/dequant得到对应Wb'),
('至少包含W8-only和目标动态采样学生传播路径','每个位宽独立校准，至少包含该位宽Wb-only和目标动态采样学生传播路径'),
('D32、F32、L32分别约100–200步；重算开关','每个位宽的D32、F32、L32分别120步，使用下述独立短课程；重算开关'),
('16随机配置＋3训练控制，每组200M有效训练token','3位宽×（16随机配置＋3训练控制）=57项，每组200M有效训练token'),
('每结构2B起，必要时5B；最终优选至少3训练seed','每个位宽选2–4结构，每结构2B起，必要时5B；最终优选至少3训练seed'),
('### 首轮19项，按这个执行','### 首轮57项，按这个执行'),
('统一B4、d2、组宽64；再加同数据/预算的BF16微调、W8-only QAT、固定B4/d2 A8编码mean QAT三个控制。','以上16种在INT4、INT6、INT8上各执行一遍，共48种随机训练。每个位宽分组再加同数据/预算的BF16微调、该位宽Wb-only QAT、固定B4/d2 A8编码mean QAT三个控制，共9控制、合计57项，计划工作量为原来的3倍。三份BF16控制的数值设置相同，是各分组配对重复，不能算三种位宽结构或三训练seed。统一B4、d2、组宽64；其余设置不变。'),
('前5%有效token使用W8+A8编码mean','A阶段每个位宽前5%有效token使用对应Wb+A8编码mean'),
('B阶段从最佳动态与最佳全静态F/L各选一个','B阶段在每个位宽内分别从最佳动态与最佳全静态F/L各选一个'),
('最多18组；完全相同配置/预算可复用','每个位宽最多18组，总计最多54组；完全相同位宽/配置/预算可复用'),
('C单项增加','C也在各位宽内单项增加'),
('每个结果使用本目录 `RUN_RESULT.example.json` 的字段，null表示未测，不当0。','每个结果使用本目录 `RUN_RESULT.example.json` 的字段，null表示未测，不当0。完成时必须将placeholder标志设false，并填写实际命令、执行源码manifest与配置路径/SHA。BF16控制实际weight_bits填16，随机编码/替换字段为不适用；W-only也不填写虚构的输入采样。逐seed保存NLL、目标数、PPL、原件路径和SHA，不能用单个NLL代表三seed。'),
('| case/执行SHA | 尺度/B/d |','| case/执行SHA/权重位宽 | 尺度/B/d |'),
('D32/F32/L32先导曲线与吞吐、A阶段Slurm清单','各位宽D32/F32/L32先导曲线与吞吐；G2通过后再附A阶段Slurm清单'),
])
p=D/'REMOTE_AGENT_START_HERE_ZH.md';s=p.read_text(encoding='utf-8')
s=s.replace('### 3.2 可训练参数与梯度', '''### 3.2 可训练参数与梯度

**位宽扩展严格只改权重量化精度。** 三组均按64×64 tile，`Qmax=2^(b−1)−1`，`scale=maxabs(W)/Qmax`；INT4码−7…7、INT6码−31…31、INT8码−127…127。全零tile保持0并按原规则防除零；round、对称截断、浮点主权重/STE规则相同。PR147只给W8 oracle，W4/W6需新增独立量化边界参考，不能把weight_bits配置字段改了但仍除127。

输入概率仍是A8 q/256，门限仍8位、共享64，绝不能随权重改成A4/A6。训练/数值参考可用int8容器保存W4/W6码，但结果必须分开记录逻辑位宽、容器位宽与实际packed字节；未经bit-pack不能声称实际存储缩为4/6位。W4/W6仍是固定权重，非权重随机流。
''')
s=s.replace('G1最少覆盖：', '''**G2独立短课程：每配置120个优化step，先20步mean、20步T128、20步T64、60步目标T32；L在最后20步冻结尺度。** 这只用于烟测，不能机械套用A的200M-token日程，否则先导可能尚未进入目标T。必须验证目标T与冻结L阶段的loss/梯度/重载，才放行A；A仍从原模型初始化。三个位宽分别执行，不能由W8通过推断W4/W6通过。

G1最少覆盖：''')
p.write_bytes(s.encode())

edit('TRAINING_PLAN_ZH.md',[
('学生36层FFN都采用W8、分档输入和真实随机采样','学生36层FFN分别采用INT4/INT6/INT8权重、分档输入和真实随机采样'),
('**W8指前向和导出权重为8位，并不表示训练时冻结权重。**','**本版按用户要求增加INT4/INT6，形成W4/W6/W8三组，其余设置不变，计划工作量为原来的3倍。位宽指前向和导出权重，不表示训练时冻结权重。**'),
('前向每次重新得到W8','前向每次重新得到对应Wb'),
('两个W8矩阵','两个Wb矩阵（b=4/6/8）'),
('→ Wd（W8）','→ Wd（Wb）'),
('第一版保持PR147算术：三矩阵按64×64 tile对称W8量化，码值−127…127；','第一版保留PR147其余算术：三矩阵按64×64 tile对称Wb量化，Qmax=2^(b−1)−1；W4/W6/W8分别为−7…7、−31…31、−127…127，tile scale=maxabs(W)/Qmax；'),
('先固定W8、A8、组宽64','三种权重位宽分别扫描，保持A8、组宽64'),
('| 尺度策略 | D、F、L、H | 四种都测 |','| 权重位宽 | INT4、INT6、INT8，三组同样扫描 | 各跑完整一套 |\n| 尺度策略 | D、F、L、H | 四种都测 |'),
('**4策略×4采样=16组**，每组约200M有效训练token，同数据顺序、同训练seed；另3个控制，共19组','**3位宽×4策略×4采样=48组**，每组约200M有效训练token，同数据顺序、同训练seed；各位宽另3个控制，共57项'),
('最佳动态与最佳全静态各B∈{2,4,8}、d∈{1,2,3}，**最多18组**','每个位宽内的最佳动态与最佳全静态各B∈{2,4,8}、d∈{1,2,3}，每位宽18组，**总计最多54组**'),
('对入围结构逐项测x/z不等T','各位宽分别对入围结构逐项测x/z不等T'),
('选2–4结构，每种2B有效训练tokens起','每个位宽选2–4结构，每种2B有效训练tokens起'),
('A中三个额外训练控制：相同数据/预算的BF16微调、W8-only QAT、编码期望值','A中每个位宽的三个额外训练控制：相同数据/预算的BF16微调、该位宽Wb-only QAT、编码期望值') if 'A中三个额外训练控制：相同数据/预算的BF16微调、W8-only QAT、编码期望值' in (D/'TRAINING_PLAN_ZH.md').read_text(encoding='utf-8') else
('A中三个额外训练控制：相同数据/预算的BF16微调、W8-only QAT、固定B4/d2的A8编码期望值QAT','A中每个位宽三个额外训练控制：相同数据/预算的BF16微调、该位宽Wb-only QAT、固定B4/d2的A8编码期望值QAT'),
('机器清单明确列出19个A阶段计划','三份BF16控制数值设置相同，属于各位宽分组的配对重复，不是三种量化结构或三个训练seed。机器清单明确列出57个A阶段计划'),
('前向得到 `W8_fake = W + stop_gradient(dequant(quant8(W)) − W)`，得到真实W8数值','前向得到 `Wb_fake = W + stop_gradient(dequant(quant_b(W)) − W)`，得到真实W4/W6/W8数值'),
('至少覆盖W8-only和目标动态采样学生路径','各位宽分别至少覆盖对应Wb-only和目标动态采样学生路径'),
('仅W8+A8期望值前向','仅对应Wb+A8期望值前向'),
('固定W＋精确线性累加','固定Wb＋精确线性累加'),
('因为前向W8就只需要4GB显存','因为前向是低位权重就只需要几个GB显存'),
('真正导出W8、尺度表','真正导出对应W4/W6/W8、尺度表'),
])
p=D/'TRAINING_PLAN_ZH.md';s=p.read_text(encoding='utf-8')
s=s.replace('输入概率仍', '输入概率仍')
s=s.replace('## 4. 简单扫描清单','输入概率保持A8/8位随机门限；W4/W6不意味着A4/A6。PyTorch可以用int8容器存低位码，但必须记录逻辑位宽与实际存储位宽；宣称4/6位存储前要真正bit-pack。W4/W6量化新增独立oracle，W8兼容PR147。\n\n## 4. 简单扫描清单')
p.write_bytes(s.encode())

p=D/'REMOTE_ENV.example.json';v=json.loads(p.read_bytes());v['weight_bits_sweep']=[4,6,8];v['planned_workload_multiplier']=3
p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
p=D/'RUN_RESULT.example.json';v=json.loads(p.read_bytes())
v.update(configuration_path=None,executed_source_manifest_sha256=None,actual_command_argv=[],comparison_suite_weight_bits=None)
v['model_revision']='1cfa9a7208912126459214e8b04321603b3df60c'
v['ffn'].update(replacement_applicable=None,weight_bits=None,weight_storage_container_bits=None,
                weight_export_packed_bytes=None,probability_bits=None,group_size=None,sharing=None)
v['evaluation'].update(all_model_layers_scoring_coverage_verified=False)
w=v['evaluation']['full_wt2'];w.pop('nll_sum');w.pop('scored_tokens');w.pop('per_seed_ppl')
w['per_seed_results']=[dict(seed=None,nll_sum=None,scored_tokens=None,ppl=None,raw_result_path=None,sha256=None)]
w['ppl_aggregation']='arithmetic_mean_of_per_seed_ppl'
p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
print('Updated remote guide, rationale, and templates for W4/W6/W8; no training run.')
