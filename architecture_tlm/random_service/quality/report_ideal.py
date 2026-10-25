"""Build a standalone Chinese report from frozen results (Python 3.8+, matplotlib)."""
import argparse
import base64
import html
import io
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


NAMES = {'ideal':'理想读出', 'old':'旧比较器', 'iid':'合成 IID 对照',
         'lfsr32':'LFSR32 ×1', 'lfsr32_shared64':'共享 LFSR ×64', 'bivium':'Bivium ×20',
         'raw':'直通', 'vn':'VN'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('directory', type=Path)
    a = p.parse_args()
    read = lambda name: json.loads((a.directory/name).read_text(encoding='utf8'))
    stages, cases, audit = read('STAGES.json'), read('SUMMARY.json')['cases'], read('AUDIT.json')
    normal = [x for x in cases if x['source'] != 'duplicate']
    sel = lambda source,mode,kind: [x for x in normal if x['source']==source and x['mode']==mode and x['backend']==kind]
    fmt = lambda x: '—' if x is None else '{:.4f}'.format(x)
    def span(rows, fn, places=4):
        v = [fn(x) for x in rows]
        pattern = '{:.'+str(places)+'f}'
        return pattern.format(min(v))+'～'+pattern.format(max(v))
    def table(head, rows):
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(h)+'</th>' for h in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(c))+'</td>' for c in r)+'</tr>' for r in rows)+'</tbody></table></div>'
    charts = []
    def figure(fig, filename):
        fig.tight_layout()
        buf=io.BytesIO();fig.savefig(buf,format='svg',metadata={'Date':None});plt.close(fig)
        svg=buf.getvalue();(a.directory/filename).write_bytes(svg)
        charts.append('<img alt="'+filename+'" src="data:image/svg+xml;base64,'+base64.b64encode(svg).decode()+'">')
    fig, axes = plt.subplots(1,3,figsize=(14,4.6))
    groups = []
    for mode in ('raw','vn'):
        groups.append(('Input '+mode,[x['conditioned'] for x in stages if x['source']=='ideal' and x['mode']==mode]))
    for kind,label in [('lfsr32','LFSR1'),('lfsr32_shared64','GF64'),('bivium','Bivium20')]:
        for mode in ('raw','vn'):
            groups.append((label+' '+mode,[x['output']['first_lane'] for x in sel('ideal',mode,kind)]))
    for ax,key,title,target in zip(axes,('p','rho','var'),('P(bit=1)','Lag-1 correlation','T128 variance / IID(p)'),(.5,0,1)):
        for i,(label,values) in enumerate(groups):
            get = lambda v: v['p1'] if key=='p' else v['rho']['1'] if key=='rho' else v['windows']['128']['variance_over_iid_at_empirical_p']
            vals = [get(v) for v in values]
            ax.scatter(np.asarray(vals),i+np.linspace(-.14,.14,len(vals)),s=16,color='#087f8c' if i%2==0 else '#b56c2e',alpha=.8)
        ax.axvline(target,color='#718096',ls='--',lw=1)
        ax.set_yticks(range(len(groups)));ax.set_yticklabels([g[0] for g in groups],fontsize=9)
        ax.invert_yaxis();ax.set_title(title);ax.grid(axis='x',alpha=.2)
    figure(fig,'hierarchy.svg')
    fig,ax=plt.subplots(figsize=(12,3.5))
    for i,kind in enumerate(('lfsr32_shared64','bivium')):
        r=sel('ideal','raw',kind)[0]
        ax.bar(np.arange(16)+(i-.5)*.36,np.array(r['joint']['first_four_pattern_counts'])/4096,width=.36,label=NAMES[kind].replace('共享 LFSR ×64','GF64').replace('Bivium ×20','Bivium20'))
    ax.axhline(1/16,ls='--',color='#9b3333',label='Four independent fair bits: 1/16')
    ax.set_xticks(range(16));ax.set_xticklabels([format(i,'04b') for i in range(16)])
    ax.set_ylabel('Pattern frequency');ax.set_xlabel('First four q128 bits (seed32003, boot0, raw)');ax.legend(loc='upper right',fontsize=8)
    figure(fig,'joint_patterns.svg')
    stage_rows=[]
    for source in ('ideal','old','iid'):
        for mode in ('raw','vn'):
            s=[x for x in stages if x['source']==source and x['mode']==mode]
            stage_rows.append([NAMES[source],NAMES[mode],span(s,lambda x:x['conditioned']['n'],0),
                span(s,lambda x:100*x['retained_ratio'],2)+'%',span(s,lambda x:x['conditioned']['p1']),
                span(s,lambda x:x['conditioned']['rho']['1']),span(s,lambda x:x['conditioned']['windows']['128']['variance_over_iid_at_empirical_p'],3)])
    digital_rows=[]
    timing_rows=[]
    for kind in ('lfsr32','lfsr32_shared64','bivium'):
        for mode in ('raw','vn'):
            r=sel('ideal',mode,kind)
            digital_rows.append([NAMES[kind],NAMES[mode],span(r,lambda x:x['output']['first_lane']['p1']),
                span(r,lambda x:x['output']['first_lane']['rho']['1']),
                span(r,lambda x:x['output']['first_lane']['windows']['128']['variance_over_iid_at_empirical_p'],3),
                span(r,lambda x:x['probes']['and_measured']),span(r,lambda x:x['probes']['endpoint_first_word_match'])])
            timing_rows.append([NAMES[kind],NAMES[mode],str(r[0]['bus_bits']),span(r,lambda x:x['first_output_us'],2),
                span(sel('old',mode,kind),lambda x:x['first_output_us'],2)])
    joint_rows=[]
    for source in ('ideal','old','iid'):
        for kind in ('lfsr32_shared64','bivium'):
            r=sel(source,'raw',kind)
            joint_rows.append([NAMES[source],NAMES[kind],span(r,lambda x:x['joint']['first_four_q128_xor_one_fraction']),
                str(r[0]['sparse_proposal']['q']),span(r,lambda x:x['sparse_proposal']['one_hit_rate']),
                fmt(r[0]['sparse_proposal']['iid_one_hit_reference'])])
    all_rows=[]
    for r in cases:
        all_rows.append([r['case_id'],fmt(r['output']['first_lane']['p1']),fmt(r['output']['first_lane']['rho']['1']),
                        fmt(r['probes']['and_measured']),fmt(r['joint']['first_four_q128_xor_one_fraction']),'{:.2f}'.format(r['first_output_us'])])
    body='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>理想读出下的分层随机质量 · 2026-10-25</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f5f5;color:#172d36;font:16px/1.75 "Microsoft YaHei",sans-serif}main{max-width:1180px;margin:auto;padding:40px 28px}h1{font-size:32px;line-height:1.3}h2{font-size:23px;margin-top:0}h3{font-size:18px}p{margin:12px 0}.eyebrow{color:#087f8c;font-size:13px;font-weight:bold;letter-spacing:.08em}.lead{font-size:19px;max-width:930px}.box{background:white;border:1px solid #dae1e3;border-radius:12px;padding:24px;margin:24px 0}.note{border-left:4px solid #b56c2e;background:#fff7ec;padding:14px 18px}.flow{display:flex;flex-wrap:wrap;gap:12px;align-items:center}.node{padding:14px;background:#eaf4f4;border-radius:8px;font-size:15px}.muted{color:#526a75;font-size:14px}table{border-collapse:collapse;min-width:690px;width:100%;font-size:14px}th,td{padding:10px 12px;border-bottom:1px solid #e2e8eb;text-align:left}th{background:#edf3f4;white-space:nowrap}.scroll{overflow:auto}img{width:100%;height:auto}code{font-family:Consolas,monospace;font-size:13px;overflow-wrap:anywhere}summary{cursor:pointer;font-weight:bold}a{color:#087f8c}li{margin:8px 0}.tag{display:inline-block;background:#e2eff0;color:#087f8c;padding:3px 9px;border-radius:6px;margin:3px;font-size:13px}@media(max-width:600px){main{padding:22px 14px}.box{padding:17px}h1{font-size:26px}.lead{font-size:17px}}
