"""Index existing Issue204 measurements in the shared power/area folder."""
from pathlib import Path
import csv,hashlib,io,json,math,re,subprocess
R=Path(__file__).resolve().parents[4];REF='4175c5565fcd714b0648d97a15c1697b5fbcee05';REG=R/'digital_circuit_simulation_registry';OUT=REG/'summaries/20261029_matrix204'
URL='https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/'+REF+'/'
SPECS=[('matrix_validation_20261028','四档T32首轮','matrix-t32-204-20261028','active'),('matrix_single_scale_20261028','单尺度INT8/T32','matrix-single-scale-204-20261028','active'),('module_energy_20261028','参数化popcount/OR/累计/恢复','matrix-modules-204-20261028','replay'),('bf16_ppa_20261028','BF16/FP32成熟算术与DOT4','matrix-bf16-204-20261028','normal'),('int8_classic_ppa_20261028','四lane经典INT8','matrix-int8-classic-204-20261028','matched'),('int8_parallel64_20261028','同64路并行INT8','matrix-int8-par64-204-20261029','peak')]
def digest(b):return hashlib.sha256(b).hexdigest()
def read(n):
 b=subprocess.check_output(['git','show',REF+':'+n],cwd=R)
 p=R/n
 if p.exists():assert p.read_bytes()==b,'Working source differs from pinned commit: '+n
 return b
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def f(v):return '—' if v is None else f'{v:.6g}'
def definition(n,c,m):
 if n=='module_energy_20261028':
  return {'pop':'一次组合popcount（DROP为输出丢弃低位数）','diff':'一次正负popcount差','mask':'64输入的符号/掩码及正负各16组OR4','shift':'一次固定权重位平面移位恢复','align':'一次可变尺度对齐加法','acc':'32次时间累计的一帧（含窗口内控制拍）','plane':'64输入单平面OR4/计数/32次累计一帧','bank':'64输入多平面/32次累计/恢复一帧，一个输出'}[c['family']]
 if n=='bf16_ppa_20261028' and c.get('kind')!='matrix':return '一次标量'+{'add2':'FP32加法','mul1':'BF16乘积/FP32输出','fma2':'BF16×BF16+FP32 FMA','fma3':'BF16×BF16+FP32 FMA'}[c['name']]
 return '一帧64项点积，'+str(m)+'个输出；非64×64全矩阵'
