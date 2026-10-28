"""Build the public, qualified report from immutable server numeric originals."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import tarfile
from collections import Counter

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--audit',type=Path);a=p.parse_args()
    root=Path(__file__).parent;d=copy.deepcopy(json.loads(a.source.read_text(encoding='utf-8')))
    for top in d['results']:
        for row in top['power_windows']:
            codes=row.pop('warnings');row['tool_message_codes']=codes
            # 601/602 are Information messages, not power-annotation warnings.
            row['warning_codes']={k:v for k,v in codes.items() if k not in ('PWR-601','PWR-602')}
    d['original_results_sha256']=sha(a.source)
    d['processing']='preserve all numbers; separate known Information PWR-601/602 from warnings'
    (root/'RESULTS.json').write_bytes((json.dumps(d,indent=2,ensure_ascii=False)+'\n').encode())
    tops=d['results'];total_cycles=sum(x['functional_cycles'] for x in tops)
    audit=[]
    if a.audit:
        with tarfile.open(a.audit) as t:
            index=json.load(t.extractfile('timing_audit_v1/INDEX.json'))
            for name,m in index['files'].items():
                b=t.extractfile(name).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
            for top in tops:
                prefix='timing_audit_v1/'+top['spec']['top']+'/'
                def text(name):return t.extractfile(prefix+name).read().decode()
                disabled=text('disable_timing.rpt');hold=text('hold.rpt');untested=text('untested.rpt');exceptions=text('exceptions.rpt')
                flags=Counter(re.findall(r'(?:positive_unate|negative_unate|non_unate)\s+([pcCdlLuUfm])\b',disabled))
                assert not any(flags.get(x,0) for x in ['l','L','u','U','f']),flags
                audit.append(dict(top=top['spec']['top'],disabled_arc_flags=dict(flags),
                    loop_breaking_arcs=flags.get('l',0)+flags.get('L',0),
                    false_or_multicycle_exceptions_reported=bool(re.search(r'false_path|multicycle_path',exceptions)),
                    untested_reasons=dict(Counter(re.findall(r'untested\s+([a-z_]+)',untested))),
                    first_hold_startpoint=re.search(r'Startpoint:\s+(\S+)',hold).group(1),
                    first_hold_endpoint=re.search(r'Endpoint:\s+(\S+)',hold).group(1)))
        (root/'TIMING_AUDIT.json').write_bytes((json.dumps(dict(archive_sha256=sha(a.audit),verified_members=len(index['files']),cases=audit),indent=2)+'\n').encode())
    def window(t,name):return next(x for x in t['power_windows'] if x['window']['name']==name)
    fused=next(t for t in tops if t['spec']['top']=='win512_g16_p1_o0_e0')
    staged=next(t for t in tops if t['spec']['top']=='win512_g16_p2_o0_e0')
    area_gain=1-fused['raw_cell_area_um2']/staged['raw_cell_area_um2']
    energy_gain=1-window(fused,'all')['energy_per_output_J']/window(staged,'all')['energy_per_output_J']
    lines=['# Attention采样控制：服务器DC/VCS/PT首轮结果','',
       '2026-10-28；Issue198 / PR199，负责人rayggxia。用户授权后在独立远端任务目录经Slurm执行，复用既有8个固定top。',
       '', '**本轮推荐G16融合准备、二进制赢家作为下一步hold修正的主候选。** '
       f'相对G16两级准备，映射面积减少{area_gain:.2%}，全1压力例每次输出地址的控制能量减少{energy_gain:.2%}。'
       '该结论限定当前库/约束/合成输入；所有候选均有hold违例，不能称时序签核、可制造最终PPA或整Attention最优。',
       '', '## 1 执行与验证','',
       '- DC O-2018.06-SP1、VCS O-2018.09-SP2、PT O-2018.06-SP1；同一SS SVT库1.08V/125°C，库SHA与此前本地映射相同。',
       '- 100MHz，输入slew0.1ns，输出0.02pF，setup uncertainty2ns、hold0.1ns；core边界IO delay0。未放宽原准备约束以隐藏违例。',
       f'- 58组轨迹分别核对RTL固定top与DC综合网表，共116项、{total_cycles}拍、{total_cycles*2}个P/C端口样本逐周期一致。三seed17/503/1009；含配置/输出/公平位等待、复位、零/单/多、保持/切换及rank cap。',
       '- 66个PT显式窗口已计算；每个窗口net及leaf cell活动覆盖均报告100%。赢家轨迹有PWR-981部分向量映射告警、PTE-003禁用时序弧提示，原件与消息代码完整保留。追加8top静态审计已核：禁用弧为propagated constant/conditional arc，未发现loop-breaking或用户false/multicycle例外；PWR-981仍待专项标注验收。',
       '- 厂商基本SVT模型，VCS未反标SDF，不关闭timing checks、不force notifier。功能一致是零延迟逻辑证据；PT为预布局averaged功耗，没有SPEF/CTS，不包含完整延迟毛刺。',
       '- 首个DC作业38437604因coin_mask先引用后声明失败；调整声明顺序后20项/90000拍原拒绝oracle复核通过。旧失败与执行v1/v2/v3不改。修正DC预检38437625、矩阵38437668；VCS/PT38437709/38437736，归档38437848。',
       '', '## 2 面积与时序','',
       '面积为DC标准单元面积，不是布局核心。按用户确认SHARK未缩几何，55nm折算面积=原值×0.81；不按55/65另算、不重复换算。功率/能量/时序保持真实仿真条件，未乘0.81。',
       '', '|top|原始面积 mm²|55nm折算 mm²|PT setup ns|PT hold ns|',
       '|---|---:|---:|---:|---:|']
    for t in tops:lines.append(f"|{t['spec']['top']}|{t['raw_cell_area_um2']/1e6:.6f}|{t['area_55nm_equivalent_um2']/1e6:.6f}|{t['setup_ns']:+.6f}|{t['hold_ns']:+.6f}|")
    lines += ['', '以上setup均为工具报告的非负值，提前保持版仅约0.000527ns，几乎没有裕量；hold最差约−0.114ns。'
       '这不是完整时序通过，升频也不能修复hold。追加诊断38437962显示各top最差hold都从rst_n输入开始：融合版经组合门到failed_reg，提前保持/拒绝版可直接到库单元RN脚。当前0最小输入延迟及0.1ns hold uncertainty使这些短路不满足；还存在其他输入hold路径，不能只把reset设false path就声称全部修复。下一步需明确真实reset/配置IO时序合同并补延迟/缓冲，在一致约束下重新STA；更高频率本轮未跑。TIMING_AUDIT.json保留禁用弧、untested原因和最短路径索引。',
       '', '## 3 赢家控制功耗与每次输出能量','',
       '全1是固定候选512路都为1的吞吐压力例，128输出+16burn；属于连续保持、并非128个独立有效样本。'
       '窗口从首帧接受前半拍至末输出消费后半拍，包含首尾流水，不含初始配置。M3为固定三活跃位且含实际rank拒绝。',
       '', '|赢家top|全1总功率 mW|全1 pJ/输出|M3 pJ/输出|时钟运行空闲 mW|',
       '|---|---:|---:|---:|---:|']
    for t in tops:
        if t['spec']['kind']!='winner':continue
        all_,three,idle=window(t,'all'),window(t,'three'),window(t,'idle_clock_running')
        lines.append(f"|{t['spec']['top']}|{all_['power']['total_W']*1e3:.3f}|{all_['energy_per_output_J']*1e12:.2f}|{three['energy_per_output_J']*1e12:.2f}|{idle['power']['total_W']*1e3:.3f}|")
    lines += ['', '三seed持续压力总功率、窗口/输出次数、internal/switching/leakage分项和完整输入/报告SHA见RESULTS.json。'
       '压力含复位/部分query失败，pJ/握手只能诊断，不能当每个成功query或同质量独立样本能量。',
       '', '融合准备保留较少DFF，当前理想时钟模型下空闲仍约1.356mW；时钟不停止时，寄存器时钟引脚内部功耗占大头。'
       'report_power的clock_network组已包含这些引脚内部功耗（i属性），不能在总功率上再加一次；本轮未实现或计量ICG/CTS。',
       '', '一热状态当前面积与能量均较大；提前保持可减少外供公平随机位，但控制自身面积增加、setup裕量明显缩小。'
       '上游随机源未在本边界计价，因此不能仅凭本表判定提前保持总能量是否更好。',
       '', '## 4 拒绝路径预取','',
       '相同逻辑proposal/校正硬币、128个相同输出地址；配置等待分别1/8拍。此输入分布与赢家压力不同，不作两算法质量匹配的横向能效比较。',
       '', '|拒绝top|配置等1拍总功率 mW|pJ/输出|配置等8拍 pJ/输出|空闲 mW|',
       '|---|---:|---:|---:|---:|']
    for t in tops:
        if t['spec']['kind']!='rejection':continue
        a,b,i=window(t,'mixed1'),window(t,'mixed8'),window(t,'idle_clock_running')
        lines.append(f"|{t['spec']['top']}|{a['power']['total_W']*1e3:.3f}|{a['energy_per_output_J']*1e12:.2f}|{b['energy_per_output_J']*1e12:.2f}|{i['power']['total_W']*1e3:.3f}|")
    lines += ['', '预取将该轨迹控制总拍减少64，控制内部pJ/输出约下降2%–3%，但公平bit从64增至128。'
       '这笔上游服务/比较/重配置成本未计，不能将内部微小收益宣布为完整拒绝采样器节能。按需仍为保守默认，预取为显式选项。',
       '', '## 5 证据、边界与后续','',
       '- 所有窗口使用同一次DC网表/SDC和其门级VCD，按SOURCE/manifest、网表、模型及原始报告SHA绑定。私有大网表、波形、库导出/厂商模型不进入Git。',
       '- 原字节和失败完整归档、下载/逐成员校验见work/rayggxia/198/EDA_ARCHIVE.json及EDA_COLLECTION_CHECK.json；未宣称本地已取得仍只在服务器的完整大包。',
       '- 本轮没有QK、概率源/比较器/阈值重编码、V访存/输出累加、SRAM、完整随机源分发或整Attention能量；没有模型/PPL、GPU或后布局验证。',
       '- 优先修复/明确hold与IO合同，审计PWR-981；PTE-003静态原因已检查，常量禁用/conditional检查仍保留原标注。随后同边界对G16融合和G32/两级做修正后对照，再决定提频/流水/时钟门控。不能直接用面积缩放系数推导功耗或频率。',
       '- 统一数字台账新增attention-control-198-eda-20261028，与此前v1/v2独立并存；STA状态写violations，功耗写calculated并保留告警。PR199待审不自动合并或关闭Issue。',
       '', '原始工具数值有限有效位；表格仅显示适合比较的精度。采样相关性/真实后训练Attention质量仍需原任务另行验证。','']
    (root/'RESULTS_ZH.md').write_bytes(('\n'.join(lines)).encode())
    print(json.dumps(dict(tops=len(tops),functional_cycles=total_cycles,power_windows=sum(len(t['power_windows']) for t in tops),area_reduction=area_gain,energy_reduction=energy_gain)))

if __name__=='__main__':main()
