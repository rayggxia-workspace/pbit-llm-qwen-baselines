"""Record user-selected RNG sharing topology without starting experiments."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
H=Path(__file__).resolve().parent;R=H.parents[3];W=R.parents[1];A=W/'project_archives/matrix204_dual_plan_20261029/two_lfsr';A.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepend(p,n):
 b=p.read_bytes()
 if n.splitlines()[0].encode() in b:return
 d=A/('preimage_'+sha(p)+'.bin')
 if not d.exists():d.write_bytes(b)
 assert p.read_bytes()==b;p.write_bytes(n.encode()+b)
def main():
 n='12_双随机分层矩阵架构评估计划.md';p=R/'digital_circuit_simulation_registry'/n;q=W/'digital_circuit_simulation_registry'/n
 if q.exists():shutil.copyfile(q,A/(sha(q)+'_'+q.name))
 shutil.copyfile(p,q);assert sha(p)==sha(q)
 note='''## 2026-10-29 Issue204：用户指定输入/权重各一颗全局LFSR32

用户进一步明确：全部输入共用一颗LFSR32，全部权重共用另一颗LFSR32，分层计数器独立生成层号。主候选据此固定，连接独立只作数学精度对照，不按每连接完整PRNG计成本。P8输入/P7幅值权重且8×4时，仅各需5位格内抖动；两颗32位状态共64位、单5位格计数器合69位（不含概率/权重保持、累计和广播）。T64/128/256分别5+4、4+4、4+3位抖动。只广播所需低位与层号，不把32位全部拉给比较器；K64/M输出仍有64个X-SNG及64M个W-SNG。

先单乘法T32/64/128/256，再64对乘累加与M输出复用；当前只是用户方案记录，未启动实现/EDA/模型。两轴不同非零seed、实际抽头/反馈与短窗联合/时间相关性、帧间连续推进另验；普通LFSR5缺零/31周期不能直接替代32值均匀抖动。全局共享改变点积协方差，不能继承连接独立PPL；先精确归约、OR4单列，原尺度不改。已更新功耗面积目录12方案页并逐字同步根镜像，不新增run、旧台账不改。rayggxia，Issue204/PR209、task/204-bf16-baseline，源基线f5d22ac4470c9a423bbba238994957f1a4491cd0；本补充发布见TWO_LFSR_PUBLICATION.json，PR待审未合并、Projects待维护者同步。

'''
 for p0 in [R/'PROJECT_MEMORY_ZH.md',W/'PROJECT_MEMORY_ZH.md',W/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md',R/'progress/rayggxia/STATUS.md',R/'work/rayggxia/204/HANDOFF.md',H/'HANDOFF.md']:prepend(p0,note)
 results=[]
 for root in [R,W]:
  reg=root/'digital_circuit_simulation_registry';before={p.name:sha(p) for p in (reg/'records').glob('*.json')}
  r=subprocess.run([sys.executable,str(reg/'registry.py'),'check'],capture_output=True,text=True,check=True)
  assert before=={p.name:sha(p) for p in (reg/'records').glob('*.json')};results.append(dict(records_unchanged=len(before),check=json.loads(r.stdout)))
 out=dict(date='2026-10-29',user_selected_main_topology='One global LFSR32 for X, one global LFSR32 for W',source_base='f5d22ac4470c9a423bbba238994957f1a4491cd0',grids=[dict(T=t,Ka=a,Kw=b,X_jitter_bits=8-(a.bit_length()-1),W_jitter_bits=7-(b.bit_length()-1)) for t,a,b in [(32,8,4),(64,8,8),(128,16,8),(256,16,16)]],T32_RNG_state_bits=64,T32_joint_cell_counter_bits=5,plan_path=n,plan_sha256=sha(p),mirror_equal=sha(p)==sha(q),registry=results,new_EDA=0,new_PPL=0,implementation_status='proposal only; no RTL or LFSR sequence acceptance claim')
 (H/'TWO_LFSR_VALIDATION.json').write_bytes((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())
 print(json.dumps(dict(mirror_equal=out['mirror_equal'],records_unchanged=[r['records_unchanged'] for r in results],new_EDA=0)))
if __name__=='__main__':main()
