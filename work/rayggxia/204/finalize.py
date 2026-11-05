"""Verify archived bytes and summarize each actual run without re-running EDA."""
from pathlib import Path
import hashlib,json,math,shutil,statistics,tarfile,zipfile
ROOT=Path(__file__).resolve().parents[3]
WS=ROOT.parents[1]
PKG=ROOT/'architecture_tlm/matrix_validation_20261028'
HERE=Path(__file__).resolve().parent
ARCH=WS/'project_archives/matrix204_t32_20261028'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def main():
 snapshots=[];archive_records=[];functional=[];candidates={};failures=[]
 packs=ARCH/'execution_packages';packs.mkdir(exist_ok=True)
 for p in sorted((HERE/'private').glob('matrix204_*.zip')):
  dst=packs/p.name
  if dst.exists():assert sha(dst)==sha(p)
  else:shutil.copyfile(p,dst)
  with zipfile.ZipFile(dst) as z:
   b=z.read(p.stem+'/EXECUTION_MANIFEST.json');m=json.loads(b)
   for n,h in m['files'].items():assert hashlib.sha256(z.read(p.stem+'/'+n)).hexdigest()==h,n
  snapshots.append({'snapshot':p.stem,'path':str(dst),'sha256':sha(dst),'bytes':dst.stat().st_size,
    'source_manifest_sha256':hashlib.sha256(b).hexdigest(),'members_verified':len(m['files'])})
 for f in sorted(ARCH.glob('matrix204_*/**/reports.tar.gz')):
  with tarfile.open(f) as t:
   index=json.load(t.extractfile('RETURN_MANIFEST.json'))['files']
   for n,h in index.items():assert hashlib.sha256(t.extractfile(n).read()).hexdigest()==h,n
   r=json.load(t.extractfile('RESULT.json'))
  archive_records.append({'path':str(f),'sha256':sha(f),'bytes':f.stat().st_size,'members_verified':len(index),'status':r['status']})
  if 'functional_' in f.parent.name:functional.append({'snapshot':f.parent.parent.name,'M':r['M'],'cases':r['cases'],'status':r['status']})
  else:
   if r['status']!='calculated':failures.append({'snapshot':f.parent.parent.name,'top':r['top'],'status':r['status'],'error':r.get('error')});continue
   if len(r['windows'])!=6:raise ValueError('Need all 3 seeds, active/idle')
   top=r['top']
   if top in candidates:raise ValueError('Duplicate completed PPA should be explicitly selected '+top)
   candidates[top]=dict(result=r,archive=str(f))
 rows=[]
 for top,item in sorted(candidates.items()):
  r=item['result'];a=[w for w in r['windows'] if w['mode']=='active'];idle=[w for w in r['windows'] if w['mode']=='idle']
  assert len(a)==len(idle)==3
  row={'top':top,'M':r['M'],'mode':r['mode'],'archive':item['archive'],'seeds':[w['seed'] for w in a]}
  for k in ['raw_area_um2','area_55eq_um2','total_W','internal_W','switching_W','leakage_W','gross_pJ_per_operation','cycles_per_operation']:
   row[k]=statistics.mean(w[k] for w in a)
  row.update(energy_std_pJ=statistics.pstdev(w['gross_pJ_per_operation'] for w in a),
    idle_W=statistics.mean(w['total_W'] for w in idle),setup_slack_ns=min(w['setup_slack_ns'] for w in r['windows']),
    hold_slack_ns=min(w['hold_slack_ns'] for w in r['windows']),
    all_mapped_pin_activity_verified=all(w['all_mapped_pin_activity_verified'] for w in r['windows']),
    review_flags=sorted({v for w in r['windows'] for v in w['review_flags']}),
    latency_cycles_range=[min(v for w in a for v in w['latency_cycles_per_frame']),max(v for w in a for v in w['latency_cycles_per_frame'])],
    windows=[{k:w[k] for k in ['seed','mode','total_W','gross_pJ_per_operation','window_ns','operations','setup_slack_ns','hold_slack_ns','review_flags']} for w in r['windows']])
  row['constant_top_port_proofs']=[w.get('constant_top_port_proofs',[]) for w in r['windows'] if w.get('constant_top_port_proofs')]
  row['groups']={}
  for name in a[0].get('groups',{}):
   row['groups'][name]={'cells':a[0]['groups'][name]['cells'],'raw_area_um2':a[0]['groups'][name]['area_um2'],
    'mean_watts':[statistics.mean(w['groups'][name]['watts'][j] for w in a) for j in range(4)]}
  rows.append(row)
 summary={'scope':'synthetic prelayout compute tile; outside weights/config/events/q9 memory, RNG, encoding, physical wires/CTS and final floating recovery',
   'N':64,'T':32,'BINS':4,'PVT':'SS1.08V125C','frequency_MHz':100,'area_multiplier':0.81,
   'snapshots':snapshots,'archives':archive_records,'functional':functional,'PPA':rows,'failures_preserved':failures}
 save(PKG/'results/FINAL_SUMMARY.json',summary)
 names={0:'S0 精确三级树',1:'S1 精确位平面',2:'S2 先计数再加权',3:'S3 普通OR4',4:'D0 直接定点参考',5:'D1 确定位串行'}
 lines=['# T32矩阵验证结果（2026-10-28）','',
  '本轮先核对码域/位宽/符号/分档与握手，再在EDA服务器执行VCS、DC、门级回放和PT。实际完成范围由下表与FINAL_SUMMARY.json为准；保留所有后处理失败版本。',
  '', '固定N64/B4/T32、SS1.08V125C、100MHz；每核三seed，各15帧合成输入。面积已经乘0.81，原始面积另存；能量为整个帧测量窗口的总能量/完成帧数，包含本核控制、计数/恢复/排空及握手。',
  '', '| 方案 | M | 55nm等效面积 µm² | 总功率 µW | 能量 pJ/帧 | 周期/帧 | setup/hold ns |',
  '|---|---:|---:|---:|---:|---:|---|']
 for x in rows:
  lines.append('| %s | %d | %.2f | %.2f | %.3f ± %.3f | %.2f | %.4f / %.4f |'%(names[x['mode']],x['M'],x['area_55eq_um2'],x['total_W']*1e6,x['gross_pJ_per_operation'],x['energy_std_pJ'],x['cycles_per_operation'],x['setup_slack_ns'],x['hold_slack_ns']))
 lines+=['','能量±为三个seed的总体标准差，不是置信区间。M8每帧完成8个长度64的点积；不能把其每帧能量直接与M1相除就判优。M1/M8都是计算tile，未包含完整矩阵存储系统。','',
  'v1/v2各36项540帧功能通过（两版本共1080帧）：S0/S1/S2与同事件整数参考一致；S3与独立集合OR参考一致；D0/D1与精确定点参考一致。涵盖0/256端点、±127/±1/0、符号抵消、不同/无效bin、共享/独立/分层事件、中途复位、采样gaps、输出stall和帧间重配置。',
  '', 'S3有结构误差：共享同R、同号同位权的测试中相对精确和低75%；独立半概率例约低52.4%–54.4%。三seed数值见NUMERICAL_SUMMARY.json。OR碰撞偏差不会随延长T自动消失，本实现不能以这种误差换得的能量直接宣称同质量优势。',
  '', 'D0/D1使用q9∈[0,256]的概率分子，输出对应精确期望参考；SC输出为32拍事件整数和，两者参考的比例为1/8。D0是自行实现、尚未优化的直接定点核，不冒充成熟INT8最优基线；内部top名matrix_s4对应D0枚举，不是互斥OR方案S4。',
  '', 'S0当前hold违例与各核功耗表范围/其他告警必须保留。报告的功耗是前布局条件结果；功能通过、活动全覆盖与时序/功耗签核是不同结论。无CTS/SPEF/SDF，无真实LLM/PPL、BF16编码及最终尺度恢复、SRAM/权重保持、RNG/比较器与物理广播线，不以本表宣布整机PPA或模型质量胜出。',
  '', '后处理版本记录：v2保留测试台real变量导致的波形拒绝；v3去除DUT外real；S0的VCS向量端口/转义位网同名由v4逐时刻相等证明后处理；v5批量收集同一组leaf pins，原边界可用时逐名集合全等，核验源/库/约束SHA后复用网表；v6/v8修复cell/lib调试可见性，常量引脚初态完整后才允许PT；v7打包含派生结果导致部署失败，没有提交EDA。v9只对PT未报告活动的顶层sample_ready常量0，要求映射网表显式assign和VCD零翻转共同证明，保留原始PT表；真实cell pins仍全部PT/VCD交叉核验。v9复用已计算的首个PT窗口和通过的门级回放，不重复算能量。',
  '', '调度回执：v4多余索引1..5未执行即撤回；v3旧数字后处理38437898_4在替换时实际已运行1分34秒后取消，不能写成尚未运行。它的完整替代结果由v9提供。完成的综合没有重跑，失败波形/后处理按新冻结版本复验；未取消或修改其他任务。精确Slurm终态保存在本任务私有回执。',
  '', '当前新变体采用统一32位输出/部分内部状态，S0核心累计25位。后续应把已证明的SC内部25位边界落实到新核并做消融，不能把本轮称为各架构最优实现。D0/D1的量化精确性高于单次T32抽样；真实模型质量和同规模成熟数字对照尚未闭合。',
  '', '源码与冻结manifest在本目录；原字节执行包、小报告及逐成员SHA在project_archives/matrix204_t32_20261028，Git只保存小型自有源码/合成fixture/汇总索引，不上传PDK/IP、网表或大波形。']
 for m in (1,8):
  a=next((x for x in rows if x['mode']==0 and x['M']==m),None)
  if a:
   for x in rows:
    if x['M']==m and x['mode'] in (1,2,3):lines.append('\n相对同M=%d的S0，%s：面积%+.2f%%，能量%+.2f%%，周期%+.2f%%。'%(m,names[x['mode']],(x['area_55eq_um2']/a['area_55eq_um2']-1)*100,(x['gross_pJ_per_operation']/a['gross_pJ_per_operation']-1)*100,(x['cycles_per_operation']/a['cycles_per_operation']-1)*100))
 lines+=['','结论：本次多输出共享计数有效改善自身SC实现，但没有证明整体优于普通数字。M1确定位串行能量约34.47pJ/帧、11周期，低于当前精确树165.99pJ/帧、37周期，面积相近。下一步重点为同规模M8数字对照、收紧SC位宽/真实ICG消融、权重驻留与SRAM实际端口、真实后训练输入和告警收敛；不能预设SC必胜。']
 (PKG/'results/REPORT_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
 print('VERIFIED_ARCHIVES',len(archive_records),'COMPLETE_PPA_CORES',len(rows))
 for x in rows:print(x['top'],x['area_55eq_um2'],x['gross_pJ_per_operation'],x['cycles_per_operation'],x['review_flags'])
if __name__=='__main__':main()
