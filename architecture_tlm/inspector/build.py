"""Build a source-linked inspection page from immutable TLM results.

This reads archived results, not model weights. New observations are optional
and labelled separately; old 80-event prefixes are never expanded or invented.
"""
import ast
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE='eb317e4f6fb1b0d8844887401f3275f128ef8a83'
EXEC='fba22b192ab914046e50cc405f6dd473bf30d154'
URL='https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines'
MODEL='architecture_tlm/unified_v6/model.py'
CORE='architecture_tlm/unified_v6/core.py'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def source(path, function=None, needle=None):
    raw=subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)
    text=raw.decode('utf-8')
    line=1
    if function:
        found=[]
        def walk(nodes,prefix=''):
            for n in nodes:
                if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
                    name=prefix+n.name
                    if name==function:found.append(n.lineno)
                    walk(n.body,name+'.')
        walk(ast.parse(text).body)
        if len(found)!=1:raise ValueError('ambiguous source anchor '+function)
        line=found[0]
    if needle:
        lines=text.splitlines(); found=[i+1 for i,l in enumerate(lines) if needle in l]
        if len(found)!=1:raise ValueError('ambiguous source needle '+needle)
        line=found[0]
    return dict(path=path,line=line,sha256=hashlib.sha256(raw).hexdigest(),
        url=URL+'/blob/'+BASE+'/'+path+'#L'+str(line),reference_commit=BASE)


