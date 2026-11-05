"""Write delivery notes from the verified completed batch, without rerunning EDA."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def main():
 r=json.loads((ROOT/'architecture_tlm/matrix_single_scale_20261028/results/FINAL_SUMMARY.json').read_text(encoding='utf-8'))
 assert len(r['PPA'])==16 and len(r['report_archives'])==22 and len(r['source_packages'])==3 and not r['failures_preserved']
 assert sum(x['frames'] for x in r['functional'])==1056
 assert not set(r['active_jobs_at_collection']) & {'38439478','38439503','38439546','38439568','38439629','38439646'}
 raw=json.loads((HERE/'private/SLURM_FINAL.json').read_text(encoding='utf-8'));assert raw['returncode']==0
 lines=raw['stdout'].splitlines();tasks=[]
 for line in lines[1:]:
  a=line.split('|')
  if not a or '.' in a[0]:continue
  assert a[1:3]==['COMPLETED','0:0'],a
  tasks.append(dict(zip(['job','state','exit_code','elapsed'],a)))
 save(HERE/'EXECUTION_INDEX.json',{'source_packages':r['source_packages'],'report_archives':r['report_archives'],'functional':r['functional'],
  'ppa_cores':16,'ppa_windows':96,'functional_frames':1056,'slurm_tasks':tasks,'server_tasks_remaining':0,
  'source_manifests':[x['source_manifest_sha256'] for x in r['source_packages']],
  'scope':'synthetic compute/control only; no real model accuracy or physical signoff; versions are implementation variants, not independent quality replications'})
 def pick(v,mode,m):return next(x for x in r['PPA'] if x['snapshot'].split('_')[2]==v and x['mode']==mode and x['M']==m)
 a=pick('v1',0,1);b=pick('v3',3,1);g=pick('v3',6,1);d=pick('v1',5,1)
 m8=pick('v3',3,8);d8=pick('v1',5,8)
 text='''# Issue204 单尺度INT8完成回执（2026-10-28）

负责人rayggxia，task/204-matrix-t32，PR205 open/ready/unmerged，base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166，科学输入基线cc04dee9890ea6dcfbeee872b0cab914d3b1c2c6。本地目录tmp/matrix-t32-issue204-20261028。沿用原Issue/PR，不改旧四档冻结输入、其他任务或整机/模型默认。

用户决定：64路共用一个尺度、真正signed INT8[-128,127]、N64/T32；每幅值位平面和符号先OR4，64→16个事件，再做精确并行计数。实现3版：V1直接实现；V2把每组正负各6位改为一个signed7时间计数；V3使用专用无符号popcount并隔离末端恢复输入，保留signed7组计数。mode3每拍popcount16再时间累计；mode6每组独立累计后求和，二者同事件OR oracle全等。SC内部20位，数字22位，输出符号扩展32位。

全部完成：V1 672帧、V2 96帧、V3 288帧，共1056帧功能PASS；16个综合变体、96个active/idle PT窗口，SS1.08V125C100MHz。3原始执行包和22报告归档远端/本地SHA/大小及逐成员校验；Slurm全部COMPLETED/0:0，本任务无遗留作业。执行索引EXECUTION_INDEX.json，结果architecture_tlm/matrix_single_scale_20261028/results/FINAL_SUMMARY.json和REPORT_ZH.md；源包/报告在project_archives/matrix204_single_scale_20261028。不得重复昂贵测量或改写冻结输入。

M1：精确树%.3fpJ、OR4-popcount16优化版%.3fpJ（能量%+.2f%%、面积%+.2f%%），16路signed7独立时间累计优化版%.3fpJ；数字位串行%.3fpJ。M8优化OR4 %.3fpJ/帧、数字位串行%.3fpJ/帧，每帧8点积。还不能证明SC能效胜数字。共同尺度省去bin选择/移位，但新旧码域、刺激及位宽也改变，不能作纯尺度消融归因。

主PPA为16帧驻留权重、uniform signed INT8输入、公共R8，三seed均值；SC原始期望=数字点积/4。OR损失另报，时间计数硬件改动不改变OR结果；真实模型单尺度质量未验。面积raw×0.81保留双列，不缩放功耗/时间。外部权重存储/保持读口、RNG/比较器、输入量化/尺度选择、最终浮点恢复、物理广播线及CTS/SDF/SPEF在外，CE未冒称ICG。全部时序与功耗警告保留。

中央新run matrix-single-scale-204-20261028，增量union check/render并保留其他record；结果见REGISTRY_CHECK.json。源码/结果本地已完成，发布回执以PUBLICATION.json和最新PR205为准；发布前不写成已推送。Projects既有权限限制仍待维护者同步。下一步审阅计数实现、hold/功耗表告警；真实ICG、SRAM驻留端口及真实后训练模型同质量验证独立开展，不自动启动昂贵模型实验。
'''%(a['gross_pJ_per_operation'],b['gross_pJ_per_operation'],(b['gross_pJ_per_operation']/a['gross_pJ_per_operation']-1)*100,
 (b['area_55eq_um2']/a['area_55eq_um2']-1)*100,g['gross_pJ_per_operation'],d['gross_pJ_per_operation'],m8['gross_pJ_per_operation'],d8['gross_pJ_per_operation'])
 (HERE/'HANDOFF.md').write_text(text,encoding='utf-8',newline='\n')
 path=ROOT/'progress/rayggxia/STATUS.md';old=path.read_text(encoding='utf-8')
 if old.startswith('# Issue204 单尺度INT8'):old=old.split('\n---\n\n',1)[1]
 path.write_text(text+'\n---\n\n'+old,encoding='utf-8',newline='\n')
 print('DELIVERY_NOTES_WRITTEN',len(tasks),'Slurm tasks')
if __name__=='__main__':main()
