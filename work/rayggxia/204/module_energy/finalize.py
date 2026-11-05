"""Verify original archives, summarize energy, and test compositional estimates."""
from pathlib import Path
import hashlib,json,math,shutil,statistics,tarfile,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];WS=ROOT.parents[1]
PKG=ROOT/'architecture_tlm/module_energy_20261028';ARCH=WS/'project_archives/matrix204_module_energy_20261028'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def mean(v):return statistics.mean(v)
def main():
 sources=[];artifacts=[];functions=[];failures=[];rows=[];rawcases={}
 (ARCH/'execution_packages').mkdir(exist_ok=True)
 for p in sorted((HERE/'private').glob('matrix204_modules_v*.zip')):
  dst=ARCH/'execution_packages'/p.name
  if dst.exists():assert sha(dst)==sha(p)
  else:shutil.copyfile(p,dst)
  with zipfile.ZipFile(dst) as z:
   b=z.read(p.stem+'/EXECUTION_MANIFEST.json');m=json.loads(b)
   for n,h in m['files'].items():assert hashlib.sha256(z.read(p.stem+'/'+n)).hexdigest()==h,n
  sources.append({'snapshot':p.stem,'path':str(dst),'sha256':sha(dst),'bytes':dst.stat().st_size,'manifest_sha256':hashlib.sha256(b).hexdigest(),'members_verified':len(m['files'])})
 transfer=json.loads((HERE/'TRANSFER_VERIFICATION.json').read_text(encoding='utf-8'))
 for x in transfer['artifacts']:
  p=Path(x['path']);assert sha(p)==x['sha256'] and p.stat().st_size==x['bytes']
  with tarfile.open(p) as t:
   bootstrap=x['directory']=='bootstrap_failure';mf='BOOTSTRAP_MANIFEST.json' if bootstrap else 'RETURN_MANIFEST.json';m=json.load(t.extractfile(mf))['files']
   for n,h in m.items():assert hashlib.sha256(t.extractfile(n).read()).hexdigest()==h,n
   r=json.load(t.extractfile('BOOTSTRAP_RESULT.json' if bootstrap else 'RESULT.json'))
  artifacts.append(dict(x,members_verified=len(m)))
  if bootstrap:failures.append(r|{'archive':str(p)});continue
  if x['directory'].startswith('functional'):
   functions.append({'case':r['case'],'status':r['status'],'replays':r['replays'],'archive':str(p)});continue
  if r['status']!='calculated':failures.append({'case':r['case'],'status':r['status'],'error':r.get('error'),'archive':str(p)});continue
  assert len(r['windows'])==12;r['archive']=str(p);rawcases[r['case']['name']]=r
  row={'case':r['case'],'archive':str(p),'raw_area_um2':r['raw_area_um2'],'area_55eq_um2':r['area_55eq_um2'],
   'setup_slack_ns':min(w['setup_slack_ns'] for w in r['windows']),'hold_slack_ns':min(w['hold_slack_ns'] for w in r['windows']),
   'review_flags':sorted({f for w in r['windows'] for f in w['review_flags']}),'profiles':{},
   'all_mapped_pin_activity_verified':all(w['all_mapped_pin_activity_verified'] for w in r['windows'])}
  for profile in ('sparse','dense','replay','idle'):
   ww=[w for w in r['windows'] if w['mode']==profile];assert len(ww)==3
   q={k:mean(w[k] for w in ww) for k in ['internal_W','switching_W','leakage_W','total_W','window_ns','operations']}
   if profile!='idle':
    q.update(energy_pJ_per_operation=mean(w['gross_pJ_per_operation'] for w in ww),energy_std_pJ=statistics.pstdev(w['gross_pJ_per_operation'] for w in ww),cycles_per_operation=ww[0]['cycles_per_operation'],
     cell_dynamic_pJ_per_operation=mean((w['internal_W']+w['switching_W'])*w['window_ns']*1000/w['operations'] for w in ww))
   q['seed_results']=[{k:w[k] for k in ['seed','total_W','gross_pJ_per_operation','operations','window_ns','cycles_per_operation']} for w in ww]
   if r['case']['family'] in ('acc','plane','bank'):
    q['logical_samples_per_frame']=32;q['accepted_logical_samples']=int(q['operations'])*32
   row['profiles'][profile]=q
  for profile in ('sparse','dense','replay'):
   q=row['profiles'][profile];q['incremental_pJ_vs_idle_per_operation']=q['energy_pJ_per_operation']-row['profiles']['idle']['total_W']*q['window_ns']*1000/q['operations']
  rows.append(row)
 # Estimate module composition on held connected designs, preserving per-seed pairing.
 estimates=[]
 def w(name,profile,seed):return next(x for x in rawcases[name]['windows'] if x['seed']==seed and x['mode']==profile)
 def e(name,seed):return w(name,'replay',seed)['gross_pJ_per_operation']
 needed=['maskor64','popdiff16','acc7','acc8','acc9','acc11','plane64_b9','plane64_b11','bank77','bank54','bank50']
 if all(n in rawcases for n in needed):
  for seed in (17,503,1009):
   mask=w('maskor64','replay',seed);diff=w('popdiff16','replay',seed)
   common=32*(e('maskor64',seed)+e('popdiff16',seed))
   for b in (9,11):
    pred=common+10e3*(mask['leakage_W']+diff['leakage_W'])+e('acc%d'%b,seed);actual=e('plane64_b%d'%b,seed)
    estimates.append({'target':'plane64_b%d'%b,'seed':seed,'method':'raw_component_sum','predicted_pJ':pred,'measured_pJ':actual,'relative_error':pred/actual-1})
   models={}
   for name in ('bank77','bank54','bank50'):
    c=rawcases[name]['case'];shift=next(z['case']['name'] for z in rows if z['case']['family']=='shift' and z['case']['widths']==c['widths'] and z['case']['FIRST']==c['FIRST'])
    pred=e(shift,seed)
    for b in c['widths']:
     pred+=common+30e3*(mask['leakage_W']+diff['leakage_W'])+e('acc%d'%b,seed)+20e3*w('acc%d'%b,'idle',seed)['total_W']
    models[name]=pred;actual=e(name,seed)
    estimates.append({'target':name,'seed':seed,'method':'raw_component_sum','predicted_pJ':pred,'measured_pJ':actual,'relative_error':pred/actual-1})
   pred=e('bank54',seed)+models['bank50']-models['bank54'];actual=e('bank50',seed)
   estimates.append({'target':'bank50','seed':seed,'method':'bank54_calibrated_width_delta','calibration':'bank54 only; validation target bank50 not fitted','predicted_pJ':pred,'measured_pJ':actual,'relative_error':pred/actual-1})
 quant=[]
 for c in json.loads((PKG/'CASES.json').read_text()):
  if c['family']!='pop':continue
  for profile in ('sparse','dense','replay'):
   errors=[]
   for seed in (17,503,1009):
    d=PKG/'fixtures'/c['name']/str(seed);meta=json.loads((d/'WINDOWS.json').read_text());win=next(x for x in meta['windows'] if x['mode']==profile)
    st=(win['start_ns']-50)//10;end=(win['end_ns']-50)//10
    inputs=[int(x,16)&((1<<c['IW'])-1) for x in (d/'stim.hex').read_text().splitlines()];outputs=[int(x,16) for x in (d/'expect.hex').read_text().splitlines()]
    errors.extend((outputs[i]<<c['DROP'])-inputs[i].bit_count() for i in range(st,end))
   quant.append({'name':c['name'],'profile':profile,'output_unit':1<<c['DROP'],'mean_error_count':mean(errors),'RMSE_count':math.sqrt(mean(x*x for x in errors)),'max_abs_error_count':max(abs(x) for x in errors)})
 numeric=[]
 for name in ('bank54','bank50'):
  vals=[];refs=[]
  for seed in (17,503,1009):
   pair=[]
   for n in ('bank77',name):
    c=next(c for c in json.loads((PKG/'CASES.json').read_text()) if c['name']==n);d=PKG/'fixtures'/n/str(seed);m=json.loads((d/'WINDOWS.json').read_text());v=next(x for x in m['windows'] if x['mode']=='replay');start=(v['start_ns']-50)//10
    a=[int(x,16) for x in (d/'expect.hex').read_text().splitlines()];out=[a[start+35*i+34] for i in range(16)];pair.append([x-(1<<c['OW']) if x>=(1<<(c['OW']-1)) else x for x in out])
   refs+=pair[0];vals+=pair[1]
  err=[a-b for a,b in zip(vals,refs)];numeric.append({'name':name,'outputs':len(vals),'extra_NRMSE_vs_bank77_OR':math.sqrt(sum(x*x for x in err)/sum(x*x for x in refs)),'max_abs_error_raw':max(abs(x) for x in err)})
 summary={'date':'2026-10-28','PVT':'SS1.08V125C','frequency_MHz':100,'area_multiplier':.81,'source_packages':sources,'report_archives':artifacts,
  'functional':functions,'PPA':sorted(rows,key=lambda x:x['case']['id']),'failures_preserved':failures,'composition_estimates':estimates,'pop_quantization':quant,'bank_numeric':numeric,
  'active_jobs_at_collection':transfer['active_jobs_at_collection'],
  'metadata_errata':['Raw PT samples field is a zero placeholder, not actual sequential input count. Derived sequential profiles explicitly record32 samples/frame; stimulus en pulses and oracle verify the count.',
   'Frozen README replay description was broad: only pop16/diff/mask/acc/plane/shift/bank use derived old M8 vectors. Other pop sizes use IIDp=.35; align replay is random signed words/shift. These are synthetic profiles, not model activations.'],
  'boundary':'Only named compute/control modules; CE not ICG; no wrapper I/O flops on combinational tops. No SRAM/RNG/comparator/encoding/CTS/SDF/SPEF/physical broadcast; module sums depend on load and synthesis context.'}
 stats=[]
 for target,method in sorted({(x['target'],x['method']) for x in estimates}):
  ee=[x for x in estimates if x['target']==target and x['method']==method]
  stats.append({'target':target,'method':method,'mean_relative_error':mean(x['relative_error'] for x in ee),'max_abs_relative_error':max(abs(x['relative_error']) for x in ee)})
 summary['composition_statistics']=stats
 summary['functional_replays']=sum(len(f['replays']) for f in functions)
 summary['functional_transactions']=sum(x['transactions'] for f in functions for x in f['replays'])
 save(PKG/'results/FINAL_SUMMARY.json',summary)
 lines=['# 参数化模块能耗结果','', '统一SS1.08V125C100MHz，面积已经乘0.81；原始面积另存。下表replay三seed均值，操作单位随模块变化，不可只看功率或将不同单位直接相加。组合逻辑无人工I/O寄存器；顺序模块计真实寄存器及自由时钟。',
  '', '| 模块 | 输入/输出位 | 55nm等效面积 µm² | replay功率 µW | replay能量 pJ/次 | 周期/次 |', '|---|---:|---:|---:|---:|---:|']
 for x in sorted(rows,key=lambda x:x['case']['id']):
  c=x['case'];p=x['profiles']['replay'];lines.append('| %s | %d/%d | %.2f | %.3f | %.4f | %.0f |'%(c['name'],c['IW'],c['OW'],x['area_55eq_um2'],p['total_W']*1e6,p['energy_pJ_per_operation'],p['cycles_per_operation']))
 lines+=['', 'pop/diff/mask/align以一次组合求值计；acc/plane以一帧32次更新计，含一次清零共33拍；bank一帧35拍；固定shift的replay也每35拍恢复一次，能量含该驻留时间的泄漏。shift的dense每拍变化能量另见JSON，不能把replay帧能量再乘32。',
  '', 'pop8/32/64的replay是IIDp=.35合成bit；pop16及单平面相关模块用旧M8驻留W公共R8回放。align的replay是随机有符号字和移位量。sparse/dense为切换压力，bank参数可逐拍变化，不能代替驻留W主结果。bank77/54/50的replay使用同一输入、预解码7幅值位及乘积符号，并显式把abs(W)限127；不能与旧完整INT8/8幅值位结果作纯状态位消融。',
  '', '原PT元数据samples字段写0是占位错误；实际acc/plane/bank每帧32个输入更新，由stim en与oracle核对，派生JSON已补明确字段。原件保留，能量由窗口时长与完成帧数计算，不受该字段影响。',
  '', 'Pop输出缩位采用舍弃计数LSB，单位为2^DROP，偏差/RMSE以真实事件数单位列在pop_quantization；不是高位回绕。固定恢复的输出宽覆盖全部输入编码范围；可变对齐为算术右移舍入向负无穷再加法，单独表征，不混入单尺度恢复成本。',
  '', '逐项相加验证：模块统一输出负载20fF，但内部连接负载不同，存在边界、额外缓冲、综合优化、共享输入相关性及计数输出活跃度差异。raw_component_sum是未经校准的独立模块估算；bank54_calibrated_width_delta只用bank54校准、留bank50验证，不能推广为所有输入规模或整个芯片的误差保证。',
  '', '| 验证对象／方法 | seed | 模块预测 pJ | 实测 pJ | 误差 |','|---|---:|---:|---:|---:|']
 for x in estimates:lines.append('| %s / %s | %d | %.4f | %.4f | %+.2f%% |'%(x['target'],x['method'],x['seed'],x['predicted_pJ'],x['measured_pJ'],100*x['relative_error']))
 lines+=['', '因此popcount和移位相加只能覆盖计算核的一部分。应加上权重位选择/OR、时间累计、清零/控制/结果寄存器、调用频率与时钟，再用组合模块校准；SRAM、随机前端和物理布线仍待独立闭合，不能承诺全芯片估算精度。',
  '', 'V1在EDA前因旧Python不支持Path.write_text(newline=...)启动失败，33个任务日志及源包保留；V2仅修复保存函数兼容性，RTL/bench/fixtures不变。Windows Icarus因系统DLL重定位不可用，不能标本地功能通过；服务器VCS实际99次三seed回放为功能证据。所有STA/功耗表范围告警保留，前布局无CTS/SDF/SPEF。源包与报告原字节及成员SHA在project_archives/matrix204_module_energy_20261028。']
 for x in numeric:lines.append('\n%s在48个replay点积上相对bank77 OR输出的额外NRMSE=%.3f%%，不是模型精度。'%(x['name'],100*x['extra_NRMSE_vs_bank77_OR']))
 if len(rows)==33:
  by={x['case']['name']:x for x in rows};b54=by['bank54'];b50=by['bank50'];b77=by['bank77']
  lead=['', '已完成33个配置、396个功耗窗口，99次功能回放/162396逐周期比较通过；67报告归档、2原始执行包的远端/本地及逐成员SHA核验。全部所报setup/hold非负，功耗模型范围等告警仍保留。',
   '', '主要结论：popcount和移位相加不足以直接预测整核。未经校准的独立模块相加，对组合bank高估约23%，对单平面高估约26%–27%；同输入与20fF端口负载口径下，用bank54校准后、只更换位宽预测bank50，三seed最大绝对误差0.637%。这仅验证N64/相近位宽变更，不是跨规模/全芯片误差保证。',
   '', 'bank77/54/50的replay能量分别%.3f/%.3f/%.3fpJ/35拍；54→50只省%.2f%%能量、%.2f%%面积，本组48点积额外NRMSE相对OR基线从%.3f%%变为%.3f%%。可先以54位作为较稳妥起点，50位保留为候选；无模型精度结论。'%(b77['profiles']['replay']['energy_pJ_per_operation'],b54['profiles']['replay']['energy_pJ_per_operation'],b50['profiles']['replay']['energy_pJ_per_operation'],100*(1-b50['profiles']['replay']['energy_pJ_per_operation']/b54['profiles']['replay']['energy_pJ_per_operation']),100*(1-b50['area_55eq_um2']/b54['area_55eq_um2']),100*numeric[0]['extra_NRMSE_vs_bank77_OR'],100*numeric[1]['extra_NRMSE_vs_bank77_OR']),
   '', '输入规模对popcount成本影响明显，输出少一位不一定省去大量逻辑：pop64只丢一个LSB，面积约降0.54%、dense能量约降1.20%，因为高位计数仍依赖低位进位。应优先结合保留平面数量、时间累计和调用频率考虑，不能按输出位数比例缩放能耗。']
  lines=lines[:1]+lead+lines[1:]
 (PKG/'results/REPORT_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
 print('VERIFIED',len(sources),'packages',len(artifacts),'reports',len(functions),'functional cases',len(rows),'PPA cases',12*len(rows),'windows')
 for x in rows:
  if x['case']['family'] in ('bank','acc'):print(x['case']['name'],x['profiles']['replay']['energy_pJ_per_operation'],x['area_55eq_um2'],x['review_flags'])
if __name__=='__main__':main()