def modules():
    # id, title, lane, I/O, current contract, outstanding check, evidence
    rows=[
      ('embedding','词嵌入','entry','token → D 个 BF16；独立 BF16 残差',
       '读取一个 embedding 行；事务源固定token7，不实际执行文本推理',
       '真实token/数值一致性属于模型评测，本页不证明', 'FullDecode.run'),
      ('norm','Attention RMSNorm','attention','D BF16 → D BF16',
       '归一化按向量/非线性吞吐和SRAM读写计时',
       '归一化和倒平方根是宏级操作，未做同工艺RTL标定','FullDecode.vec'),
      ('qkv','Q/K/V 投影','attention','D → D + 2×KV×d；BF16权重/接口',
       '固定权重矩阵，Qwen为14个Q头/2个KV头；常规数字路径',
       '512 MAC/拍是配置吞吐，不是GPU实测或已闭合阵列','FullDecode.matrix'),
      ('rope','RoPE、偏置与KV追加','attention','Q/K旋转；当前 K/V BF16 写外存',
       '当前token先追加，context数包含当前查询；历史KV预先存在',
       '不包含prefill和首次摘要构建，不能作为TTFT','FullDecode.run'),
      ('selector','摘要筛选／候选修复','attention','FP32摘要 + Q → 每Q头候选地址',
       'max4随机保留＋固定8块修复；摘要在DRAM；按KV组处理',
       '不是新训练筛选网络或耦合退火；地址由合成logits行为源决定','FullDecode.attention_rows'),
      ('qk','QK 与分数缩放','attention','候选 Q/K → FP32 分数',
       '先合并GQA多头的K地址，再按物理burst读取；各Q头分数独立',
       '逻辑候选保留率不等于K物理流量；并集放大必须显示','FullDecode.qk'),
      ('probability','Softmax／Ising类别采样','attention','FP32 分数 → 概率或 V 地址',
       '准确/PV、赢家、校正拒绝分别走不同路径；逐头处理',
       '输出次数、proposal帧、lane工作、FSM周期、有效独立样本不是同一个量','FullDecode.sample_row'),
      ('pv','PV／选V累加与平均','attention','V BF16；概率/地址 → 累加结果',
       'V按GQA组去重读取，但样本重复次数仍保留加法；PV用systematic偏移',
       '累加后回BF16转换未单列；systematic路径不继承旧IID PV的PPL','FullDecode.sampled_attention'),
      ('o','O 投影','attention','D → D BF16',
       '完整输出矩阵仍是常规数字计算',
       '输出投影及其权重搬运仍可能占显著成本','FullDecode.matrix'),
      ('residual1','残差相加＋FFN Norm','attention','独立 BF16 residual + Attention 输出',
       'BF16主路径保留；保存下一分支所需残差，不转换成随机流',
       '需要核对读写所有权和动态格式边界','FullDecode.residual_add'),
      ('encode_x','FFN 输入编码','ffn','每64个 BF16 x → q8/sign/bin/exact-one',
       '组内PoT顶尺度，四档S/S4/S16/S64；不重排通道',
       '动态maxabs/编码/比较器前端成本仍待工艺表征','FullDecode.matrix_sc'),
      ('gu','gate/up 随机矩阵','ffn','D → 2F；固定W8，B4/T32/K32',
       'gu合并矩阵共享x；8个64×64引擎，B4位平面计数并行；每波34拍',
       '32KiB驻留权重并行供给尚未闭合；48KiB计数状态只记metadata','FullDecode.matrix_sc'),
      ('restore_gu','符号、位平面和尺度恢复','ffn','计数 → g/u FP32 部分和',
       '按64路通用向量吞吐恢复，跨输入组部分和另读写',
       '跨组加法是否包含在恢复宏内需明确，避免漏算或双计','FullDecode.matrix_sc'),
      ('swiglu','连续 SwiGLU','ffn','g/u FP32 → SiLU(g)×u → z FP32',
       '当前仍是连续非线性和逐元素乘法，独立z缓冲',
       'gu完成后才做SwiGLU，再做down；不是已实现的通道流水','FullDecode.run'),
      ('encode_z','z 独立重新编码','ffn','每64个 FP32 z → q8/sign/bin/exact-one',
       'z独立定尺度；没有直接沿用Sg×Su的宽范围',
       'FP32入口的动态编码成本必须计入','FullDecode.matrix_sc'),
      ('down','down 随机矩阵与恢复','ffn','F → D FP32；固定W8',
       '与gu复用同类tile/恢复资源；每输入组重放相同随机阈值',
       'T32仅单波采样数，不是整层或整矩阵总周期','FullDecode.matrix_sc'),
      ('residual2','FP32→BF16＋残差','ffn','D FP32 → BF16 → BF16 residual',
       'SC/W8路径显式转换；BF16基准保持自己的格式',
       '转换位真行为与PPA尚未由本次模型验证','FullDecode.run'),
      ('readout','最终 Norm / lm_head / 选词','exit','D → 词表 logits → 下一token',
       '完整读出和argmax工作计入，不因embedding共享而消失',
       '合成事务只计工作，没有真实文本logits或生成质量','FullDecode.run'),
      ('rng','本地随机源','support','原始随机字／有偏响应，独立语义',
       '整机默认只是足量本地源合同；PR97有真实握手/种子模型',
       'PR103只有薄接口证明，尚未在整机启用；无流SRAM不等于无寄存器','FullDecode.__init__'),
      ('sram','片上 SRAM 与局部状态','support','权重ping/pong、残差、x/z、部分和、map/hist',
       '静态arena、16bank、80MHz宏；地址/端口/fabric互斥明确',
       '预留容量不是动态占用曲线；计数状态/保持接口不在宏面积内','FullDecode.__init__'),
      ('dram','DRAM / KV / 权重搬运','support','64B物理突发，32请求窗口',
       '本批默认Link16GB/s、80ns；每窗排空后再下一窗',
       '连续流窗口上限约9.85GB/s；不是此次DRAMSys/DRAMPower执行','FullDecode.weight'),
    ]
    actual={'FullDecode.attention_rows':'FullDecode.route'}
    nodes=[]
    for i,title,lane,io,contract,gap,fn in rows:
        # Resolve against actual code rather than guessing stable line numbers.
        try:ref=source(MODEL,actual.get(fn,fn))
        except ValueError:
            if i=='selector':ref=source(MODEL,needle='def select_rows(')
            else:raise
        nodes.append(dict(id=i,title=title,lane=lane,io=io,contract=contract,gap=gap,source=ref))
    return nodes