</style><main><div class="eyebrow">RNG / ISSUE95 / 2026-10-25</div><h1>理想比较器假设下，质量怎样沿随机源层级变化？</h1>
<p class="lead">单路偏置和自相关接近理想后，仍要检查并行输出的联合关系。本轮最明确的发现是：<b>共享 64 路 LFSR 的固定联合关系不因更换物理种子而消失。</b></p>
<span class="tag">225 / 225 完成</span><span class="tag">3 条物理噪声轨迹</span><span class="tag">1 µs 原始采样</span><span class="tag">每端点 4096 帧</span><span class="tag">无新 Spectre / RTL / PPA</span>
<section class="box"><h2>1 · 这一轮实际模拟了什么</h2><div class="flow"><div class="node">已有 core_V 波形<br>软件阈值 0.6 V → bit</div><b>→</b><div class="node">直通 / VN 候选调理<br>保留原始样本时间</div><b>→</b><div class="node">32-bit 种子字<br>串行分给两个独立端点</div><b>→</b><div class="node">LFSR / GF64 / Bivium<br>R8 → q/256 比较 → bit</div></div>
<p>三条 Spectre 噪声 seed 为 32003、32009、32027；各 20,000 个固定相位样本，时间 2 ms～21.999 ms。理想读出是对<b>仍挂接旧比较器负载的核心电压</b>作阈值判断，未仿真实际理想比较器器件，也不是无负载核心。</p>
<p>同一波形的旧比较器输出以 0.4 V 阈值采样，MID 不删除，分别保留 1089 / 1145 / 1115 个 MID 样本。另加入三个 PCG64 合成 IID 统计对照，以及九个故意重复种子的故障对照。合成对照不是物理熵。</p>
<p>每条记录分成四个固定、不重叠的 5000-bit 窗口，各冷启动两个端点。216 个主案例＝3 输入 ×3 seed ×2 调理 ×3 后端 ×4 启动窗口；加 9 个重复种子对照。四窗口来自同一物理轨迹，<b>不能当作四条独立物理 seed</b>，也不拼接启动段计算自相关。</p>
<div class="note">这是单路物理记录向两个数字端点依次播种的条件实验；未提供物理阵列多源同时采样的空间相关性。默认换种仍为 10⁸ 拍，在 100 MHz 为 1 s，本轮不触发周期换种。四次冷启动不冒充四次实际周期换种。</div></section>
<section class="box"><h2>2 · 物理 bit → 调理 → 种子字</h2><p>下表范围为三个物理／合成 seed 分别计算后的最小值～最大值。P1 为 1 的比例；ρ₁ 为序列相邻项相关；V128 为不重叠 128-bit 块均值方差除以 p(1−p)/128。V128 接近 1 只是有限样本诊断。</p>'''
    body+=table(['输入','调理','输出 bit 数','保留率','P1','ρ₁','V128'],stage_rows)
    body+='''<p>理想输入自身的 ρ₁ 为 −0.0037～0.0101，但 V128 为 1.208～1.596，提示仍须关注较长窗口的相关／漂移结构，不能只看 lag1。VN 后保留约四分之一，P1 接近 0.5；ρ₁ 仍有 −0.0322 的一条记录，不能认定所有指标必然改善。</p>
