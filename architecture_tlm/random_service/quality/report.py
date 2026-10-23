"""Build scientific figures and a self-contained Chinese evidence report.

Postprocessing only; Python 3.8 + NumPy + matplotlib is sufficient.
"""
import argparse, base64, hashlib, html, json, shutil
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

NAMES={'bare':'裸源理想判决','buffers_x2':'旧比较器A','b1_p2_b2_n2':'旧比较器B',
       'iid_fixture':'IID合成对照','biased_markov':'偏置＋相关合成','duplicate_seed_control':'重复种子故障'}
KINDS={'lfsr32':'LFSR32','lfsr32_shared64':'LFSR＋GF64','bivium':'Bivium'}


def dump(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def avg(v):return float(np.mean(v))
def spread(v):return '{:.4f}～{:.4f}'.format(min(v),max(v))
def table(headers,rows):
    return '<table><thead><tr>'+''.join('<th>'+html.escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(c)+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table>'


def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--delivery',type=Path,required=True)
    p.add_argument('--archive',type=Path,required=True);a=p.parse_args()
    r=json.loads((a.results/'RESULTS.json').read_text(encoding='utf-8'))
    s=json.loads((a.results/'STAGES.json').read_text(encoding='utf-8'))
    audit=json.loads((a.results/'AUDIT.json').read_text(encoding='utf-8'))
    rows=r['cases'];complete=[x for x in rows if x['status']=='complete']
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'svg.fonttype':'none','font.size':10})
    fig,axs=plt.subplots(1,3,figsize=(13.5,3.8),layout='constrained')
    physical_table=[]
    for name in ('bare','buffers_x2','b1_p2_b2_n2'):
        xx=[];pp=[];rr=[];vv=[]
        for dt in (1e-7,5e-7,1e-6,2e-6):
            data=[x['metrics'] for x in s['physical_sampling'] if x['key'].startswith(name+'_') and x['interval_s']==dt]
            xx.append(dt*1e6);pp.append(avg([x['p1'] for x in data]));rr.append(avg([x['rho']['1'] for x in data]))
            vv.append(avg([x['windows']['32']['variance_over_iid_at_empirical_p'] for x in data]))
            physical_table.append([NAMES[name],str(dt*1e6)+' µs',spread([x['p1'] for x in data]),
                spread([x['rho']['1'] for x in data]),spread([x['windows']['32']['variance_over_iid_at_empirical_p'] for x in data])])
        for ax,v in zip(axs,(pp,rr,vv)):ax.plot(xx,v,marker='o',label=NAMES[name]);ax.set_xscale('log');ax.set_xlabel('同一通道采样间隔 / µs');ax.grid(alpha=.2)
    for ax,label in zip(axs,('P(1)','相邻采样相关系数 ρ(1)','T32均值方差 / IID参照')):ax.set_ylabel(label)
    axs[0].axhline(.5,color='gray',ls='--',lw=1);axs[1].axhline(0,color='gray',ls='--',lw=1);axs[2].axhline(1,color='gray',ls='--',lw=1)
    axs[0].legend();fig.suptitle('物理读出路径：三组噪声种子的均值；不是同一噪声轨迹的串接实验')
    fig.savefig(a.results/'physical-quality.svg');fig.savefig(a.results/'physical-quality.png',dpi=140);plt.close(fig)
    fig,axs=plt.subplots(1,3,figsize=(13.5,3.7),layout='constrained')
    names=('bare','buffers_x2','b1_p2_b2_n2','iid_fixture','biased_markov');x=np.arange(len(names))
    for ax,kind in zip(axs,KINDS):
        for mode,shift in [('raw',-.18),('vn',.18)]:
            values=[];err=[]
            for name in names:
                data=[z['output']['first_lane']['bias']*100 for z in complete if z['source']==name and z['backend']==kind and z['conditioner']==mode and z['reseed_cycles']==0]
                values.append(avg(data));err.append([avg(data)-min(data),max(data)-avg(data)])
            ax.bar(x+shift,values,width=.34,label='直接种子' if mode=='raw' else 'VN候选种子',yerr=np.array(err).T,capsize=3)
        ax.axhline(0,color='gray',lw=1);ax.set_xticks(x,[NAMES[n] for n in names],rotation=35,ha='right')
        ax.set_title(KINDS[kind]);ax.set_ylabel('第1路q=128输出偏差 / 百分点');ax.grid(axis='y',alpha=.2)
    axs[0].legend();fig.suptitle('本地PRNG：每端点4096帧，仅启动播种；误差线为三seed范围，不是置信区间')
    fig.savefig(a.results/'digital-quality.svg');fig.savefig(a.results/'digital-quality.png',dpi=140);plt.close(fig)
    stage_table=[]
    for name in names:
        rr=[x for x in s['conditioning'] if x['source']==name and x['conditioner']=='vn']
        stage_table.append([NAMES[name],spread([x['raw']['p1'] for x in rr]),spread([x['raw']['rho']['1'] for x in rr]),
            spread([x['conditioned']['p1'] for x in rr]),spread([x['conditioned']['rho']['1'] for x in rr]),
            spread([100*x['retained_ratio'] for x in rr])+'%'])
    compact=[]
    for z in rows:
        c={k:z[k] for k in ('case_id','source','seed','evidence','conditioner','backend','reseed_cycles','status','duplicate_seed')}
        c.update(seed_stats=z['seed_stats'],raw_artifact=z['raw_artifact'])
        if 'output' in z:
            c.update(p1=z['output']['first_lane']['p1'],rho1=z['output']['first_lane']['rho']['1'],
                max_lane_rho=z['output']['max_abs_same_cycle_lane_rho'],
                worst_cdf=z['output']['worst_lane_cdf_error'],and_error=z['probes']['and_error'],
                endpoint_rho=z['probes']['endpoint_first_bit_rho'],ffn_toy=z['probes']['ffn_toy'])
        compact.append(c)
    dump(a.results/'SUMMARY.json',dict(cases=compact,source_manifest_sha256=r['source_manifest_sha256'],
        config_sha256=r['config_sha256'],source_local_execution_commit='8a862a3',complete=len(complete),total=len(rows)))
    def embed(name):return '<img alt="随机质量测量曲线" src="data:image/svg+xml;base64,'+base64.b64encode((a.results/name).read_bytes()).decode()+'">'
    overview=table(['层级','测量对象','本轮覆盖'],[
        ['物理输出','P1、ρ(k)、T32/T128窗口方差','复用9条Spectre轨迹；100ns～2µs抽样'],
        ['候选调理','偏置、输出序列相关性、保留率','直通与Von Neumann；没有新硬件/健康认证'],
        ['种子分发','实际包、重复状态、零种子拒绝','两个端点，32bit握手，完整随机网络'],
        ['本地PRNG','8bit分布、13档概率响应、时间/跨路相关','LFSR32 / GF64 / Bivium，0与1024拍换种'],
        ['计算使用端','AND偏差、K32共享输入玩具点积、候选帧','局部合成探针；不是完整FFN或LLM验收']])
    detail_rows=[[c['case_id'],f"{c.get('p1',float('nan')):.4f}",f"{c.get('rho1',float('nan')):.4f}",
                  f"{c.get('worst_cdf',float('nan')):.4f}",f"{c.get('and_error',float('nan')):.4f}",c['seed_stats']['loads']] for c in compact]
    h='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>随机质量沿层级变化：首轮实测回放</title><style>body{font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif;color:#20313d;background:#f5f7f9;margin:0}main{max-width:1120px;margin:auto;padding:28px}h1{font-size:28px}h2{font-size:21px;margin-top:34px}img{width:100%;background:white}table{width:100%;border-collapse:collapse;font-size:14px}td,th{border-bottom:1px solid #c8d3dc;text-align:left;padding:9px;overflow-wrap:anywhere}th{background:#e8eff4}.notice{padding:14px 18px;border-left:4px solid #b8791c;background:#fff3df}.scroll{overflow-x:auto}code{overflow-wrap:anywhere}a{color:#245e9b}details{margin-top:20px}li{margin:8px 0}@media(max-width:600px){main{padding:15px}table{font-size:12px}img{min-width:650px}}</style><main>'''
    h+='<p>Issue95 · 2026-10-23 · 现有源码不改，质量诊断另行输出</p><h1>随机数看起来均匀，不代表各路可以任意组合</h1>'
    h+='<p>已完成189个端到端案例，每个案例两个本地端点、各4096帧；每种输入使用401/503/607三组seed。另有36项物理路径/采样间隔诊断、30项调理对照和1269项原件/算术/结构复核。</p>'
    h+='<div class="notice"><strong>三个核心发现：</strong><ol><li>旧比较器的时间相关明显高于裸源；VN去偏后仍有相关，不能仅凭P1接近50%验收。</li><li>GF64在q=128时，输出第0、1、2、3路始终满足 b₀⊕b₁⊕b₂⊕b₃=0；本轮全部相关案例均复现。两两相关小，不等于联合独立。</li><li>两个端点用同一个种子且按同一更新序列运行，三个后端都输出完全相同；PRNG不会修复种子复制错误。</li></ol></div>'
    h+='<h2>怎么沿层级测量</h2>'+overview
    h+='<p>物理底层不逐拍供应计算随机字；它缓慢提供种子。本次把既有物理记录预先收集，再按现有种子接口回放，便于隔离质量传播。种子可用率设置为1字/数字拍，仅是质量实验设置，不是模拟阵列吞吐实测。1024拍是加速换种压力测试，0仅启动；没有将1亿拍跑满，也没有据此选定最佳换种周期。</p>'
    h+='<h2>物理源与比较器：先看时间相关</h2><div class="scroll">'+embed('physical-quality.svg')+'</div><p>9条记录来自同一已核验归档38237164，保留2ms～20ms。裸源以0.6V理想判决，旧比较器输出以0.4V判决；三种电路分别仿真，不是同一次物理噪声轨迹的逐级因果对照，也不是多通道同时采集。新共享高速比较器结果未纳入。</p>'+table(['路径','间隔','P1范围','ρ₁范围','T32方差/IID'],physical_table)
    h+='<h2>VN候选调理：去偏不等于去相关</h2>'+table(['输入','原P1','原ρ₁','VN后P1','VN后ρ₁','保留率'],stage_table)
    h+='<p>物理路径此表统一0.5µs抽样。VN将不重叠01/10对分别映射0/1，丢弃00/11；经典无偏结论依赖输入条件，不能直接套到任意相关物理源。输出的相邻bit是按有效输出序号排序，间隔可变。保留率是bit数比例，不是已经测出的吞吐或能效。当前共享种子入口没有这块调理RTL；这里仅比较候选算法。</p>'
    h+='<h2>本地扩展与Bernoulli比较</h2><div class="scroll">'+embed('digital-quality.svg')+'</div><p>许多PRNG输出的边缘偏差看起来较小，但这没有增加物理熵。有限样本、不同通道数和多重比较会影响最大偏差/相关系数，不能把图当作后端排名或质量通过证明。13个阈值q∈[0,256]按q/256检查；q=0/256必须精确为0/1。真实sigmoid还包含驱动/LUT量化，本轮没有完成其全链误差认证。</p>'
    h+='<h2>联合相关与计算误差</h2><p>GF64的q=128帧只有至多32维异或差分秩，且前4路存在上述严格关系。换种也不会改变固定线性映射的这个约束。Bivium本轮未显示这一条GF关系，但不代表证明其全部高阶/跨时独立。</p><p>AND探针取pₓ=0.25、pᵥ=0.75：独立目标0.1875；同一个随机字广播给两个比较器时目标变成0.25。测试同时报告实际误差。当前FFN是允许单字共享的K32分层输入编码，不能因此禁止其合法共享；其64输入W8玩具点积仅作局部敏感性探针，不能外推完整FFN/PPL。</p>'
    h+='<h2>目前能决定什么</h2><ul><li>调理验收同时看偏置、时间相关、有效输出率；简单VN不能直接作为当前旧比较器的合格种子方案。</li><li>GF64按用途限制共享；要求全候选联合独立的模块不能只凭两两检查放行。</li><li>分发器应防止意外重复种子/重放，保留epoch与端点审计；“重新加载”不自动意味着新随机性。</li><li>继续接入同时采集的真实多路阵列记录，扫描跨行/列共模、Vref/PVT、不同播种间隔和更长输出；完整Attention及模型质量仍需单独评估。</li></ul>'
    h+='<details><summary>展开全部189个案例</summary><div class="scroll">'+table(['案例','P1(第1路)','ρ₁(第1路)','最坏路CDF差','AND误差','种子装载'],detail_rows)+'</div></details>'
    h+='<h2>来源与复现</h2><p>执行源码本地commit 8a862a3；8文件SOURCE_MANIFEST绑定准确字节，基线6966739a。原件、NPZ和逐层摘要均有SHA；中央数字电路台账以DESIGN_PROOF/功能诊断登记，无新RTL、综合、STA、功耗或硅片实测。</p><p>本轮没有运行NIST熵估计/认证、重启矩阵、全部统计套件或长周期搜索。边缘最小熵字段仅由P1计算，不是熵率。参考：<a href="https://csrc.nist.gov/pubs/sp/800/90/b/final">NIST SP800-90B</a>区分熵源及其调理与验证；<a href="https://csrc.nist.gov/pubs/sp/800/22/r1/upd1/final">SP800-22</a>明确统计检验不能单独认证发生器。</p></main></html>'
    (a.results/'REPORT.html').write_text(h,encoding='utf-8')
    a.delivery.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(a.results/'REPORT.html',a.delivery)
    a.archive.mkdir(parents=True,exist_ok=True)
    for name in ('RESULTS.json','CONFIG.json','SOURCE_MANIFEST.json','STAGES.json','AUDIT.json','PHYSICAL_INPUT.json','SUMMARY.json'):
        target=a.archive/name
        if target.exists() and target.read_bytes()!=(a.results/name).read_bytes():raise ValueError('immutable archive changed')
        shutil.copyfile(a.results/name,target)
    dump(a.results/'ARCHIVE_INDEX.json',dict(full_results=dict(path=str(a.archive/'RESULTS.json'),sha256=sha(a.archive/'RESULTS.json'),bytes=(a.archive/'RESULTS.json').stat().st_size),
        digital_raw_files=len(rows),physical_raw_records=9,delivery=dict(path=str(a.delivery),sha256=sha(a.delivery))))
    print(json.dumps(dict(cases=len(rows),html_bytes=a.delivery.stat().st_size,output=str(a.delivery)),ensure_ascii=True))

if __name__=='__main__':main()