def risk_catalog():
    return [dict(id=i,title=t,status=s,impact=impact,check=check) for i,t,s,impact,check in [
      ('weight-feed','SC驻留权重接口','未闭合','每波32KiB权重须在T32期间并行稳定供给；普通SRAM单次读出不证明这一点','定制CIM/保持阵列/宽bank三者选定，标定端口、状态、面积与能量'),
      ('counter-state','局部计数状态','未落实','8引擎/B4/T32上限48KiB，仅metadata，未指定物理阵列','明确寄存器或阵列实现，不能从SRAM arena预留或宏面积中凭空抵扣'),
      ('trace','历史底层轨迹截断','观测限制','所有52项仅保留前80个事件；row receipt也非全量','完整phase可以绘图；底层仅画前缀，新运行另导出stage/逐query聚合'),
      ('rng','整机未启用新随机后端','未接通','旧结果假定本地足量供给；新源的种子/预热/回压尚不在整机时间中','接入时替换需求合同，源账本差分计一次，不重复加等待'),
      ('conversion','Attention输出格式转换','隐含边界','FP32累加到BF16输出没有独立转换动作','确定融合边界或单列转换，补位真测试与成本'),
      ('partial-add','跨输入组部分和','合同待明确','恢复宏和跨组累加的算术边界未单独说明','明确包含关系或增加独立动作，避免漏算/双计'),
      ('cdc','100MHz核／80MHz SRAM','代理时延','每次20ns CDC只是模型参数，不是实现证据','接口STA/CDC/缓冲和时钟开销待闭合'),
      ('dram','Link外存情景','代理模型','无行命中/ACT/PRE/刷新/休眠；64pJ/B+50mW是占位情景','关键情景再用真实DRAMSys闭环，不给Link结果贴DRAMPower标签'),
      ('sample-law','采样方法与质量版本','尚无联合证据','systematic PV、新赢家/拒绝和q/256 LUT不能继承旧CTMC/IID的PPL','每种数值算法绑定代码/数据/预算和对应模型指标'),
      ('energy','完整能量/面积','未标定','各方案缺项不同，已定价小计不具备整机能效比的意义','完整能量/面积保留未知；缺项、单价来源、计费边界逐项公开'),
      ('schedule','阻塞采样与直方图','保守映射','采样期间占所有SRAM bank/fabric，逐地址直方图RMW','这是可行代理，不是最优设计；选择性细化/独立实现校验'),
      ('input','输入与系统边界','条件事务','合成logits、预先存在KV/摘要；没有实际模型推理和prefill','报告限定decode，勿称TTFT或真实QKV全系统验证'),
      ('idle','保持/空闲成本','未区分','digital_idle/sc_idle按整窗口统计，不是互斥状态','赋值前区分工作/保持/睡眠，避免重复漏电'),
    ]]