<p>旧比较器原始 ρ₁ 约 0.50；VN 后偏置减小，但变为 −0.236～−0.187 的负相关，保留率仅约 12%。这说明 VN 在相关输入上不保证 IID。其 V128 低于 1 反映负相关结构，也不能称物理熵增加。</p>
<p><b>打包／分发不会净化 bit。</b>32-bit 字按原顺序装配，审计逐 bit 一致；仅末尾不足 32 bit 不发送。完整调理流与真正装入端点的短前缀分别记录。每端点 LFSR 使用 32 状态 bit；Bivium 传输 192 bit、装入 177 bit、丢弃 15 个填充位置。</p>
<p class="muted">原始 ρ₁ 对应 1 µs；VN 的 ρ₁ 对应相邻保留项，其物理间隔不固定。PRNG 的 ρ₁ 对应 10 ns 帧间隔。这三者不能画成同一物理频率的相关性衰减曲线。</p></section>
<section class="box"><h2>3 · 本地 PRNG → 概率输出</h2><p>图中只使用理想输入：原始／VN 各 3 个点，数字输出各 12 个冷启动点。数字统计取端点 a 第一 lane 的 q=128 输出。点数、记录长度和物理时间轴不同；虚线是参考值，不是通过门槛。</p>'''
    body+=charts[0]+table(['后端','种子路径','输出 P1','输出 ρ₁','输出 V128','两端点 AND 概率','首字相同比例'],digital_rows)
    body+='''<p>AND 探针使用端点 a 的 q=64 和 b 的 q=192，独立参考为 0.1875。若非法复用同一随机字，理论变成 0.25。各端点使用不同种子材料时，当前有限样本的边缘统计总体接近参考；这不构成独立性或物理熵证明。</p>
