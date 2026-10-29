"""Derive tables only from collected report values; no assumed circuit prices."""
from pathlib import Path
import json,statistics as st,hashlib
S=Path(__file__).resolve().parent
def save(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 data=json.loads((S/'RESULTS.json').read_text());ungated=json.loads((S/'RESULTS_V2.json').read_text());rows=[]
 for x in data['results']:x['implementation']='v4_ICG_reset'
 for x in ungated['results']:x['implementation']='v2_CE'
 data['results']+=ungated['results']
 for x in data['results']:
  w={n:[v for v in x['windows'] if v['window']==n] for n in ('work','idle','seed')}
  assert len(w['work'])==len(w['idle'])==3
  cycles=[c for c in x['cycles'] if not c['stall']]
  front=set(c['front_cycles'] for c in cycles);full=set(c['full_cycles'] for c in cycles);assert len(front)==len(full)==1
  row=dict(x['case'],implementation=x['implementation'],cell_counts=x['cell_counts'],raw_area_um2=x['raw_area_um2'],area55_mm2=x['area55_mm2'],front_cycles=front.pop(),full_cycles=full.pop(),
      work_mW=st.mean(v['power']['total_W']*1000 for v in w['work']),query_energy_nJ=st.mean(v['energy_pJ']/8000 for v in w['work']),
      query_energy_range_nJ=[min(v['energy_pJ']/8000 for v in w['work']),max(v['energy_pJ']/8000 for v in w['work'])],
      idle_mW=st.mean(v['power']['total_W']*1000 for v in w['idle']),idle_leakage_mW=st.mean(v['power']['leakage_W']*1000 for v in w['idle']),
      seed_energy_nJ=st.mean(v['energy_pJ']/1000 for v in w['seed']) if w['seed'] else None,
      setup_ns=min(v['slacks_ns']['setup'] for v in x['windows']),hold_ns=min(v['slacks_ns']['hold'] for v in x['windows']),
      annotated_nets_pct=min(v['annotated_nets_pct'] for v in x['windows']),annotated_cells_pct=min(v['annotated_cells_pct'] for v in x['windows']),
      warnings=sorted(set(a for v in x['windows'] for a in v['warnings'])))
  assert row['front_cycles']==3*(128//row['lanes'])+36
  assert row['full_cycles']==4*(128//row['lanes'])+38+(128 if row['mode']==2 else 0)
  for gate in ('gate_setup','gate_hold'):
   values=[v['slacks_ns'].get(gate) for v in x['windows'] if v['slacks_ns'].get(gate) is not None]
   row[gate+'_ns']=min(values) if values else None
  rows.append(row)
 a=json.loads((S/'NUMERICAL_AUDIT.json').read_text())['rows'];num=[]
 for name in dict.fromkeys(x['name'] for x in a):
  v=[x for x in a if x['name']==name]
  num.append(dict(name=name,tv8=st.mean(x['tv_fp32_to_conserved_p8'] for x in v),tv_exp=st.mean(x['tv_exp_fixed_only'] for x in v),
       rne_mass=[x['rne_mass'] for x in v],bernoulli_hits=[x['bernoulli_total_hits'] for x in v]))
 save(S/'SUMMARY.json',dict(rows=rows,numerical=num,results_sha256=hashlib.sha256((S/'RESULTS.json').read_bytes()).hexdigest(),
      definition='query energy is total PT work-window energy/8 including interquery control gaps, excludes one-time seed initialization; idle is measured CE-hold not stopped clock'))
 lines=['# 数字Softmax P8与两条采样后端：EDA结果','',
 'Issue198 / PR199。128候选、S128；FP32输入转换到fixed11/F4、max/exp/sum/公共倒数/保质量P8、存储及后端均在电路内。详细算法、输出语义与复现说明见[README_ZH.md](README_ZH.md)。本轮是合成分数电路验证，没有模型PPL。','',
 'SS1.08V125C、100MHz。面积为原始SHARK面积×0.81的55nm等效标准单元面积，非布局core面积；功率/能量不缩放。三seed工作窗口均值，包含每8查询间隙，冷启动单列；不含V地址映射/读取/累加。','',
 '|版本/配置|原面积 µm²|55等效 mm²|概率就绪/完整输出 拍|工作 mW|每查询 nJ|空闲 mW|',
 '|---|---:|---:|---:|---:|---:|---:|']
 for r in rows:lines.append('|%s|%.2f|%.6f|%d / %d|%.4f|%.4f|%.4f|'%(r['implementation']+'/'+r['top'],r['raw_area_um2'],r['area55_mm2'],r['front_cycles'],r['full_cycles'],r['work_mW'],r['query_energy_nJ'],r['idle_mW']))
 lines+=['','p8为前端加概率流发射，sys为完整systematic计数路径，bern为完整独立R8比较及直方图路径。三者都输出128项；零项也发射，下游据计数跳过V。不能将p8与集成sys/bern的功耗简单相减，视为后端的独立精确测量。','',
 'Systematic总计数固定128；Bernoulli仅期望为128，输出按固定128归一化。二者样本联合分布不同，不能把同采样数直接当同质量。P8/S128的systematic相位只有1bit有效，相关性/候选顺序敏感性需模型实测。','',
 '|版本/配置|setup余量 ns|hold余量 ns|net/cell活动覆盖 %|一次种子＋预热 nJ|',
 '|---|---:|---:|---:|---:|']
 for r in rows:lines.append('|%s|%.6f|%.6f|%.2f / %.2f|%s|'%(r['implementation']+'/'+r['top'],r['setup_ns'],r['hold_ns'],r['annotated_nets_pct'],r['annotated_cells_pct'],'不适用' if r['seed_energy_nJ'] is None else '%.4f'%r['seed_energy_nJ']))
 for r in rows:
  if r['gate_setup_ns'] is not None:lines.append('\n'+'门控检查 %s：ICG %d个，enable setup %.6fns / hold %.6fns。'%(r['top'],r['cell_counts']['icg'],r['gate_setup_ns'],r['gate_hold_ns']))
 lines+=['','数据时序按下降沿发出、上升沿捕获，2fF输出负载；v4启动时停钟释放复位、等待20ns后启钟，仅rst_n使用setup2/hold1合同。原v3 Bernoulli复位恢复违例−0.366158ns保留，不是靠放宽正常数据路径获得通过。没有SDF/SPEF/CTS，门级回放为零延迟活动，不能代替后布局验证。所有负slack和PT警告保留在RESULTS.json/原始报告，不因能算出功耗就视为时序通过。','',
 'v2寄存器用CE；v3加入真实ICG；主表v4复用v3网表并验证停钟释放复位、等待20ns后启动的合同，正常查询无额外周期。仍保留未门控逻辑、ICG及漏电功耗。不要把工作功率除以整模型平均功率当能量占比；整模型替换还需统一并行头数、复用、实际查询率、空闲门控、共同KV路径及匹配质量。','',
 '## 数值诊断','',
 '|输入组（三seed）|P8相对FP32 TV|固定指数路径 TV|普通RNE总质量（目标256）|Bernoulli128轮总命中|',
 '|---|---:|---:|---|---|']
 for n in num:lines.append('|%s|%.4f%%|%.4f%%|%s|%s|'%(n['name'],100*n['tv8'],100*n['tv_exp'],str(n['rne_mass']),str(n['bernoulli_hits'])))
 lines+=['','TV=0.5 sum_i abs(p_i−q_i/256)，只对保质量概率报告TV。普通RNE质量不守恒，原JSON使用未重归一L1。P12/P16软件敏感性也保留，但没有对应硬件测量。不要把P8误差或合成向量通过替换为Qwen真实PPL通过。','',
 '## 证据与范围','',
 'v1作业38459525：7配置旧VCS声明顺序编译失败，保留。v2预检38459538全部28回放通过，PPA38459583目前已归档4个配置的16门级回放/30PT窗口；三个16lane配置仍在综合，不报未完成PPA。v3预检38459724/PPA38459737为12RTL＋12门级/24PT；v4预检38459936/回放38459970复用v3网表，另12RTL＋12门级/24PT。已归档完整配置80回放、81920个计数比较、78PT窗口；加上进行中16lane的12个RTL预检，共92个功能回放。具体状态见SUPPLEMENTARY_STATUS.json。v2/v3优化命令不同，不把差值全归于ICG。','',
 'Bivium仅为紧凑连续状态核，systematic1核、Bernoulli7核；种子预热不每查询重复。旧随机服务端点的checkpoint/epoch等未包含，同一紧凑核也可给Ising复用，不能把边界缩减算成数字算法专属收益。无物理熵生成/全局分发，无新增GPU/模型/PPL。','',
 'RESULTS.json、RESULTS_V3_ORIGINAL.json及RESULTS_V2.json保存逐窗口、slack、活动覆盖、PT检查及功耗原件SHA；SOURCE_V2/V3.json及SOURCE.json分别绑定实际v2/v3/v4快照，COLLECTION.json/RAW_INDEX.json提供原字节归档索引。collect.py/summarize.py是后处理，未反写不可变执行快照。中央run在digital_circuit_simulation_registry/records/attention-digital-p8-198-eda-20261029.json。']
 (S/'REPORT_ZH.md').write_bytes(('\n'.join(lines)+'\n').encode())
 print(json.dumps(rows,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