def main():
 packages=[];cases=[];profiles=[];hashes={};record_hashes={p.name:digest(p.read_bytes()) for p in (REG/'records').glob('*.json')}
 for package_index,(n,title,rid,primary) in enumerate(SPECS):
  base='architecture_tlm/'+n;path=base+'/results/FINAL_SUMMARY.json';raw=read(path);s=json.loads(raw);recordpath='digital_circuit_simulation_registry/records/'+rid+'.json';recraw=read(recordpath);rec=json.loads(recraw)
  rtls=subprocess.check_output(['git','ls-tree','-r','--name-only',REF,base+'/rtl'],cwd=R).decode().splitlines()
  code=[dict(path=p,absolute_path=str(R/p),present_locally=(R/p).exists(),sha256=digest(read(p)),github=URL+p) for p in rtls]
  packages.append(dict(id=package_index,name=n,title=title,run_id=rid,summary_path=path,summary_absolute_path=str(R/path),summary_present_locally=(R/path).exists(),summary_sha256=digest(raw),summary_github=URL+path,report_github=URL+base+'/results/REPORT_ZH.md',record_path=recordpath,record_sha256=digest(recraw),RTL=code,source=rec['source'],source_packages=s.get('source_packages',s.get('snapshots')),boundary=rec['boundary']))
  for i,x in enumerate(s['PPA']):
   c=x.get('case',{});name=c.get('name',x.get('top'));top=x.get('top',('me_' if n.startswith('module') else 'bf_' if n.startswith('bf16') else 'i8_')+name);m=x.get('M',1);family=c.get('family',title)
   arc=x.get('archive')
   entries=s.get('report_archives',s.get('archives',[]))
   if not arc:
    entries=[a for a in entries if Path(a['path']).parent.name==x['result_directory']];assert len(entries)==1;arc=entries[0]['path']
   a=next(a for a in entries if a['path']==arc);p=Path(arc);assert p.exists(),arc
   if arc not in hashes:hashes[arc]=digest(p.read_bytes())
   assert hashes[arc]==a['sha256'],arc
   rawarea=x['raw_area_um2'];area=x['area_55eq_um2'];assert math.isclose(area,.81*rawarea,rel_tol=1e-10)
   sta=x.get('reset_contract_sta',x);setup=sta.get('setup_slack_ns');hold=sta.get('hold_slack_ns');flags=x.get('review_flags',[])
   if setup is not None and hold is not None:status='有时序违例' if min(setup,hold)<0 else '余量非负'
   else:status='见原STA'
   if flags:status+='；有告警'
   cid=f'p{package_index}_c{i}';cfg={k:v for k,v in c.items() if k!='id'};cfg.update({k:x[k] for k in ['M','mode','snapshot'] if k in x})
   ps=x.get('profiles')
   if ps is None:ps={'active':dict(total_W=x['total_W'],energy_pJ=x['gross_pJ_per_operation'],cycles_per_operation=x['cycles_per_operation']),'idle':dict(total_W=x['idle_W'])}
   seq=(n!='module_energy_20261028' or c['family'] in ['acc','plane','bank']);lat=x.get('normal_latency_cycles',x.get('latency_cycles'));ii=x.get('initiation_interval_cycles',x.get('frame_interval_cycles'))
   if n=='int8_classic_ppa_20261028':ii=19
   case=dict(id=cid,package=package_index,name=name,top=top,family=family,configuration=cfg,primary_profile=primary,raw_area_um2=rawarea,area_multiplier=.81,area_55eq_um2=area,clock_MHz=s.get('clock_MHz',s.get('frequency_MHz')),period_ns=10,PVT=s['PVT'],clock_meaning='实际时钟约束' if seq else '组合DUT测量激励/虚拟时钟约束，无人工输入输出寄存',operation_definition=definition(n,c,m),normal_latency_cycles=lat,native_II_cycles=ii,configured_pipeline_registers=c.get('pipes'),setup_slack_ns=setup,hold_slack_ns=hold,raw_setup_slack_ns=x.get('raw_setup_slack_ns'),raw_hold_slack_ns=x.get('raw_hold_slack_ns'),timing_status=status,review_flags=flags,archive_absolute_path=arc,archive_sha256=a['sha256'],archive_bytes=p.stat().st_size,result_member='RESULT.json',result_member_sha256=a.get('result_member_sha256'),archive_access='本机授权归档，已核验归档SHA；其他机器需同路径原件或恢复索引',profile_names=list(ps))
   assert case['clock_MHz']==100
   cases.append(case)
   for mode,q in ps.items():
    energy=q.get('energy_pJ_per_operation',q.get('energy_pJ'));cycles=q.get('cycles_per_operation');power=q['total_W']
    if energy is not None:
     assert cycles is not None and math.isclose(energy,power*cycles*10*1000,rel_tol=1e-8),(n,name,mode)
    profiles.append(dict(case_id=cid,mode=mode,power_W=power,power_uW=power*1e6,energy_pJ_per_operation=energy,energy_std_pJ=q.get('energy_std_pJ'),measured_cycles_per_operation=cycles,measured_interval_ns=None if cycles is None else cycles*10,window_ns=q.get('window_ns'),operations=q.get('operations'),seeds=[17,503,1009]))
 assert len(cases)==66 and len(hashes)==66
 data=dict(date='2026-10-29',scope='Issue204既有66配置的派生查阅索引；其他模块见同目录00/01与04/08/09/10，不新增仿真run',reference_commit=REF,area_policy='raw*.81 once, original report bytes preserved; no power/time scaling',packages=packages,cases=cases,profiles=profiles,validation=dict(summary_files_verified=6,raw_archives_sha_verified=len(hashes),new_EDA_runs=0,model_PPL='not_run'))
 save(OUT/'MODULE_INDEX.json',data)
 fields=['package','run_id','name','top','mode','configuration','PVT','clock_MHz','period_ns','clock_meaning','raw_area_um2','area_55eq_um2','power_uW','energy_pJ_per_operation','measured_cycles_per_operation','measured_interval_ns','normal_latency_cycles','native_II_cycles','operation_definition','setup_slack_ns','hold_slack_ns','timing_status','review_flags','archive_absolute_path','archive_sha256','summary_absolute_path','summary_github','RTL_github']
 o=io.StringIO(newline='');writer=csv.DictWriter(o,fieldnames=fields,lineterminator='\n');writer.writeheader()
 for p in profiles:
  c=next(c for c in cases if c['id']==p['case_id']);pkg=packages[c['package']];r=dict(c,**p);r.update(package=pkg['name'],run_id=pkg['run_id'],summary_absolute_path=pkg['summary_absolute_path'],summary_github=pkg['summary_github'],RTL_github=' | '.join(x['github'] for x in pkg['RTL']),configuration=json.dumps(c['configuration'],ensure_ascii=False),review_flags=';'.join(c['review_flags']))
  writer.writerow({k:r.get(k) for k in fields})
 (OUT/'MODULE_MODES.csv').write_bytes(o.getvalue().encode('utf-8-sig'))
 lines=['# 矩阵与算术模块：功耗、面积、时钟及文件地址（2026-10-29）','',f'本页汇总Issue204已经完成的**66个配置、{len(profiles)}条运行模式均值**。这是既有结果索引，无新EDA、模型或PPL；不新增run，不改原件。此前8位比较器、sigmoid、计数流水及旧FP32/BF16原型见[04汇总](04_最新功耗面积汇总.md)，阈值库等见[10专题](10_阈值寄存器与全Q头资源估算.md)（完整根阅读镜像/对应任务分支）。全项目目录仍以[00](00_总览.md)/[01](01_结果地址索引.md)为准。','',
 '可筛选数据：[所有模式CSV](summaries/20261029_matrix204/MODULE_MODES.csv)、[完整配置/地址/来源SHA JSON](summaries/20261029_matrix204/MODULE_INDEX.json)。CSV为UTF-8 BOM方便本机Excel；JSON/Markdown为UTF-8 LF。原始报告字节不变。','',
 '**统一条件：SS / 1.08V / 125℃ / 100MHz（10ns）。面积同时保留raw与raw×0.81的55nm等效值，绝不二次折算；功率、能量和时间不缩放。** 组合模块也受100MHz/10ns测量与虚拟时钟约束，但无人工I/O寄存器，不能称其固有流水延迟为一拍。','',
 '功率随输入活动变化，主表只选active/replay/normal/matched/peak；所有sparse/dense/fullrange/paced/int8/idle模式保留在CSV/JSON。每次能量必须带操作定义：组合调用、32次时间累计一帧、64项点积一帧分别计量；M8一帧含8输出，不能当M1或整64×64矩阵。一律三seed均值。','',
 '测得窗口平均周期/次不等于原生pipeline latency或II，更不是Fmax；未知原生延迟留空。BF16单元的PIPES为上游寄存器配置，不替代实测握手周期。setup/hold非负也只是前布局报告，无CTS/SDF/SPEF/完整延迟毛刺；负值与告警均保留。','']
 for pkg in packages:
  cs=[c for c in cases if c['package']==pkg['id']];lines+=['## '+pkg['title'],'',f"run `{pkg['run_id']}`；[正式报告]({pkg['report_github']})、[冻结版本汇总]({pkg['summary_github']})。",'', '| top / 配置名 | raw面积 µm² | 55nm等效 µm² | 主模式 | 活动 µW | idle µW | pJ/次 | 窗口平均拍/次 | setup / hold ns | 时序 |','|---|---:|---:|---|---:|---:|---:|---:|---|---|']
  for c in cs:
   pp=[p for p in profiles if p['case_id']==c['id']];q=next(p for p in pp if p['mode']==c['primary_profile']);idle=next((p['power_uW'] for p in pp if p['mode']=='idle'),None)
   lines.append(f"| {c['top']} | {f(c['raw_area_um2'])} | {f(c['area_55eq_um2'])} | {q['mode']} | {f(q['power_uW'])} | {f(idle)} | {f(q['energy_pJ_per_operation'])} | {f(q['measured_cycles_per_operation'])} | {f(c['setup_slack_ns'])} / {f(c['hold_slack_ns'])} | {c['timing_status']} |")
  lines+=['', '源码与报告具体地址：','',f"- 汇总本机位置：`{pkg['summary_absolute_path']}`；{'当前稀疏checkout未展开，使用上方固定Git提交链接或git show读取' if not pkg['summary_present_locally'] else '当前本机可读'}。",f"- 源码文件："+'、'.join('['+Path(x['path']).name+']('+x['github']+')' for x in pkg['RTL'])+'。准确文件SHA和本机绝对位置见JSON packages.RTL。',f"- 中央记录：[records/{pkg['run_id']}.json](records/{pkg['run_id']}.json)；执行源ZIP/manifest、PVT/位宽/边界与历史失败索引均在此。",'- 每个top的原始归档绝对路径及SHA见CSV archive_absolute_path/archive_sha256；RESULT.json为归档内成员，综合报告在synthesis/，PT报告在各模式/pt/。档案不是工艺库本体。','']
  if pkg['name']=='module_energy_20261028':lines+=['popN_dD：N输入popcount输出丢D个低位，结果单位为2^D；shift是固定位权恢复，align为可变尺度移位相加。acc7..11为有符号饱和时间累计器；plane/bank含OR4和累计，bank77/54/50是状态总位数。不能把各模块毛能量直接相加当芯片；原组合校准偏差约23%，详见原报告。','']
  if pkg['name']=='bf16_ppa_20261028':lines+=['表中setup/hold采用相同网表、4.5..5.5ns外部reset释放契约补充STA；原始复位约束下负值仍在JSON raw_*及原报告。四独立标量hold仍−0.061165ns；N64虽非负，setup仅0.000027ns。normal与int8派生输入分列，不当同精度质量证明。','']
  if pkg['name']=='int8_parallel64_20261028':lines+=['同一32位结果核：满速2126.33µW /21.2633pJ /10ns，paced为114.8µW /40.18pJ /350ns；22位结果对应2118.33µW /21.1833pJ与108.933µW /38.1267pJ。paced时钟仍100MHz自由运行。初版hold负结果另存，不混用初版面积与最终功率。','']
 lines+=['## 长期入口与核验','',f'数值固定引用仓库提交`{REF}`，它是本索引读取版本，不冒称原执行提交；各run的实际source_base/未提交冻结manifest绑定保留在JSON packages.source。重建命令：`python work/rayggxia/204/int8_parallel64/build_power_index.py`。', '',f'此次6份汇总及源码均与固定Git对象逐字一致，66份所引原始报告归档SHA已核验，面积与能量单位检查通过。统一registry记录不变；不把重汇总算作新实验。源码/结果Git链接可跨机器访问；本机project_archives需授权目录，稀疏checkout未展开的源码不冒称本机已有实体文件。','', '后续新增模块继续在同任务PR登记run，并在本目录更新面向阅读的汇总入口；不要仅留聊天记录。']
 (REG/'11_矩阵与算术模块功耗面积时钟索引.md').write_bytes(('\n'.join(lines)+'\n').encode())
 assert record_hashes=={p.name:digest(p.read_bytes()) for p in (REG/'records').glob('*.json')}
 save(Path(__file__).with_name('POWER_INDEX_VALIDATION.json'),dict(reference_commit=REF,configurations=len(cases),profile_rows=len(profiles),source_summaries=6,archives_sha_verified=len(hashes),registry_records_unchanged=len(record_hashes),outputs=[dict(path=str(p.relative_to(R)),sha256=digest(p.read_bytes()),bytes=p.stat().st_size) for p in [REG/'11_矩阵与算术模块功耗面积时钟索引.md',OUT/'MODULE_INDEX.json',OUT/'MODULE_MODES.csv']],new_simulations=0))
 print(json.dumps(dict(configurations=len(cases),profile_rows=len(profiles),archives_sha_verified=len(hashes),records_unchanged=len(record_hashes))))
if __name__=='__main__':main()