<p>9 个重复种子对照中，两端点每帧输出均完全一致。即使每路单独的 P1 很好，也无法满足需要相互独立的乘法输入。种子分配与消费者相关性约束是必要接口。</p></section>
<section class="box"><h2>4 · 两两相关小，仍不代表多路独立</h2><p>GF64 的前四路 q128 bit 存在精确关系 b₀⊕b₁⊕b₂⊕b₃=0。独立公平 bit 的奇偶为 1 的概率应为 0.5；本轮所有 GF64 案例都为 0。下图展示一个启动窗口的 16 种模式。</p>'''
    body+=charts[1]+table(['种子源','后端','前四路 XOR=1','稀疏阈值 q','恰好一路命中','IID 参考'],joint_rows)
    body+='''<p>稀疏探针取 q≈256/路数，使独立情形期望命中约一路：64 路用 q=4，20 路用 q=13。理想直通输入下，GF64 的恰好一路命中率约 0.685～0.706，明显偏离 IID 参考 0.371；Bivium 约 0.362～0.396，对应参考 0.377。这里只测这一特定联合事件，不能泛化为所有任务的优劣。</p>
<div class="note">共享 GF64 可继续作为有明确相关性合同的专用源，但不能宣称 64 路联合 IID。更好的种子、增加物理熵源或慢速换种都不会去掉这个固定映射关系。需要 IID 假设的 OR／稀疏选择，应在真实消费者上检查或更换映射／后端。</div>
<p class="muted">完整 JSON 保留历史 q=64 proposal 探针，但其 64 路恰好一路命中的 IID 概率仅约 2×10⁻⁷，4096 帧不足以判断，本报告不据此下结论。64 路和 20 路的最大两两相关也不直接排名；测试对数分别为 2016 和 190，另保留相同前四路的 6 对相关。</p></section>
<section class="box"><h2>5 · 质量处理的代价：种子收集时间</h2><p>下表为本轮顺序播种两个端点后，<b>两端点同步接收第一帧请求</b>的时间，自窗口起点计，单位 µs；未计此前模拟电路启动／2 ms 丢弃段。响应消费再晚一拍。传输字仅在最后组成 bit 到达后，附加 1 拍理想收集／CDC 延迟；该延迟是模型假设，未实现 CDC 电路。</p>'''
    body+=table(['后端','调理','两个端点总线 bit','理想读出启动 µs','旧比较器启动 µs'],timing_rows)
    body+='''<p>理想输入下，两个 LFSR 端点直通启动约 63.03 µs，VN 后约 213～275 µs；两个 Bivium 端点直通约 383.08 µs，VN 后约 1461～1617 µs。Bivium 含 5 个预热帧共 800 次递推。生成阶段持续 4096 帧、约 40.96 µs，本地输出不要求物理源同步输出等量 bit。</p>
