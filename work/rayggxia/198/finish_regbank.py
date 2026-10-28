"""Verify original EDA bytes, summarize only measured boundaries, register union."""
from pathlib import Path
import hashlib,json,tarfile,statistics,re,shutil,subprocess,sys,csv,io
R=Path(__file__).resolve().parents[3];WS=R.parents[1];W=Path(__file__).parent
C=R/'architecture_tlm/attention_compare_20261027/regbank_20261029'
A=WS/'project_archives/attention_compare_issue198_20261027/regbank_20261029'
RID='attention-regbank-198-eda-20261029'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(d,indent=2,ensure_ascii=False)+'\n').encode())
def verify_archive(path,index,extra):
 n=0
 with tarfile.open(path) as t:
  for m in t.getmembers():
   assert m.isfile(),m.name
   b=t.extractfile(m).read();h=hashlib.sha256(b).hexdigest()
   if m.name in extra:assert h==extra[m.name]
   else:assert h==index[m.name]['sha256'] and len(b)==index[m.name]['bytes'],m.name
   n+=1
 return n
def main():
 receipt=read(A/'COLLECTION.json');hist=read(A/'HISTORY_COLLECTION.json');idx=read(A/'RAW_INDEX.json')
 assert sha(A/'RESULTS.json')==receipt['results_sha256'] and sha(A/'RAW_INDEX.json')==receipt['index_sha256']
 assert sha(A/'REPORTS.tar.gz')==receipt['archives']['REPORTS']['sha256']
 assert sha(A/'HISTORY.tar.gz')==hist['sha256'] and sha(A/'HISTORY_INDEX.json')==hist['index_sha256']
 members=verify_archive(A/'REPORTS.tar.gz',idx,{'collection/RAW_INDEX.json':receipt['index_sha256']})
 historical=verify_archive(A/'HISTORY.tar.gz',read(A/'HISTORY_INDEX.json'),{'HISTORY_INDEX.json':hist['index_sha256']})
 data=read(A/'RESULTS.json');rows=[];audit=[]
 for n,h in read(C/'SOURCE.json')['files'].items():assert sha(C/n)==h,n
 assert data['source']==read(C/'SOURCE.json')
 with tarfile.open(A/'REPORTS.tar.gz') as t:
  for x in data['results']:
   top=x['case']['top'];win={}
   for name in ['load','sample_hold','idle','transaction']:
    z=[y for y in x['windows'] if y['window']['name']==name];assert len(z)==3
    win[name]=dict(power_uW=statistics.mean(y['power']['total_W']*1e6 for y in z),energy_pJ=statistics.mean(y['energy_pJ'] for y in z),energy_std_pJ=statistics.stdev(y['energy_pJ'] for y in z),cycles=z[0]['window']['cycles'])
   row=dict(**x['case'],raw_area_um2=x['raw_area_um2'],area55_mm2=x['area55_um2']/1e6,counts=x['counts'],register_raw_area_per_bit_um2=x['area_groups_raw_um2']['register']/x['counts']['register'],setup_ns=x['worst_setup_ns'],hold_ns=x['worst_hold_ns'],windows=win)
   rows.append(row);p='results/'+top+'/gate_17/sample_hold/'
   disabled=t.extractfile(p+'disabled.rpt').read().decode();exceptions=t.extractfile(p+'exceptions.rpt').read().decode();hold=t.extractfile(p+'hold.rpt').read().decode()
   flags=sorted(set(re.findall(r'(?:positive_unate|negative_unate|non_unate)\s+(\w)\s',disabled)))
   assert set(flags)<=set('pCc') and not re.search(r'false_path|multicycle_path',exceptions)
   assert 'check_timing succeeded' in t.extractfile(p+'check_timing.rpt').read().decode()
   worststart=re.search(r'Startpoint: (.+)',hold)
   audit.append(dict(top=top,disabled_arc_flags=flags,user_false_multicycle=False,first_violating_hold_startpoint=worststart[1] if worststart else None,check_timing_succeeded=True))
   for y in x['windows']:
    s=y.pop('check_power_text');y['power_check_warnings']=re.findall(r'Warning:.*',s)
    y['power_check_pass']='check_power succeeded' in s
    y['power_check_sha256']=idx['results/'+top+'/gate_'+str(y['seed'])+'/'+y['window']['name']+'/check_power.rpt']['sha256']
 assert len(rows)==7 and sum(len(x['windows']) for x in data['results'])==84
 assert sum(len(x['checks']) for x in data['results'])==42
 assert sum(y['checked'] for x in data['results'] for y in x['checks'])==8610
 data['original_results_sha256']=receipt['results_sha256'];data['timing_audit']=audit
 data['limitations']=['Prelayout zero-delay mapped VCD; no CTS/SPEF/SDF or complete glitch model. Power not silicon measurement.',
 '16-bit gated banks hold=-0.010220 ns at wr_data input; 12-bit margin only +0.004787 ns. SS only, not physical signoff.',
 'Both comparator variants retain 256 low-ramp table extrapolations per window. No missing power tables/functions; gate root slew corrected.',
 'Synthetic three-seed thresholds/random words, not measured Qwen activity; no new model/PPL conclusion.',
 'No FP conversion/max/LUT/RNG/arbiter/address map/V/accumulation. Random source and clock/data distribution upstream are not free.',
 'Score bank is an optional simultaneously retained staging buffer; its scheduling/removal requires separate proof. All-layer area multiplication only for physical replication.']
 write(C/'RESULTS.json',data)
 d={x['top']:x for x in rows};score=d['bank_w11_g1_c0'];control_area=.01167158161863
 scaling=[]
 for width in [12,16]:
  bank=d[f'bank_w{width}_g1_c0'];drive=d[f'bank_w{width}_g1_c1']
  scaling.append(dict(width=width,threshold_bits_per_head=128*width,score_bits_per_head=128*11,
    threshold32_KiB=128*width*32/8192,score32_KiB=128*11*32/8192,
    threshold32_area55_mm2=bank['area55_mm2']*32,threshold32_hold_mW=bank['windows']['sample_hold']['power_uW']*32/1000,
    driver32_area55_mm2=drive['area55_mm2']*32,driver_score32_area55_mm2=(drive['area55_mm2']+score['area55_mm2'])*32,
    driver_score_control32_area55_mm2=(drive['area55_mm2']+score['area55_mm2']+control_area)*32,
    driver32_sample_mW=drive['windows']['sample_hold']['power_uW']*32/1000,
    driver_energy_all36layers_nJ=drive['windows']['transaction']['energy_pJ']/1000*32*36,
    threshold_energy_all36layers_nJ=bank['windows']['transaction']['energy_pJ']/1000*32*36,
    driver_score_energy_all36layers_nJ=(drive['windows']['transaction']['energy_pJ']+score['windows']['transaction']['energy_pJ'])/1000*32*36,
    assumption='Same synthetic transaction per query-head; 32 heads x36 layers, batch1 decode. Energy excludes inter-query gaps and external costs. Modular area sum, no integration closure.'))
 summary=dict(rows=rows,scaling=scaling,control_area55_mm2_per_head=control_area,score_area55_mm2_per_head=score['area55_mm2'],reuse_head_counts=[1,4,8,32],area_scale=.81)
 write(C/'SUMMARY.json',summary)
 labels=['12位/CE常开时钟','12位/真实ICG','16位/CE常开时钟','16位/真实ICG','12位/ICG+128比较器','16位/ICG+128比较器','11位/ICG分数缓存']
 table='\n'.join(f"|{label}|{x['raw_area_um2']/1e6:.6f}|{x['area55_mm2']:.6f}|{x['windows']['load']['energy_pJ']:.2f}|{x['windows']['sample_hold']['power_uW']:.2f}|{x['windows']['transaction']['energy_pJ']/1000:.6f}|{x['hold_ns']:.6f}|" for label,x in zip(labels,rows))
 scale_table='\n'.join(f"|P{x['width']}|{x['threshold32_KiB']:.1f}|{x['threshold32_area55_mm2']:.4f}|{x['threshold32_hold_mW']:.3f}|{x['driver32_area55_mm2']:.4f}|{x['driver_score_control32_area55_mm2']:.4f}|{x['driver_energy_all36layers_nJ']/1000:.3f}|" for x in scaling)
 reuse_table='\n'.join(f"|{h}|{32//h}|{(d['bank_w12_g1_c1']['area55_mm2']+score['area55_mm2']+control_area)*h:.4f}|{(d['bank_w16_g1_c1']['area55_mm2']+score['area55_mm2']+control_area)*h:.4f}|{1.68*(32//h):.2f}|" for h in [1,4,8,32])
 report='''# 128节点 Ising 概率阈值寄存器：实测模块与全部 Q 头资源预算

2026-10-29，Issue198 / draft PR199，rayggxia。**预存阈值的成本不能忽略，但正确门控后的寄存器保持功耗并没有随128次更新爆炸；并行比较和随机供给需要单独预算。** 本轮提供目标库DC/门级/PT前布局结果，不是芯片实测或完整Ising签核。

## 单头模块结果

128个位置、16字/拍写端口（8拍装满），ICG版本每4字使用一个真实CKGTX8，共32个，防止综合合并门控造成大扇出。门控DFFQX1原面积7.2μm²/bit，55nm折算5.832μm²/bit；CE版本映射使能寄存器平均折算7.8732μm²/bit，不能用裸DFF单价替代它。表中面积包含写译码/门控和综合逻辑；比较器行已包含阈值寄存器，不再重复相加。

SHARK原几何面积×0.81另列，功率/能量/时间不缩放。SS SVT 1.08V/125°C，100MHz；三seed=17/503/1009，表为算术均值。窗口：装载8拍，采样/保持160拍，事务168拍=1.68μs；另测空闲32拍。160更新用于对齐当前S128+burn32实验计数，不构成“必须预热32次”的新结论。

|模块|原面积 mm²|55nm折算 mm²|8拍装载 pJ|采样/保持功率 μW|完整168拍 nJ|hold ns|
|---|---:|---:|---:|---:|---:|---:|
'''+table+'''

纯12位阈值库1536bit，门控后保持功率915→33.17μW（约27.6倍），完整事务能量1.550864→0.084722nJ（约18.3倍）；16位2048bit，1220→37.69μW（约32.4倍），2.068080→0.102183nJ（约20.2倍）。装载仍需30.65/40.53pJ，不能记零。ICG本身输入时钟仍翻转，保持功率含其内部功耗与泄漏。

加128路比较器后，12/16位完整事务约0.605808/0.796656nJ，采样期358.1/470.9μW，已显著高于只保持寄存器。随机字由testbench输入，**随机数发生器本体未计**。32头全并行，P16每拍需65536个随机输入bit（P12为49152bit）；这是接口吞吐需求，不等价于必须复制同数量独立RNG，也不能默认高质量随机数免费。

## Qwen3-4B 全部 Q 头的条件预算

当前模型每层32个Q头、36层；GQA共享K/V不表示四个Q头的score/概率阈值相同。以下按batch1 decode、一层32头全并行，跨36层复用硬件。面积只乘32；每token跨层活动次数为32×36=1152。若另外物理复制36层，面积才再乘36。

|概率精度|32头阈值容量 KiB|仅阈值库面积 mm²|阈值保持 mW|阈值库+比较器面积 mm²|再加11位score库及旧控制面积 mm²|阈值库+比较器跨36层 μJ/token|
|---|---:|---:|---:|---:|---:|---:|
'''+scale_table+'''

全部面积为55nm折算标准单元之和，未含布线/利用率/宏边界。额外11位score缓存共45056bit=5.5KiB、0.273311mm²；阈值+score合计11.5/13.5KiB。若score用12位，则合计12/14KiB，面积再增加约0.023888mm²。分数缓存是“需同时保留分数和阈值”的预算，不断言最终必须同时保存；能否复用存储要结合max、查表和QK流水证明，不能先扣掉。

旧G16反馈/仲裁控制折算0.011671582mm²/头，32头0.373491mm²；上表加上它后的1.133/1.293mm²只是已知模块拼加。尚未计分数转定点、整数max/差值、阈值LUT及读端口、RNG、候选到token地址映射、V读取和累加。前端QK/SparQ筛选也未计。完整Ising仍不能用该部分面积或能量代替。

仅阈值库跨36层能量约0.098/0.118μJ/token；阈值库+比较器约0.698/0.918μJ/token；若11位score库也每头执行相同168拍事务，则二者合计约0.793/1.013μJ/token。它们是本轮合成活动外推，未计其他层计算期间的保持/空闲时间。旧控制0.923nJ来自p=1/32、S128/burn0，和本轮均匀阈值、160更新不匹配，**不直接相加声称已测完整采样能量**。

## 面积与复用的选择

无需默认32头全部复制；H套硬件处理32头，面积按H缩放，但不应仅为省面积把延迟无限增加：

|硬件头数 H|32头批数|P12部分面积 mm²|P16部分面积 mm²|仅各批装载+160更新时间 μs|
|---|---:|---:|---:|---:|
'''+reuse_table+'''

面积列包括阈值库+比较器+11位score库+旧控制；时间列仅168拍模板×批数，假设每套每拍供应16个阈值，批间不重叠。它不包含阈值生成、控制重取/流水尾、QK/V/累加，因此不是整个层或模型时延。装载8拍要求上游有相应查表吞吐，单读口ROM将是128拍；没有把ROM复制/端口成本藏在8拍假设里。减少并发主要降低峰值面积/功率，不保证1152次工作总能量同比下降。

我的判断：优先保留真实时钟门控；先用P12/P16作为精度与能耗两个候选，不直接降为8位。寄存器保持不再是最大已测活动项，但32头复制的存储、比较器和控制面积已到约1mm²级，绝不能称几乎免费。下一项对结论最敏感的是匹配吞吐及随机质量的RNG/LUT前端，之后再和相同质量、相同KV布局的精确softmax+采样比较。

## 验证、限制与复现

7个top、3seed、RTL与综合网表42条通过，合计8904个执行拍，其中8610拍在完整装载后对独立Python oracle核验；初始7拍没有定义全部存储，禁止消费。无数据reset，不用X当合法数据。84个PT窗口均100% net/leaf cell活动标注。全部setup非负，最小4.887380ns；门控16位两top的wr_data输入hold为−0.010220ns，门控12位仅+0.004787ns；尚需真实上游路径与时钟树闭合，不能靠随意改输入约束宣称通过。

比较器两top每窗口保留256个过快内部边沿的库表外推告警（报表四舍五入约0.02ns，库下限0.02ns），其功耗为带告警估算；其他五top check_power通过。没有缺失power table/function。禁用弧为常量/条件传播，ICG TE固定0；无用户false/multicycle路径。DC签名转换/命名警告保留。纯bank输出每bit负载2fF，比较器128个输出各20fF；内部使用映射实际扇出，无布线寄生。

首轮Windows路径分隔符问题发生在上传校验，无作业；v2 Python参数括号语法失败在EDA前；v3单门控库功能/DC通过，但PT根时钟零slew造成32个库外推，修正根输入slew为0.1ns后仅重算PT。v4两组未门控对照的空ICG集合产生SEL-005，严格日志门禁停止；v5只加quiet并复用已验证DC/波形、完成缺少的门级seed和PT，其余五组直接引用v4。所有旧失败/告警保留在HISTORY归档，不将重复PT当新实验。

代码`bank.sv/tb.sv/generate.py/runner.py/repair.py/common.tcl/dc.tcl/pt.tcl/collect.py`及SOURCE保留。向量不入Git，精确字节在各source_v*.zip/RAW归档，generator可重建；模型/tokenizer/语料不适用于本次合成RTL测试，无新GPU/PPL。v4 Slurm38447688，修复38447724；早期38447560失败、38447569有效功能/旧slew功耗保留。执行父提交1f4dff93，最终发布SHA见REGBANK_PUBLICATION.json。

原报告、历史和索引SHA见work/rayggxia/198/REGBANK_ARCHIVE.json及REGBANK_COLLECTION_CHECK.json；统一台账run `attention-regbank-198-eda-20261029`。完整网表/VCD包留授权EDA服务器，本地保存原报告与失败历史，不上传工艺库或凭据。PR199保持draft待审、Issue198开放，Projects沿既有权限限制待维护者同步。
'''
 (C/'REPORT_ZH.md').write_bytes(report.encode())
 artifacts=[]
 for p,role in [(C/'RESULTS.json','public_numeric'),(C/'SUMMARY.json','all_heads_scaling'),(A/'REPORTS.tar.gz','private_original_reports'),(A/'HISTORY.tar.gz','private_negative_history'),(A/'RAW_INDEX.json','private_raw_index'),(A/'COLLECTION.json','private_raw_archive_location')]+[(p,'immutable_source_archive') for p in sorted(A.glob('source_v*.zip'))]:
  artifacts.append(dict(path=str(p),role=role,present_at_registration=True,required=True,bytes=p.stat().st_size,sha256=sha(p)))
 write(W/'REGBANK_ARCHIVE.json',dict(local_artifacts=artifacts,remote_raw=dict(bytes=receipt['archives']['RAW']['bytes'],sha256=receipt['archives']['RAW']['sha256'],downloaded=False,private_location_index=str(A/'COLLECTION.json'))))
 write(W/'REGBANK_COLLECTION_CHECK.json',dict(report_members_verified=members,history_members_verified=historical,original_index_files=len(idx),source_files_verified=len(data['source']['files']),functional_unique_checks=42,executed_cycles=8904,checked_cycles=8610,PT_final_windows=84,source_immutable=True,original_results_sha256=receipt['results_sha256']))
 cases=[]
 for x in data['results']:
  for y in x['windows']:
   cases.append(dict(top=x['case']['top'],width=x['case']['width'],seed=y['seed'],window=y['window'],raw_area_um2=x['raw_area_um2'],area_55nm_equivalent_um2=x['area55_um2'],power_W=y['power']['total_W'],energy_J=y['energy_pJ']*1e-12,setup_ns=y['slacks_ns']['setup'],hold_ns=y['slacks_ns']['hold'],power_check_pass=y['power_check_pass'],power_warnings=y['power_check_warnings'],power_report_sha256=y['report_sha256']))
 record=dict(schema_version=1,id=RID,name='128字阈值/分数寄存器与并行比较器：7top/84PT窗口',family='Attention/寄存器/概率比较',registered_on='2026-10-29',owner='rayggxia',issue=198,evidence_level='DC_GATE_PT_PRELAYOUT',status='calculated_with_hold_and_ramp_warnings',stages=dict(functional='pass',synthesis='completed',sta='violations',power='calculated',postlayout='not_run'),boundary=data['boundary'],conditions=dict(node_nm=65,target_equivalent_area_nm=55,area_only_scale=.81,corner='SS',voltage_V=1.08,temperature_C=125,clock_MHz=100,seeds=[17,503,1009],window_ns=None,load_pF={'bank':.002,'compare':.02},input_transition_ns=.1,io_max_ns=1.,io_min_ns=.2,setup_uncertainty_ns=.5,hold_uncertainty_ns=.05,sdf=False,spef=False,cts=False,words=128,widths=[11,12,16],load_words_per_cycle=16,updates=160,activity='Synthetic Python PRNG, thresholds uniform [0,0.5] with boundaries; zero-delay gate VCD averaged PT'),source=dict(git_commit=None,parent_commit=data['source']['parent_commit'],source_manifest_sha256=sha(C/'SOURCE.json'),binding='v5 final manifest; five completed v4 cases, v3 proof reuse and v5 partial continuation recorded per-case; old immutable archives retained'),artifacts=artifacts,cases=cases,limitations=data['limitations'],next_action='Close 16-bit input hold and comparator low-ramp extrapolation with physical interface; integrate measured-throughput LUT and qualified RNG before total Ising comparison')
 p=R/'digital_circuit_simulation_registry/records'/f'{RID}.json';write(p,record)
 register(p,artifacts)
 print(json.dumps(dict(rows=rows,scaling=scaling,report_members=members,history_members=historical),ensure_ascii=False))

