"""Register completed Spectre evidence and preserve limits of the analog readout."""
import csv,hashlib,json,tarfile
from pathlib import Path
TASK=Path(__file__).resolve().parents[3]
ROOT=TASK.parents[1]
WORK=TASK/'work/rayggxia/184'
FORMAL=TASK/'architecture_tlm/physical_rng_normal_readout/results/38387635'
DATA=ROOT/'analog_pbit_20261016/normal_readout_38387635'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
x=read(FORMAL/'REVIEW.json');archive=Path(x['archive']);obs=read(WORK/'OBSERVATION_38387635_6.json')
with tarfile.open(archive) as tar:summary=json.load(tar.extractfile('38387635/summary.json'))
lines=['常规偏置比较器完整通道：38387635正式结果 / 2026-10-25 / Issue184、PR185',
    '', '任务COMPLETED，Slurm退出0:0，8CPU分配、总用时3:45:08、累计CPU12:01:03。',
    'APS每案例单线程、最多8个独立案例并行，最终3个seed并行；不能把8核分配等同8倍加速。',
    '58案例结束、无Spectre error/warning；SVT20u的尾管饱和裕量不足，作为预期淘汰项保留。',
    '选中LVT20u，常规偏置10MOS＋原2MOS核心，1.2V/TT25°C/5fF，零外加核心电容；连续工作。',
    '输入对过驱动约190mV、gm/Id约12；连接核心的1mV确定性阶跃最坏延迟3.5ns（保存分辨率0.5ns）。',
    '独立校准62003/62009/62017完成后冻结Vref=0.604745V，验证期间未改。',
    'fmin500Hz、fmax100MHz、maxstep2.5ns、noisescale1；22ms总、预先丢弃2ms启动、20ms有效。',
    '实际每1us采一次，2ms到21.999ms，每seed恰好20000次；三个seed分别统计，没有拼接或删除MID。',
    '', '正式1us采样结果：', 'seed | 原始位数 | P(1) | MID个数/比例 | lag1相关 | lag100相关']
for r in x['validation']:
    q=r['raw'];lines.append('{} | {} | {:.3f}% | {}/{:.2f}% | {:.6f} | {:.6f}'.format(r['seed'],q['samples'],100*q['P1'],q['MID'],100*q['MID']/q['samples'],q['acf']['1'],q['acf']['100']))
lines+=['', '判读：1us间隔下未见旧比较器约0.5的强相邻相关，当前三条lag1为0.0054～0.0086。',
    'lag1小不是IID证明；seed64007的P1=48.795%，偏离50%约1.205个百分点，冻结参考后仍保留该结果。',
    '全部lag1/2/5/10/20/50/100见REVIEW.json；个别lag略超名义IID单项95%参考带，未做独立性认证。',
    '密集100ns序列lag100ns约0.272～0.273，不能把3.5ns阶跃速度解释为10MHz或更高的独立随机位率。',
    '', '读出可靠性：',
    '有效低<=0.24V、有效高>=0.96V；之间为MID，按0.6V判决的bit仅用于诊断，不能宣称可靠数字样本。',
    '原始32bit包每seed625个，含MID的包分别130/116/131个（20.80%/18.56%/20.96%）。',
    '177bit路径按实际6个32bit字装包，192个传输位全检查有效性；每seed104包，含无效电平84/71/76包。',
    '这包含最终丢弃的15bit填充位，是当前装包检查口径，不是仅对177个有效负载位的精确失败率。',
    '原始全部包无相邻重复或全零，但这不能抵消电平问题；对应位相关和汉明分布原件在quality.json。',
    '', '离线VN（必须先具备硬件可实现的有效读出）：', 'seed | VN有效输出数 | P(1) | 保留率 | 序列lag1']
for r in x['validation']:
    v=r['vn_valid'];lines.append('{} | {} | {:.3f}% | {:.3f}% | {:.6f}'.format(r['seed'],v['samples'],100*v['P1'],100*v['retention'],v['lag1']))