<p>1 µs 原始采样对应 1 Mbit/s，理想 VN 实际约 249～252 kbit/s；这属于候选调理后的序列速率，未经健康检测及熵评估，不能当作可认证熵率。模型计入等待、总线、状态装入、预热、递推、比较器和消费操作；本轮面积／能量均保持未知。</p></section>
<section class="box"><h2>6 · 对当前分层架构的判断与待补项</h2><ul>
<li>物理源→低速采种→本地高速 PRNG 的分层机制在本轮模型中可执行，种子时间和输出统计可追溯；直通与 VN 应保留为候选方案，暂不依据这一轮永久固定调理方式。</li>
<li>PRNG 能改变有限序列的可见统计结构，却不增加初始种子的物理熵。上层结果正常不能证明下层健康；重复种子对照已直接说明这一点。</li>
<li>原始输入来自 TT、25°C、noisefmin=500 Hz / noisefmax=100 MHz、maxstep=2.5 ns 的既有 Spectre 作业 38380128。它不是慢漂移/PVT/失配/并行串扰验收。后续实际比较器数据到齐后，保持同一时间戳协议替换输入再对比。</li>
<li>本轮采样间隔是 1 µs，不是 0.1 ms。20 ms 记录若抽到 0.1 ms 只剩约 200 点，不能据本报告确认该间隔的高精度相关性或 1 s 换种表现。</li>
<li>只运行局部合成 AND、共享输入 toy reduction、稀疏选择与联合模式探针；没有完整 FFN/Attention/LLM 精度结果，也没有新 RTL、综合、STA、PT 或硅片测量。</li></ul></section>
<section class="box"><h2>7 · 可复现材料</h2><p>执行源码冻结于 <code>bdbab3e38ff56e267783af9ac327dbba67a0e169</code>，5 个执行文件 SHA 绑定；增强验证测试及本报告为之后的独立后处理。6 项时序／有限源测试通过；'''+str(audit['checks'])+''' 项文件、时序、种子、操作计数与数值审计通过。</p>
<p>原始输入：<code>analog_pbit_20261016/ideal_and_old_20000_v1</code>；225 份 NPZ 与完整 JSON 保存在 <code>project_archives/rng_ideal_quality_20261025</code>。仓库保存 CONFIG、SOURCE_MANIFEST、INPUT_MANIFEST、STAGES、SUMMARY、AUDIT、ARCHIVE_INDEX；SHA 与本机路径见索引。远端读者仍需相应原始存储访问权限。</p>
<p class="muted">P1 在独立近似下的单次 95% 抽样尺度：N=20,000 时约 ±0.0069，N=4096 时约 ±0.0153；自相关、多个指标与多次比较会改变解释，因此本报告不给出统一“随机性合格”标签。STAGES 的 marginal_min_entropy_only 只是边缘概率诊断，禁止当作熵率。</p>
<details><summary>展开全部 225 个案例的关键数值</summary>'''+table(['案例','输出 P1','ρ₁','AND','四路 XOR=1','首请求 µs'],all_rows)+'''</details></section>
<footer class="muted">2026-10-25 · Issue95 · 条件模型与有限样本诊断；原始结果保留，不覆盖 2026-10-23 的旧协议。</footer></main></html>'''
    (a.directory/'REPORT.html').write_bytes(body.encode('utf8'))
    print('report generated: '+str(a.directory/'REPORT.html'))


if __name__ == '__main__':main()
