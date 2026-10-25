"""Scientific figures, exact-data tables and a standalone Chinese report. Python3.8+."""
import argparse
import base64
import csv
import hashlib
import html
import io
import json
import zipfile
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--archive',type=Path,required=True);a=p.parse_args()
    read=lambda n:json.loads((a.directory/n).read_text(encoding='utf8'))
    cases=read('SUMMARY.json')['cases'];layers=read('LAYERS.json');cfg=read('CONFIG.json');audit=read('AUDIT.json')
    physical=[c for c in cases if c['source']=='physical']
    names={'lfsr32':'LFSR32','lfsr32_shared64':'GF64','bivium':'Bivium'}
    def lane(i,c):return ('a' if i<c['lanes_per_instance'] else 'b')+str(i%c['lanes_per_instance'])
    def where(v,c):
        if v is None:return '—'
        d=v['location'];label=lane(d['lane'],c) if 'lane' in d else lane(d['lane_i'],c)+'→'+lane(d['lane_j'],c)
        return label+' / k='+str(d['lag'])
    def val(v):return '—' if v is None else '{:.6f}'.format(v['rho'])
    def cell(v,c):return val(v)+(' ['+where(v,c)+']' if v else '')
    def table(headers,rows):return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(s)+'</th>' for s in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    def csvtext(header,rows):
        f=io.StringIO(newline='');w=csv.writer(f,lineterminator='\n');w.writerow(header);w.writerows(rows);return f.getvalue()
    def artifact(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    def writejson(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
    allrows=[];data=[]
    for c in cases:
        for feature in ['word']+['q'+str(q) for q in cfg['thresholds']]+['bit'+str(k) for k in range(8)]:
            s=c['stats'][feature]
            m=[s['temporal_lag1'],s['temporal'],s['spatial']['within_instance']['same_cycle'],s['spatial']['between_instances']['same_cycle'],s['spatial']['within_instance']['lagged'],s['spatial']['between_instances']['lagged']]
            allrows.append([c['case_id'],feature]+[cell(v,c) for v in m])
            for metric,v in zip(['temporal_lag1','temporal_all','within_same_cycle','between_same_cycle','within_lagged','between_lagged'],m):
                data.append(dict(case_id=c['case_id'],feature=feature,metric=metric,**(v or dict(rho=None,abs=None,location=None,tests=0))))
    writejson(a.directory/'PEAKS.json',data)
    (a.directory/'PEAKS.csv').write_bytes(csvtext(['case','feature','lag1','temporal max','within same cycle','between same cycle','within lagged','between lagged'],allrows).encode('utf8'))
    # CSVs contain every physical-case lane / lag / pair. NPZ remains full-precision source.
    zpath=a.archive/'rng_correlation_20261025_tables.zip'
    with zipfile.ZipFile(zpath,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr('README_ZH.txt','每个物理case有两个实例a/b，lane从0编号。lag单位为10ns帧；cross[i,j,k]=Corr(i(t),j(t+k))。CSV为12有效数字，matrices.npz保留float64。合成对照全部峰值在PEAKS.csv，完整对照矩阵在归档。三个物理seed是独立仿真，不是同时空间通道。\n')
        z.write(a.directory/'PEAKS.csv','PEAKS.csv');z.write(a.directory/'LAYERS.json','LAYERS.json')
        for c in physical:
            path=next(Path(x['path']) for x in c['artifacts'] if Path(x['path']).name=='matrices.npz')
            with np.load(path) as arrays:
                for feature in ['word']+['q'+str(q) for q in cfg['thresholds']]+['bit'+str(k) for k in range(8)]:
                    t=arrays[feature+'_acf'];s=arrays[feature+'_cross'];labels=[lane(i,c) for i in range(t.shape[1])]
                    f=io.StringIO();np.savetxt(f,np.column_stack([cfg['temporal_lags'],t]),delimiter=',',fmt='%.12g',header='lag,'+','.join(labels),comments='')
                    z.writestr(c['case_id']+'/'+feature+'_temporal.csv',f.getvalue())
                    lags=cfg['spatial_lags'] if not feature.startswith('bit') else [0]
                    for ki,k in enumerate(lags):
                        f=io.StringIO();np.savetxt(f,np.column_stack([np.arange(s.shape[1]),s[ki]]),delimiter=',',fmt='%.12g',header='row_lane_index,'+','.join(labels),comments='')
                        z.writestr(c['case_id']+'/'+feature+'_space_lag'+str(k)+'.csv',f.getvalue())
                    if feature!='word':
                        f=io.StringIO();lens=[8,16,32,64,128]
                        mat=np.column_stack([np.arange(t.shape[1]),arrays[feature+'_mean']]+[arrays[feature+'_varratio_'+str(k)] for k in lens]+[arrays[feature+'_mse_'+str(k)] for k in lens])
                        np.savetxt(f,mat,delimiter=',',fmt='%.12g',header='lane_index,p1,'+','.join('variance_ratio_T'+str(k) for k in lens)+','+','.join('mse_T'+str(k) for k in lens),comments='')
                        z.writestr(c['case_id']+'/'+feature+'_windows.csv',f.getvalue())
                f=io.StringIO();np.savetxt(f,arrays['cdf_error'],delimiter=',',fmt='%.12g')
                z.writestr(c['case_id']+'/cdf_error_rows_lanes_columns_q1to256.csv',f.getvalue())
            transport=next(Path(x['path']) for x in c['artifacts'] if Path(x['path']).name=='TRANSPORT.json')
            z.write(transport,c['case_id']+'/TRANSPORT.json')
    figures=[]
    def savefig(fig,name):
        f=io.BytesIO();fig.savefig(f,format='svg',bbox_inches='tight',metadata={'Date':None});plt.close(fig)
        (a.directory/name).write_bytes(f.getvalue());figures.append('<img alt="'+name+'" src="data:image/svg+xml;base64,'+base64.b64encode(f.getvalue()).decode()+'">')
    chosen=[next(c for c in physical if c['backend']==kind and c['physical_seed']==32003 and c['mode']=='raw') for kind in names]
    fig,axes=plt.subplots(1,3,figsize=(14,3.8))
    for ax,c in zip(axes,chosen):
        control=next(x for x in cases if x['case_id']=='iid-'+c['case_id'])
        for label,item,color in [('Physical seed',c,'#047b83'),('Matched IID',control,'#b6722b')]:
            path=next(Path(x['path']) for x in item['artifacts'] if Path(x['path']).name=='matrices.npz')
            with np.load(path) as z:ax.plot(cfg['temporal_lags'][:128],np.max(abs(z['q128_acf'][:128]),axis=1),label=label,color=color,lw=1)
        ax.set_title(names[c['backend']]+' / '+str(2*c['lanes_per_instance'])+' lanes');ax.set_xlabel('Lag in output frames (10 ns)');ax.set_ylabel('Max lane |ACF|, q128');ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.tight_layout();savefig(fig,'all_lane_acf.svg')
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    for ax,c in zip(axes,chosen):
        path=next(Path(x['path']) for x in c['artifacts'] if Path(x['path']).name=='matrices.npz')
        with np.load(path) as z:m=z['q128_cross'][0].copy()
        np.fill_diagonal(m,np.nan);im=ax.imshow(m,vmin=-.015,vmax=.015,cmap='RdBu_r',interpolation='nearest')
        ax.set_title(names[c['backend']]+' same-cycle q128');ax.set_xlabel('Lane j (a then b)');ax.set_ylabel('Lane i (a then b)')
        if c['lanes_per_instance']>1:
            boundary=c['lanes_per_instance']-.5;ax.axvline(boundary,color='#333',lw=.6);ax.axhline(boundary,color='#333',lw=.6)
        fig.colorbar(im,ax=ax,fraction=.046,pad=.04)
    fig.tight_layout();savefig(fig,'spatial_q128.svg')
    def rows_for(feature,mode,source):
        return [[names[c['backend']],c['physical_seed']]+[cell(v,c) for v in [c['stats'][feature]['temporal_lag1'],c['stats'][feature]['temporal'],c['stats'][feature]['spatial']['within_instance']['same_cycle'],c['stats'][feature]['spatial']['between_instances']['same_cycle'],c['stats'][feature]['spatial']['within_instance']['lagged'],c['stats'][feature]['spatial']['between_instances']['lagged']]] for c in cases if c['mode']==mode and c['source']==source]
    headers=['后端','物理seed/对照编号','时间 k=1','时间全lag最差','实例内同拍','实例间同拍','实例内错拍','实例间错拍']
    layer_rows=[]
    for l in layers:
        if l['mode']=='raw':
            v=l['core_voltage'];lag=max(v['rho'],key=lambda k:abs(v['rho'][k]));layer_rows.append([l['seed'],'核心电压',v['n'],'均值 {:.6f} V'.format(v['mean_V']),'{:.6f}'.format(v['rho']['1']),'{:.6f} @{}µs'.format(v['rho'][lag],lag)])
            b=l['raw'];lag=max(b['rho'],key=lambda k:abs(b['rho'][k]));layer_rows.append([l['seed'],'理想0.6V比较器',b['n'],'P1={:.6f}'.format(b['p1']),'{:.6f}'.format(b['rho']['1']),'{:.6f} @{}µs'.format(b['rho'][lag],lag)])
        for stage,label in [('conditioned','调理 '+l['mode']),('packed_serial','32bit打包后串行 '+l['mode'])]:
            b=l[stage];lag=max(b['rho'],key=lambda k:abs(b['rho'][k]));layer_rows.append([l['seed'],label,b['n'],'P1={:.6f}'.format(b['p1']),'{:.6f}'.format(b['rho']['1']),'{:.6f} @index{}'.format(b['rho'][lag],lag)])
    seed_rows=[];joint_rows=[]
    for c in physical:
        tr=json.loads(next(Path(x['path']) for x in c['artifacts'] if Path(x['path']).name=='TRANSPORT.json').read_text(encoding='utf8'))
        bus,state=tr['loaded_bus_bits'],tr['loaded_state_bits']
        seed_rows.append([names[c['backend']],c['physical_seed'],c['mode'],bus['n'],state['n'],'{:.6f}'.format(bus['p1']),'{:.6f}'.format(state['p1']),'{:.6f}'.format(state['rho']['1']),'{:.2f}'.format(c['first_request_us'])])
        for j in c['stats']['joint']:
            joint_rows.append([names[c['backend']],c['physical_seed'],c['mode'],j['port'],j['q'],'{:.6f}'.format(j['one_hit']),'{:.6f}'.format(j['iid_one_hit']),'—' if 'xor1' not in j else '{:.6f}'.format(j['xor1'])])
    doc='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>物理理想读出到全路时间／空间相关实测</title><style>
*{box-sizing:border-box}body{margin:0;background:#f2f5f5;color:#19313a;font:16px/1.75 "Microsoft YaHei",sans-serif}main{max-width:1440px;margin:auto;padding:32px 24px}h1{font-size:32px;line-height:1.4}h2{font-size:22px}section{background:white;border:1px solid #dbe2e5;border-radius:12px;padding:22px;margin:22px 0}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid #dfe7e9;padding:10px;white-space:nowrap;text-align:left}th{background:#eaf1f3}img{width:100%;height:auto}.note{border-left:4px solid #b6722b;padding:12px 18px;background:#fff6e8}.muted{color:#56707b;font-size:14px}code{font-family:Consolas,monospace;font-size:13px;overflow-wrap:anywhere}summary{cursor:pointer;font-weight:bold}a{color:#047b83}.tag{background:#e1eff0;color:#047b83;padding:5px 10px;border-radius:5px;display:inline-block;margin:3px}@media(max-width:650px){main{padding:16px 10px}section{padding:14px}h1{font-size:25px}}
</style><main><p class="muted">ISSUE95 · 2026-10-25 · 实际执行结果</p><h1>从物理理想读出到顶层：逐路、逐延迟、逐路对的具体数据</h1>
<span class="tag">18物理播种案例＋18同形状IID对照</span><span class="tag">每路连续131,072帧</span><span class="tag">131个时间lag</span><span class="tag">9个跨路lag</span>
<p>输入为已测试的三条 core_V 波形，以0.6V理想比较器产生bit。经过直通或VN、32bit打包与有时间戳的分发，给两个同类型本地PRNG实例分别播种，然后连续产生131,072帧。下面的数值来自这次执行，均可定位到具体seed、实例、路号和延迟。</p>
<p><a href="rng_correlation_20261025_tables.zip" download>下载完整逐路／逐路对CSV数据包</a> · 本报告的范围统计不是置信区间，也没有预设“通过”阈值。</p>
<section><h2>1 · 精确实验边界和数据轴</h2><ul><li>物理seed：32003、32009、32027，各20000个样本，1µs间隔、2ms启动丢弃之后。核心仍挂旧比较器负载；理想阈值没有额外比较器噪声／延迟。未新运行Spectre。</li>
<li>每个案例有a/b两个独立状态实例：LFSR32为2×1路，GF64为2×64路，Bivium为2×20路。a0、b0等均从0编号。三类后端是分别运行的替代方案，不是同时接入同一网络的三组端口。</li>
<li>只有确实请求的种子前缀装入PRNG；剩余原始数据用于完整物理／调理层统计，未假装都影响当前输出。每个案例只启动一次，之后连续输出1.31072ms；默认1亿拍/1s换种未触发。物理采种慢、数字扩展快，不能将每个数字bit对应成一个新物理bit。</li>
<li>原始随机字R8、q={4,13,64,128,192}的概率bit、全部8个bitplane均测。概率恒定；不把变化的输入概率带来的相关算作PRNG缺陷。</li>
<li>时间ACF测每一路，k=1～128、256、512、1024；R8和五概率阈值的空间矩阵测所有路对，k=0、1、2、4、8、16、32、64、128。8个bitplane的空间矩阵只测同拍。定义Cᵢⱼ(k)=Corr(i(t),j(t+k))，数字k单位10ns，原始物理k单位1µs；VN的k为保留项索引。</li></ul>
<div class="note">三条物理seed是三次噪声仿真，不能当作同一物理阵列的三路同步输出。因此物理空间相关记为“无同时多路数据”，不填0。单路LFSR没有实例内路对，该项记“—”；实例间相关仍实测。</div></section>
<section><h2>2 · 每一层的数据变化</h2>'''+table(['seed','层／路径','样本数','均值／P1','ρ₁','已测lag中最大|ρ|的值与位置'],layer_rows)+'''
<p>串行打包后的bit与调理输出逐位一致，仅末尾不足32bit不发送，所以这一层不能净化随机性。最大相关对应不同测试数量和序列长度，应和完整曲线一起读。</p>
<details><summary>实际装入端点的种子前缀统计（短样本，仅作追踪）</summary>'''+table(['后端','seed','路径','总线bit数','状态bit数','总线P1','状态P1','状态串行ρ₁','首请求µs'],seed_rows)+'''
<p>两个LFSR/GF实例总共64状态bit；两个Bivium实例共384总线bit，装入354状态bit，丢弃30填充bit。状态序列是a状态随后b状态的串行诊断，不是时间连续输出，更不是种子熵率估计；原始包、装载沿和种子值保留在TRANSPORT.json。</p></details></section>
<section><h2>3 · 顶层公平概率bit：完整数值</h2><p>以下q128即p=0.5。每格显示<b>带符号的最大绝对相关值 [位置]</b>。时间“全lag最差”搜索所有输出路及131个lag；空间同拍排除自身对角并去重，错拍保留方向。a/b为不同实例。</p><h3>直通种子路径</h3>'''+table(headers,rows_for('q128','raw','physical'))+'''<h3>VN种子路径</h3>'''+table(headers,rows_for('q128','vn','physical'))+'''
<p>这次不是只测第一路，也不是只给三个seed的粗略范围。每个峰值都绑定具体路号和lag。各后端路数不同，最大值的搜索次数不同，不能直接按最大值大小排名。</p>
<details><summary>同形状、同样本长度的合成IID对照</summary><h3>raw对应对照</h3>'''+table(headers,rows_for('q128','raw','iid_control'))+'''<h3>VN对应对照</h3>'''+table(headers,rows_for('q128','vn','iid_control'))+'''<p>对照为PCG64直接产生的独立均匀字统计参考，未经过本地PRNG，也不声称物理真随机。对照不用于选择有利物理seed或改变仿真参数。</p></details></section>
<section><h2>4 · 全路时间曲线与空间矩阵</h2><p>图固定展示seed32003/raw，其他seed和VN全部数值在上表和CSV。时间图每个lag取所有路的最大|ρ|；空间图包含两个实例，黑线分隔实例a/b，自相关对角线隐藏。</p>'''+''.join(figures)+'''</section>
<section><h2>5 · 联合质量：两两相关以外的实际概率</h2>'''+table(['后端','seed','路径','实例','稀疏q','P(恰一路命中)','IID参考','前四路XOR=1'],joint_rows)+'''
<p>GF64前四路公平bit的XOR仍为0，稀疏单命中与IID参考有显著结构差异；即使其两两相关数值较小，也不能按联合IID使用。Bivium和LFSR仍只是通过已列出的有限探针，不等于全部统计性质已证明。单路LFSR的q=256单命中恒1属于退化单路对照，不用于比较多路选择质量。</p></section>
<section><h2>6 · 所有随机字、阈值与bitplane的峰值</h2><p>完整数据包保存每路131个时间lag、每路对各个空间lag以及T8/16/32/64/128方差比和MSE。R8也扫描全部q=1..256的边缘CDF误差；不止公平bit。</p><details><summary>展开504组后端／输入／阈值的精确峰值记录</summary>'''+table(['案例','观测量','时间lag1','时间全lag','实例内同拍','实例间同拍','实例内错拍','实例间错拍'],allrows)+'''</details></section>
<section><h2>7 · 可复现性与限制</h2><p>原模型用于有时间戳的种子接收及前256帧逐拍对照；连续无停顿部分用逐bit一致的C++整数实现加速，并核对中段、尾段各256帧及最终状态。相关矩阵使用整数计数；R8自相关用FFT、跨路矩阵用矩阵乘法，并逐例复算选定和最差位置。'''+str(audit['checks'])+'''项运行时核验通过；另有5项专门单测检查全部小矩阵元素、重复／移位／常量流和所有后端状态。</p>
<p>周期总数按已验证的无停顿固定操作数累计，未宣称每个长流时钟沿都运行了RTL。没有新综合、STA、PT、完整FFN/Attention/LLM或熵认证。VN、种子qualified和1拍收集/CDC仍为明示条件模型；空间指标衡量数字输出统计关系，不代表物理布线串扰。</p>
<p>数据：<code>project_archives/rng_correlation_20261025/cases/</code>；每案例words.bin、matrices.npz、DETAIL.json，物理案例另有TRANSPORT.json与状态检查点。CONFIG、SOURCE_MANIFEST、INPUT_MANIFEST、LAYERS、SUMMARY、AUDIT、PEAKS与ARCHIVE_INDEX均保存。</p>
<p class="muted">131072点下白噪声单个lag的95%参考尺度约±0.00541；这是单项参考，不是多路多lag联合门槛。三个物理seed只有三次独立仿真，更长的确定性PRNG输出不增加物理seed数量或物理熵。</p></section></main></html>'''
    (a.directory/'REPORT.html').write_bytes(doc.encode('utf8'))
    writejson(a.directory/'TABLES_ARCHIVE.json',artifact(zpath))
    print(json.dumps(dict(report=str(a.directory/'REPORT.html'),tables=artifact(zpath),peak_records=len(data))))


if __name__=='__main__':main()