lines+=['VN相邻配对固定，没有挑选相位；丢弃无效电平对是明确的离线策略，使用了模拟电压有效性信息。',
    '真实电路目前没有有效性检测或锁存器，不能把VN_valid输出数当成已经实现的硬件吞吐。',
    'VN输出到达不等间隔，真实时间戳保留；序列lag不能等同固定物理时间lag。',
    '', '数值检查与范围：',
    '2.5ns→1.25ns短记录几乎一致；100MHz→200MHz通过预设宽容差工程检查，但跨seed平均P1差约1.76个百分点、ACF差约0.0226。',
    '因此属于首轮短精度screen通过，不等于严格带宽收敛或所有设置等价。正式结果仍使用100MHz。',
    '只有20ms有效/500Hz下的TT连续通道；10Hz长漂移、PVT、失配、PEX、共享选行/列线、锁存均未覆盖。',
    '未积分动态电流，未提供完整能量、面积或熵认证；三个噪声seed不等于三个同时物理阵列通道。',
    '', '建议下一步：冻结本轮电路/参考作为对照，加实际时钟控制的采样/再生锁存与负载，验证亚稳态和采样输出有效性。',
    '先用短任务检查噪声负载、建立和采样时序；不要通过删除MID、延长间隔或重调验证seed的Vref来掩盖读出问题。',
    '如需提高原始采样频率，0.5us是后续候选，应重新做实际相位/锁存/多seed验证；本轮不自动提交新仿真。',
    '', '数据：同目录seed64007/64013/64033_raw_1us.csv、raw_1us_bits.txt、VN及装包CSV、quality.json。',
    '原始CSV含raw_index,time_s,core_V,comparator_V,bit,level,level_valid。MID全部保留。',
    '完整归档：'+str(archive), '归档SHA256：'+x['archive_sha256'],
    '远端归档：/public3/home/t6s011227/analog_pbit_20261016/normal_readout_v1/normal_readout_38387635.tar.gz',
    '536成员逐SHA、24执行源、60000采样点按原PSF重数、CSV/TXT/时间戳/P1/MID/多lag/VN一致性通过。',
    '未持久解压大波形：只保留一个44MB原包、小型审计和逐位CSV/TXT，临时波形已由TemporaryDirectory回收。']
report='\n'.join(lines)+'\n'
for p in (FORMAL/'REPORT_ZH.txt',DATA/'REPORT_ZH.txt'):p.write_text(report,encoding='utf-8',newline='\n')
# Formal recovery index only needs the archive, selected provenance and exported members.
index=read(FORMAL/'ARCHIVE_INDEX.json')
selected={k:v for k,v in index['members'].items() if k in ('summary.json','result_manifest.json','metadata.json','config.json','frozen_reference.json','numerical_screen.json','parallel_summary.json') or k.startswith('source/') or k.startswith('validation_seed')}
index.update(members=selected,total_archive_members=536,omitted_member_checksums='All535 nonmanifest member checksums are inside38387635/result_manifest.json in the signed archive; all536 verified by analysis/review_38387635.py.')
save(FORMAL/'ARCHIVE_INDEX.json',index)
exports=read(DATA/'manifest.json')
for name in ('REPORT_ZH.txt','REVIEW.json'):
    p=DATA/name;exports[name]=dict(bytes=p.stat().st_size,sha256=digest(p),derived=True)
save(DATA/'manifest.json',exports)
save(FORMAL/'EXPORT_MANIFEST.json',exports)
def artifact(p,role):return dict(path=str(p),role=role,present_at_registration=True,required=True,bytes=p.stat().st_size,sha256=digest(p))
for base in (TASK,ROOT):
    path=base/'digital_circuit_simulation_registry/records/physical-rng-normal-38387635.json';r=read(path)
    r.update(name='常规偏置10MOS比较器38387635（已完成，读出仍含MID）',status='completed_recounted_readout_limitations',
        boundary='原2MOS核心＋常规偏置10MOS比较器＋5fF输出，连续TT25C/500Hz通道。三独立新seed各20000次，参考独立校准冻结；原SVT20u OP淘汰保留。实际输出有0.63%～0.70%MID，尚无锁存。')
    r['stages']['functional']='completed_60000_samples_recounted_readout_validity_incomplete'
    compact=[dict(seed=v['seed'],raw=v['raw'],vn_valid={k:w for k,w in v['vn_valid'].items() if k not in ('blocks','arrival_gap_s')}) for v in x['validation']]
    r['conditions'].update(observed_utc=obs['observed_utc'],observed_slurm_state='COMPLETED',elapsed_slurm='03:45:08',total_CPU='12:01:03',actual_validation_samples_per_seed=20000,validation_samples_total=60000,frozen_reference_V=x['frozen_reference_V'],validation_summary=compact)
    r['conditions'].pop('validation_progress',None)
    r['cases']=[]
    for row in summary['cases']:
        small=dict(case=row['case'],status=row['status'],elapsed_s=row['simulator_elapsed_s'],check_error=row.get('check_error'),complete=True,kind=row['setting']['kind'])
        if row['setting']['kind']=='noise':
            m=row['metrics'];small['noise']=dict(dense_P1=m['p1'],dense_MID_fraction=m['midrail_fraction'],actual_samples=m['actual_sample_bits'],actual_P1=m['actual_P1'],actual_MID=m['actual_MID'])
        if row['setting']['kind']=='step':small['step_max_delay_s']=row['metrics']['maximum_delay_s']
        r['cases'].append(small)
    for p,role in ((archive,'completed_original_archive'),(WORK/'OBSERVATION_38387635_6.json','completed_slurm_observation'),(FORMAL/'REVIEW.json','independent_original_waveform_recount'),(FORMAL/'REPORT_ZH.txt','completed_results_and_limits'),(FORMAL/'ARCHIVE_INDEX.json','archive_recovery_index'),(FORMAL/'EXPORT_MANIFEST.json','raw_export_byte_index')):
        a=artifact(p,role)
        if TASK in p.parents:a['repository_path']=p.relative_to(TASK).as_posix()
        r['artifacts'].append(a)
    r['limitations']=x['limitations']
    r['next_action']='Review completed PR185 results. Before direct hardware reseeding, add and test real sampled/latching readout, metastability/validity,load and energy; preserve this frozen baseline. No automatic newjob.'
    save(path,r)
    inventory=base/'digital_circuit_simulation_registry/archive_inventory.csv'
    with inventory.open(encoding='utf-8',newline='') as f:reader=csv.DictReader(f);fields=reader.fieldnames;records=list(reader)
    assert not any(row['path']==str(archive) for row in records)
    records.append(dict(path=str(archive),bytes=archive.stat().st_size,sha256=x['archive_sha256'],linked_records=r['id'],review_state='completed_all536_members_recounted',note='38387635常规比较器；保留预期OP失败与MID，非完整数字有效性或熵认证'))
    with inventory.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(records)
