"""Verify original package/report members; summarize all single-scale variants."""
from pathlib import Path
import hashlib,json,math,shutil,statistics,tarfile,zipfile
ROOT=Path(__file__).resolve().parents[4];WS=ROOT.parents[1];HERE=Path(__file__).resolve().parent
PKG=ROOT/'architecture_tlm/matrix_single_scale_20261028';ARCH=WS/'project_archives/matrix204_single_scale_20261028'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def main():
 packs=ARCH/'execution_packages';packs.mkdir(parents=True,exist_ok=True);sources=[];artifacts=[];functions=[];rows=[];failures=[]
 for p in sorted((HERE/'private').glob('matrix204_single_v*.zip')):
  dst=packs/p.name
  if dst.exists():assert sha(dst)==sha(p)
  else:shutil.copyfile(p,dst)
  with zipfile.ZipFile(dst) as z:
   b=z.read(p.stem+'/EXECUTION_MANIFEST.json');m=json.loads(b)
   for n,h in m['files'].items():assert hashlib.sha256(z.read(p.stem+'/'+n)).hexdigest()==h,n
  sources.append({'snapshot':p.stem,'path':str(dst),'sha256':sha(dst),'bytes':dst.stat().st_size,'source_manifest_sha256':hashlib.sha256(b).hexdigest(),'members_verified':len(m['files'])})
 transfer=json.loads((HERE/'TRANSFER_VERIFICATION.json').read_text(encoding='utf-8'))
 for x in transfer['artifacts']:
  f=Path(x['path']);assert sha(f)==x['sha256'] and f.stat().st_size==x['bytes']
  with tarfile.open(f) as t:
   index=json.load(t.extractfile('RETURN_MANIFEST.json'))['files']
   for n,h in index.items():assert hashlib.sha256(t.extractfile(n).read()).hexdigest()==h,n
   r=json.load(t.extractfile('RESULT.json'))
  artifacts.append(dict(x,members_verified=len(index)))
  if x['directory'].startswith('functional'):
   functions.append({'snapshot':x['snapshot'],'M':r['M'],'cases':len(r['cases']),'frames':sum(c['frames'] for c in r['cases']),'status':r['status']});continue
  if r['status']!='calculated':failures.append({'snapshot':x['snapshot'],'top':r['top'],'status':r['status'],'error':r.get('error')});continue
  assert len(r['windows'])==6
  a=[w for w in r['windows'] if w['mode']=='active'];idle=[w for w in r['windows'] if w['mode']=='idle'];assert len(a)==len(idle)==3
  row={'snapshot':x['snapshot'],'top':r['top'],'mode':r['mode'],'M':r['M'],'archive':str(f),'seeds':[w['seed'] for w in a]}
  for k in ['raw_area_um2','area_55eq_um2','total_W','internal_W','switching_W','leakage_W','gross_pJ_per_operation','cycles_per_operation']:
   row[k]=statistics.mean(w[k] for w in a)
  row.update(energy_std_pJ=statistics.pstdev(w['gross_pJ_per_operation'] for w in a),idle_W=statistics.mean(w['total_W'] for w in idle),
   setup_slack_ns=min(w['setup_slack_ns'] for w in r['windows']),hold_slack_ns=min(w['hold_slack_ns'] for w in r['windows']),
   review_flags=sorted({v for w in r['windows'] for v in w['review_flags']}),all_mapped_pin_activity_verified=all(w['all_mapped_pin_activity_verified'] for w in r['windows']),
   windows=[{k:w[k] for k in ['mode','seed','window_ns','operations','total_W','gross_pJ_per_operation','setup_slack_ns','hold_slack_ns','review_flags']} for w in r['windows']],
   constant_top_output_proofs=[w.get('constant_top_port_proofs',[]) for w in r['windows'] if w.get('constant_top_port_proofs')])
  row['groups']={k:{'cells':a[0]['groups'][k]['cells'],'raw_area_um2':a[0]['groups'][k]['area_um2'],
   'mean_W':[statistics.mean(w['groups'][k]['watts'][i] for w in a) for i in range(4)]} for k in a[0]['groups']}
  rows.append(row)
 quality=[]
 for m in (1,8):
  values=[]
  for seed in (17,503,1009):values.extend(json.loads((PKG/'power_fixtures'/('m%d_s%d'%(m,seed))/'metrics.json').read_text(encoding='utf-8')))
  den=sum(x['event_exact']**2 for x in values);target=sum(x['SC_expected']**2 for x in values)
  quality.append({'M':m,'outputs':len(values),'OR_bias_raw':statistics.mean(x['OR_error_same_events'] for x in values),
   'OR_RMSE_raw':math.sqrt(statistics.mean(x['OR_error_same_events']**2 for x in values)),
   'OR_NRMSE_vs_same_event_RMS':math.sqrt(sum(x['OR_error_same_events']**2 for x in values)/den) if den else None,
   'SC_NRMSE_vs_quantized_target_RMS':math.sqrt(sum(x['SC_error_vs_quantized']**2 for x in values)/target) if target else None,
   'scope':'synthetic resident-W uniform INT8; no real model/PPL claim; all OR counting methods share this oracle'})
 result={'date':'2026-10-28','N':64,'T':32,'BINS':1,'signed_INT8':[-128,127],'PVT':'SS1.08V125C','frequency_MHz':100,'area_multiplier':0.81,
  'source_packages':sources,'report_archives':artifacts,'functional':functions,'PPA':rows,'numeric':quality,'failures_preserved':failures,
  'active_jobs_at_collection':transfer['active_jobs_at_collection'],'boundary':'compute/control only; external resident weights, event RNG/comparator and quantization/scale recovery excluded; no CTS/SDF/SPEF'}
 save(PKG/'results/FINAL_SUMMARY.json',result)
 names={0:'精确三级树',1:'精确位平面',2:'共享输入计数',3:'OR4→popcount16→时间累计',4:'INT8并行乘加',5:'INT8位串行',6:'OR4→16路时间计数→求和'}
 lines=['# 单尺度INT8功耗验证（2026-10-28）','',
  '64输入共用一个尺度，T32，真正signed INT8含−128，SS1.08V125C100MHz。每次OR4在同权重幅值位平面、同符号内进行，64个bit先变16个bit，然后精确并行计数；未把OR移到时间计数后。',
  '', '| 版本/方法 | M | 55nm等效面积 mm² | 功率 mW | 能量 pJ/帧 | 周期/帧 | setup/hold ns |',
  '|---|---:|---:|---:|---:|---:|---|']
 for x in sorted(rows,key=lambda z:(z['M'],z['mode'],z['snapshot'])):
  v=x['snapshot'].split('_')[2]
  lines.append('| %s %s | %d | %.6f | %.4f | %.3f | %.1f | %.5f / %.5f |'%(v,names[x['mode']],x['M'],x['area_55eq_um2']/1e6,x['total_W']*1e3,x['gross_pJ_per_operation'],x['cycles_per_operation'],x['setup_slack_ns'],x['hold_slack_ns']))
 lines+=['', '面积均已raw×0.81，原值保存在JSON；不缩放功率/能量/时间。周期为含帧握手的完整帧周期，100MHz每周期10ns。每行三组合成刺激seed均值；不是PVT/制造蒙特卡洛或模型精度。M8每帧完成8个点积，不能直接拿其能量与M1相除判优。',
  '', 'V1：直接实现，mode6正负各6位；V2：mode6每组一个7位有符号计数器；V3：保留V2组计数，模式1/3采用专用无符号popcount并隔离末端恢复输入，mode6隔离组求和输入。三种OR计数方式对同一事件得到相同整数，差异只在硬件。所有版本保留，不把未优化实现当最优架构成本。',
  '', '一个OR平面：先OR4得到16个0/1，popcount为0..16；跨32拍单符号累计0..512，正负差需要11位。16路独立累计时单符号各需6位；若先对正负OR取差，组累计范围[-32,32]需7位。完整INT8幅值最多128，需要8个幅值位平面；SC总和20位，数字总和22位，最终符号扩展32位输出。',
  '', '独立整数/OR oracle验证端点−128、±127、0、符号抵消、稀疏/半概率、公共/逐路R8、分层事件、reset中止、gaps/stall。主PPA另用16帧驻留W的uniform signed INT8输入，公共R8；所有核同一输入。SC原始结果期望为数字点积/4，共同尺度与固定×4后恢复在核心之外。',
  '', '旧四档数据保留。本轮移除逐输入尺度选择/位移，但同时采用完整INT8、收紧位宽和驻留W/不同合成刺激，因此不能将新旧表差异全部归因尺度。单尺度对真实模型的精度未验证。',
  '', 'OR4仍为有损近似，低估75%的端点压力例不代表一般分布；主刺激的OR-only bias/RMSE/相对同事件RMS归一误差见FINAL_SUMMARY.json的numeric。更换时间计数实现不会消除OR碰撞误差。',
  '', '计算核不包含权重SRAM/保持读口、RNG/比较器、输入量化/共同尺度选择、最终浮点恢复、CTS/SDF/SPEF或实际广播布线；CE不冒称ICG。保留全部hold/setup及功耗模型范围告警，功耗算出不等于芯片签核。真实模型质量、存储和全链路还需另验。',
  '', '原字节源包与小报告归档在project_archives/matrix204_single_scale_20261028，远端/本地大小SHA与归档成员逐项核验，Git不包含工艺库、网表或大波形。']
 for x in quality:lines.append('\n合成主刺激M%d：OR-only NRMSE/RMS(exact)=%.4f，SC采样NRMSE/RMS(量化目标)=%.4f；这是本组刺激，不是模型准确率。'%(x['M'],x['OR_NRMSE_vs_same_event_RMS'],x['SC_NRMSE_vs_quantized_target_RMS']))
 def pick(v,mode,m):return next((x for x in rows if x['snapshot'].split('_')[2]==v and x['mode']==mode and x['M']==m),None)
 best=pick('v3',3,1);group=pick('v3',6,1);exact=pick('v1',0,1);digital=pick('v1',5,1)
 if all((best,group,exact,digital)):
  lines+=['', '优化后M1的OR4-popcount16相对本轮精确树：能量%+.2f%%、面积%+.2f%%；相对INT8位串行：能量%.3f倍、面积%+.2f%%、时间%.2f倍。因此该核有面积收益，但本轮没有证明能效或速度胜数字。'%(100*(best['gross_pJ_per_operation']/exact['gross_pJ_per_operation']-1),100*(best['area_55eq_um2']/exact['area_55eq_um2']-1),best['gross_pJ_per_operation']/digital['gross_pJ_per_operation'],100*(best['area_55eq_um2']/digital['area_55eq_um2']-1),best['cycles_per_operation']/digital['cycles_per_operation']),
   '', '为何16路各自累计更耗能：按符号差合并后仍需8×16×7=896位时间计数状态，而每拍popcount再累计只需8×11=88位；本次映射含控制/结果寄存器分别%d和%d个。寄存器功率分别%.2f和%.2fµW，组合逻辑分别%.2f和%.2fµW；组计数版隔离末端输入后仍有大量逐拍时钟成本。寄存器使用CE，未插ICG，不能把此实现结果当所有组计数方案的理论下限。'%(group['groups']['registers']['cells'],best['groups']['registers']['cells'],group['groups']['registers']['mean_W'][3]*1e6,best['groups']['registers']['mean_W'][3]*1e6,group['groups']['combinational_unattributed']['mean_W'][3]*1e6,best['groups']['combinational_unattributed']['mean_W'][3]*1e6)]
  b8=pick('v3',3,8);d8=pick('v1',5,8)
  if b8 and d8:lines+=['', 'M8优化OR4平均每点积%.3fpJ，数字位串行%.3fpJ；OR4面积相对数字%+.2f%%，能量%.3f倍、时间%.2f倍。扩大到8输出并未使本实现能效超过数字。'%(b8['gross_pJ_per_operation']/8,d8['gross_pJ_per_operation']/8,100*(b8['area_55eq_um2']/d8['area_55eq_um2']-1),b8['gross_pJ_per_operation']/d8['gross_pJ_per_operation'],b8['cycles_per_operation']/d8['cycles_per_operation'])]
 (PKG/'results/REPORT_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
 print('VERIFIED_REPORTS',len(artifacts),'FUNCTIONAL_FRAMES',sum(x['frames'] for x in functions),'PPA_CORES',len(rows),'WINDOWS',6*len(rows))
 for x in rows:print(x['snapshot'].split('_')[2],x['top'],round(x['area_55eq_um2'],2),round(x['gross_pJ_per_operation'],3),x['cycles_per_operation'],x['review_flags'])
if __name__=='__main__':main()