def register(record_path,artifacts):
 reg=WS/'digital_circuit_simulation_registry';check=W/'.eda_private/regbank_registry_check';check.mkdir(exist_ok=False)
 names=['catalog.json','archive_inventory.csv','00_总览.md','01_结果地址索引.md','runs.csv','artifact_locations.csv']
 pre={n:sha(reg/n) for n in names};old={p.name:sha(p) for p in (reg/'records').glob('*.json')}
 for n in ['registry.py','catalog.json','archive_inventory.csv']:shutil.copyfile(reg/n,check/n)
 shutil.copytree(reg/'records',check/'records')
 subprocess.run([sys.executable,str(check/'registry.py'),'add',str(record_path)],check=True)
 rows=[dict(path=x['path'],bytes=x['bytes'],sha256=x['sha256'],linked_records=RID,review_state='sha_verified_local',note='same regbank run; original reports/history/source snapshots') for x in artifacts if x['path'].endswith(('.tar.gz','.zip'))]
 fields=['path','bytes','sha256','linked_records','review_state','note'];s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=fields,lineterminator='\n');w.writerows(rows)
 with (check/'archive_inventory.csv').open('ab') as f:f.write(s.getvalue().encode())
 s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows);(W/'REGBANK_ARCHIVE_INVENTORY_APPEND.csv').write_bytes(s.getvalue().encode())
 p=subprocess.run([sys.executable,str(check/'registry.py'),'check'],capture_output=True,text=True,check=True);write(W/'REGBANK_REGISTRY_CHECK.json',json.loads(p.stdout))
 subprocess.run([sys.executable,str(check/'registry.py'),'render'],check=True)
 assert pre=={n:sha(reg/n) for n in names} and old=={p.name:sha(p) for p in (reg/'records').glob('*.json')}
 backup=A/'reading_preimages';backup.mkdir()
 for n in names:shutil.copyfile(reg/n,backup/n)
 assert not (reg/'records'/record_path.name).exists();shutil.copyfile(record_path,reg/'records'/record_path.name)
 for n in names:shutil.copyfile(check/n,reg/n)
 assert all(sha(reg/'records'/n)==s for n,s in old.items())
 write(W/'REGBANK_REGISTRY_SYNC.json',dict(old_records=len(old),new_records=len(old)+1,all_old_records_unchanged=True,record_sha256=sha(record_path),preimages=str(backup)))
if __name__=='__main__':main()