note=('2026-10-25 Issue184/PR185最终结果本地复核完成：Slurm38387635 COMPLETED/0:0，3:45:08、8CPU/累计12:01:03；58案例，预期SVT20u尾管OP淘汰保留，Spectre零error/warning。'
      '原包44,059,813B、SHA d7112d162e1a22351d4e745be22669bae66ffd37d2af2d13805a70e04eebd8f0在project_archives/normal_readout_20261025/results；536成员、24执行源、60000原PSF采样重数及CSV/TXT/时间戳/多lag/VN一致。'
      'LVT20u/1.2V/5fF/TT25C/500Hz/连续工作，独立校准冻结0.604745V；新64007/13/33各22ms总、丢2ms、1us/20000次，P1=.48795/.49805/.49865，lag1=.008577/.006336/.005443，MID140/126/138。'
      'MID仍.63%～.70%，原32bit种子包含MID130/116/131个/625（18.56%～20.96%）；不能将软件阈值bit直接称可用数字种子。离线VN_valid4855/4896/4813位、P1=.494954/.497549/.504467，约24%保留；有效性oracle未在硬件实现。'
      '100ns密集rho约.273，不能把3.5ns确定性延迟当独立位率；100→200MHz短screen通过宽容差但均值P1差1.76pp/ACF差.0226，不宣称严格带宽收敛。'
      '原件/报告/逐位数据analog_pbit_20261016/normal_readout_38387635，正式报告architecture_tlm/physical_rng_normal_readout/results/38387635/REPORT_ZH.txt。'
      '下一步优先真实时钟/采样再生锁存、电平有效性和亚稳态，再考察共享接口；本轮未新提交、未改快照，无10Hz长漂移/PVT/PEX/动态能耗/熵认证。PR/Issue未自动合并或关闭，最终远端发布见PUBLICATION_RESULTS.json。')
canonical=ROOT/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';mirror=ROOT/'PROJECT_MEMORY_ZH.md';assert canonical.read_bytes()==mirror.read_bytes()
for p in (canonical,TASK/'PROJECT_MEMORY_ZH.md'):
    text=p.read_text(encoding='utf-8');mark='## 6 随机源、p-bit与相关性\n';assert mark in text and note not in text
    p.write_text(text.replace(mark,mark+'\n'+note+'\n',1),encoding='utf-8',newline='\n')
mirror.write_bytes(canonical.read_bytes())
for p in (WORK/'HANDOFF.md',TASK/'progress/rayggxia/STATUS.md'):
    with p.open('a',encoding='utf-8',newline='\n') as f:f.write('\n'+note+'\n')
path=ROOT/'analog_pbit_20261016/normal_readout_v1_delivery.json';d=read(path)
d.update(observed_utc=obs['observed_utc'],status_at_observation='COMPLETED',actual_20k_new_comparator_results_complete=True,review_pass=True,readout_all_samples_valid=False,archive=str(archive),archive_sha256=x['archive_sha256'],result_data=str(DATA))
d.pop('validation_progress',None);save(path,d)
save(WORK/'RESULT_VERIFICATION.json',dict(job=38387635,archive_sha256=x['archive_sha256'],all536_member_hashes_pass=True,source24_pass=True,raw60000_recount_pass=True,source_unchanged=True,report=str(FORMAL/'REPORT_ZH.txt'),data=str(DATA),entropy_certified=False,raw_digital_validity_complete=False))
print('Final results, packet limitations, registry and samebyte memory mirror recorded.')
