"""Sync only this index; preserve the larger local registry and memory union."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
H=Path(__file__).resolve().parent;R=H.parents[3];W=R.parents[1];A=W/'project_archives/matrix204_parallel64_20261029/power_index';A.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepend(p,n):
 b=p.read_bytes()
 if n.splitlines()[0].encode() in b:return
 dst=A/('preimage_'+sha(p)+'.bin')
 if dst.exists():assert dst.read_bytes()==b
 else:dst.write_bytes(b)
 assert p.read_bytes()==b,'Concurrent edit'
 p.write_bytes(n.encode()+b)
def main():
 reg=R/'digital_circuit_simulation_registry';mirror=W/'digital_circuit_simulation_registry';names=['11_矩阵与算术模块功耗面积时钟索引.md','summaries/20261029_matrix204/MODULE_INDEX.json','summaries/20261029_matrix204/MODULE_MODES.csv']
 before={p.name:sha(p) for p in (mirror/'records').glob('*.json')}
 for n in names:
  src=reg/n;dst=mirror/n;dst.parent.mkdir(parents=True,exist_ok=True)
  if dst.exists() and sha(src)!=sha(dst):shutil.copyfile(dst,A/(sha(dst)+'_'+dst.name))
  shutil.copyfile(src,dst);assert sha(src)==sha(dst)
 header='## 2026-10-29新增：矩阵与算术模块查询入口\n\n[11_矩阵与算术模块功耗面积时钟索引](11_矩阵与算术模块功耗面积时钟索引.md)汇总Issue204的66配置/209运行模式，包含popcount、OR4、累计器、移位相加、SC/BF16/INT8，逐项功率、raw/55nm等效面积、100MHz时钟、周期、STA、源码和原件绝对地址，并提供CSV/JSON。下方10月27日历史表的面积列保留原始口径；按本项目规则需要单次×0.81后再与新等效面积比较，原始功率/时间不缩放。\n\n'
 for root in [reg,mirror]:
  prepend(root/'04_最新功耗面积汇总.md',header)
  prepend(root/'README_ZH.md','## 2026-10-29矩阵/算术模块长期索引\n\n新增[11专题](11_矩阵与算术模块功耗面积时钟索引.md)：66配置/209模式的功耗、双口径面积、时钟、操作周期、时序与精确源码/原件地址；数据可筛选CSV/JSON。只整理既有结果，不新增run。后续相关模块继续登记中央run并同步此类阅读索引，避免只留在聊天中。\n\n')
 note='''## 2026-10-29 Issue204：功耗面积文件夹补齐模块长期索引

用户要求把此前模块的功耗、面积、时钟及具体文件地址统一整理，避免遗忘。已在digital_circuit_simulation_registry新增11_矩阵与算术模块功耗面积时钟索引.md及summaries/20261029_matrix204/MODULE_INDEX.json、MODULE_MODES.csv，覆盖Issue204六批66配置/209运行模式：四档首轮8、单尺度16、参数模块33、BF16五核、四lane INT8两核、64路INT8两核。固定读取提交4175c5565fcd714b0648d97a15c1697b5fbcee05；6源汇总/源码逐字及66原始报告归档SHA核验，保留每项活动/idle、raw与×.81等效面积、100MHz/10ns、操作定义/平均周期/原生延迟和II（未知留空）、STA负值/告警、源码Git地址与本机绝对原件路径。旧04页保留原始表值并加新入口和面积口径说明，README补导航。

同3份新文件已逐字同步根阅读镜像；各自README/04原有内容保留，旧record字节不改、不用67条任务子集覆盖89条完整根union。无新EDA/模型/PPL、不新增run。复现build_power_index.py，核验POWER_INDEX_VALIDATION.json；未来新增模块需同时更新中央run与阅读索引。rayggxia，继续Issue204/PR209、task/204-bf16-baseline，复用tmp/matrix-t32-issue204-20261028；本补充本地已完成，实际发布见POWER_INDEX_PUBLICATION.json；PR待审未合并，Projects待维护者同步。

'''
 for p in [R/'PROJECT_MEMORY_ZH.md',W/'PROJECT_MEMORY_ZH.md',W/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md',R/'progress/rayggxia/STATUS.md',R/'work/rayggxia/204/HANDOFF.md',H/'HANDOFF.md']:prepend(p,note)
 checks=[]
 for root in [reg,mirror]:
  check=subprocess.run([sys.executable,str(root/'registry.py'),'check'],capture_output=True,text=True,check=True)
  subprocess.run([sys.executable,str(root/'registry.py'),'render'],capture_output=True,check=True)
  checks.append(dict(path=str(root),result=json.loads(check.stdout)))
 assert before=={p.name:sha(p) for p in (mirror/'records').glob('*.json')}
 out=dict(mirror_files=[dict(path=n,sha256=sha(reg/n),same_bytes=sha(reg/n)==sha(mirror/n)) for n in names],foreign_full_mirror_records_unchanged=len(before),registry_checks=checks,new_simulations=0)
 (H/'POWER_INDEX_MIRROR.json').write_bytes((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())
 print(json.dumps(dict(mirror_files=3,full_union_records=len(before),checks=[x['result']['status'] for x in checks])))
if __name__=='__main__':main()