def audit_case(r, rel):
    out=[];m,c=r['model'],r['config'];end=r['metrics']['elapsed_ns'];a=r['attention_activity']
    def check(name,ok,detail):out.append(dict(name=name,passed=bool(ok),detail=detail))
    check('阶段时间守恒',math.isclose(sum(r['phase_ns'].values()),end,abs_tol=.01),'sum(phase_ns) = elapsed_ns')
    check('token时间守恒',math.isclose(sum(r['metrics']['token_ms'])*1e6,end,abs_tol=.01),'sum(token_ms) = elapsed_ns')
    phases=r['phases'];check('阶段无重叠',all(p['start_ns']>=0 and p['end_ns']>=p['start_ns'] and (i==0 or p['start_ns']>=phases[i-1]['end_ns']-.01) for i,p in enumerate(phases)),'未归属内存时间单列')
    check('单资源忙时边界',all(0<=v<=end+.01 for v in r['resource_busy_ns'].values()),'每资源busy≤墙钟；不能累加busy当墙钟')
    regions=sorted(r['SRAM']['layout'].values(),key=lambda v:v['address']);cap=r['SRAM']['configured_bytes']
    check('SRAM容量及不交叠',all(v['address']>=0 and v['address']+v['bytes']<=cap and (i==0 or v['address']>=regions[i-1]['address']+regions[i-1]['bytes']) for i,v in enumerate(regions)),'静态预留，不是动态live occupancy')
    check('完整层覆盖',all({p['layer'] for p in phases if p['token']==token and p['name']=='FFN_down'}==set(range(m['num_hidden_layers'])) for token in range(c['decode_tokens'])),'每token全部层完成FFN_down')
    check('QK/物理KV上界',a['QK_logical_positions']<=a['possible_QK_positions'] and a['K_unique_group_positions']<=a['possible_K_group_positions'] and a['V_unique_group_positions']<=a['possible_V_group_positions'],'逻辑头候选与GQA组物理并集分开')
    check('未知证据保留null',all(r['metrics'][k] is None for k in ('full_physical_energy_J','full_physical_area_mm2','quality_reference_ppl')),'未用缺项小计宣称完整PPA/PPL')
    check('配置SHA',hashlib.sha256(json.dumps(c,sort_keys=True,separators=(',',':')).encode()).hexdigest()==r['config_sha256'],'配置原值规范JSON SHA256')
    check('执行版本绑定',r['execution_commit']==EXEC,'冻结执行fba22b1')
    mem=r['SRAM']['traffic'];w=c['sram']['word_bytes']
    check('SRAM物理字节守恒',all(mem.get(d+'_physical_bytes',0)==w*mem.get(d+'_words',0) and mem.get(d+'_logical_bytes',0)<=mem.get(d+'_physical_bytes',0) for d in ('read','write')),'物理读写字节 = 字数×字宽，且不小于逻辑字节')
    if c['ffn']['mode']=='sc':
        d,f,l=m['hidden_size'],m['intermediate_size'],m['num_hidden_layers']*c['decode_tokens'];tiles=l*((d//64)*(2*f//64)+(f//64)*(d//64))
        check('FFN tile/乘积次数',r['FFN_activity']['SC_64x64_tiles']==tiles and r['FFN_activity']['SC_product_trials']==tiles*4096*c['ffn']['samples'],'tile公式×4096×T；无关并行波数')
    act=r['actions'];mode=c['attention']['mode'];clk=1e9/c['core_hz']
    if mode in ('screen_winner','screen_rejection'):
        p=act.get('sampler_proposal_frames',0);outs=act.get('sampler_output_indices',0)
        if mode=='screen_winner':ok=p==act.get('sampler_algorithm_updates',0)==act.get('sampler_winner_holds',0)+act.get('sampler_winner_switches',0)
        else:ok=p==outs+act.get('sampler_rejected_multi',0)+act.get('sampler_rejected_empty',0)
        check('采样提议/接受守恒',ok,'proposal包括拒绝或保持，不等于独立样本')
        check('FSM周期与服务时长',math.isclose(act['sampler_macro_active_cycles']*clk,r['resource_busy_ns']['sampler'],abs_tol=.01),'macro_active_cycles × core周期 = sampler busy')
    return out


def case_record(path):
    r=json.loads(path.read_text(encoding='utf-8'));c=r['config'];mode=c['attention']['mode'];a=r['actions'];clk=1e9/c['core_hz']
    fused=r['DRAM']['traffic'].get('KV_fused_physical_bytes',0);d=r['DRAM']['traffic']
    key='|'.join(map(str,(c['model_record']['name'] if 'name' in c['model_record'] else ('qwen' if r['model']['hidden_size']==896 else 'llama'),c['context_tokens'],c['seed'],c['ffn']['mode'],mode)))
    model='qwen' if r['model']['hidden_size']==896 else ('llama2' if 'llama2' in str(path) else 'llama1')
    waves=r['random_interface']['requests'].get('shared64_stratified',0)
    cfg=f"{c['ffn']['bins']}档/T{c['ffn']['samples']}/K{c['ffn']['strata']}"
    return dict(id=model+'|'+key,model=model,context=c['context_tokens'],seed=c['seed'],ffn=c['ffn']['mode'],attention=mode,
       path=path.relative_to(ROOT).as_posix(),sha256=digest(path),execution=r['execution_commit'],config_sha256=r['config_sha256'],
       metric=r['metrics'],phase_ns=r['phase_ns'],phases=[[p['name'],p['token'],p['layer'],p['start_ns'],p['end_ns']] for p in r['phases']],
       resources=r['resource_busy_ns'],waits=r['wait_ns'],actions=a,unpriced=r['unpriced_actions'],energy=r['energy_J'],
       memory=r['SRAM'],dram=r['DRAM'],random=r['random_interface'],shape=r['model'],attention_activity=r['attention_activity'],ffn_activity=r['FFN_activity'],
       events=r['events'][:10],saved_event_count=len(r['events']),event_count=r['event_count'],trace_truncated=r['trace_truncated'],rows=r['row_receipts'],
       core_ns=clk,sram_ns=1e9/c['sram']['clock_hz'],ffn_profile=cfg,budget=c['attention']['samples'] or math.ceil(c['context_tokens']*c['attention']['sample_ratio']),
       winner_multiplier=c['attention']['winner_update_multiplier'],waves=waves,
       SC_wave_ns=waves*(c['ffn']['startup_cycles']+c['ffn']['samples']*c['ffn']['sample_II_cycles']+c['ffn']['drain_cycles'])*clk,
       restore_ns=a.get('SC_restore_op',0)/c['vector_lanes']*clk,
       K_bytes=d.get('K_selected_physical_bytes',0)+fused//2,V_bytes=d.get('V_sparse_union_physical_bytes',0)+fused//2,
       checks=audit_case(r,path.relative_to(ROOT).as_posix()),source_kind=r['input_provenance'])


def main():
    dirs=['qwen_20261022_v2','llama1_bf16_20261022_v2','llama1_scpv_20261022_v2','llama2_bf16_20261022_v2','llama2_scpv_20261022_v2']
    paths=[]
    for d in dirs:
        paths += [p for p in (ROOT/'architecture_tlm/unified_v6/results'/d).rglob('*.json') if p.name not in ('EXECUTION.json','SUMMARY.json','ARTIFACT_MANIFEST.json')]
    cases=[case_record(p) for p in sorted(paths)]
    if len(cases)!=52:raise ValueError('expected exact archived52, not preflight prefixes')
    if len({c['id'] for c in cases})!=52:raise ValueError('duplicate case')
    checks=[x for c in cases for x in c['checks']]
    if not all(x['passed'] for x in checks):raise ValueError('archived invariant failure')
    data=dict(schema=1,source_commit=BASE,execution_commit=EXEC,scope='条件decode事务，不是模型推理或芯片性能',
       repository=URL,cases=cases,nodes=modules(),risks=risk_catalog(),
       audit=dict(cases=52,checks=len(checks),passed=sum(x['passed'] for x in checks),truncated_cases=sum(c['trace_truncated'] for c in cases),
          actual_events=sum(c['event_count'] for c in cases),kept_events=sum(c['saved_event_count'] for c in cases)),
       pending_rng=dict(pr=103,head='af98f9c87f801c3cf0fcaa8eae6966a4e5535575',status='接口证明，未接入整机默认'))
    observations=HERE/'observations.json'
    if observations.exists():data['observations']=json.loads(observations.read_text(encoding='utf-8'))
    encoded=json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    (HERE/'snapshot.json').write_text(encoded+'\n',encoding='utf-8',newline='\n')
    html=(HERE/'template.html').read_text(encoding='utf-8').replace('__SNAPSHOT__',encoded.replace('<','\\u003c'))
    (HERE/'model-inspector.html').write_text(html,encoding='utf-8',newline='\n')
    print(json.dumps(dict(cases=52,invariant_checks=len(checks),passed=True,html_bytes=(HERE/'model-inspector.html').stat().st_size)))


if __name__=='__main__':main()
