"""Synchronize the new result while retaining each existing memory preimage."""
from pathlib import Path
import hashlib,json,shutil
H=Path(__file__).resolve().parent;R=H.parents[3];W=R.parents[1];A=W/'project_archives/matrix204_parallel64_20261029'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def prepend(p,n,receipts):
 raw=p.read_bytes()
 if n.splitlines()[0].encode() in raw:return
 h=sha(p);dst=A/('preimage_'+h+'.bin')
 if dst.exists():assert dst.read_bytes()==raw
 else:dst.write_bytes(raw)
 assert p.read_bytes()==raw,'Concurrent edit'
 p.write_bytes(n.encode()+raw);receipts.append(dict(path=str(p),previous_sha256=h,archive=str(dst)))
def main():
 s=json.loads((R/'architecture_tlm/int8_parallel64_20261028/results/FINAL_SUMMARY.json').read_text());reg=json.loads((H/'REGISTRY_CHECK.json').read_text());pre=[]
 note='''## 2026-10-29 Issue204：按用户要求完成同64路并行INT8对照

rayggxia，task/204-bf16-baseline / PR209（base main），复用tmp/matrix-t32-issue204-20261028；执行base158e489816bde1547d07cd3f9e377b809055f63f+明确未提交冻结快照。用户澄清重点为整体面积/功耗、要求同SC的64路物理输入并行度，主比较已改为64个动态signed8×8并行乘法+六级平衡树+32/22位结果寄存，不以四路复用替代。旧四路/BF16/SC原件完整保留。正式入口architecture_tlm/int8_parallel64_20261028/results/REPORT_ZH.md与FINAL_SUMMARY.json。

SS1.08V125℃100MHz，面积raw×.81一次。64路32位结果：raw34842.96µm²、等效0.028222798mm²；满速2.126333mW/21.2633pJ每完整N64点积，原生1拍结果、II1=10ns；每35拍接受一帧且100MHz时钟自由运行时0.1148mW/40.1800pJ。22位结果raw34756.92µm²、等效0.028153105mm²，满速2.118333mW/21.1833pJ，同35拍0.108933mW/38.1267pJ。固定N64无bias的22位精确，非任意K累加器，外部均32位；综合高符号位复制/合并，缩位面积差约0.247%。

同原SC54操作数匹配：从原ZIP恢复X/W并逐项SHA核验，每帧W行f%8、absW上限127、X原signed8。SC54原0.0055240704mm²、0.198466667mW、69.4633pJ/350ns。相同64并行度SC面积小5.109倍、各自满速功率低10.714倍，但数字原生吞吐高35倍、满速能量低3.267倍；同350ns完成工作率下SC能量/功率为数字1.729倍。可以支持同64路SC面积优势，不能宣称目前SC相同工作率能耗优势。SC OR4/T32/去LSB近似、数字精确，合成输入匹配不等于模型质量匹配；无新模型/PPL。

最终两top/三seed各164事务，984 RTL及984映射门级输出逐项oracle/四态valid通过，24PT窗口mapped端口/leaf活动100%。v1另24窗口已算出但hold−.061165ns，原件保留；v2核验源/配置/库绑定/原网表后，DC原生hold-only实际插buffer，每核面积仅+raw1.44µm²（等效1.1664）。不重编译算术/retime、不放宽约束；最终setup/hold：32位1.429668/.032151ns，22位1.881098/.027525ns，parser flags空。数据delay1/.02ns、slew.05、load20fF、uncertainty.5/.05，reset4.5..5.5ns释放，无false/multicycle。无CTS/SDF/SPEF/完整毛刺，不是物理签核。

两执行ZIP/8报告/24传输文件/全部成员SHA已核验；准确作业与命令RUN_LEDGER，v2manifest f39df885a073d53ac9c5a7584d78e97906122722b29664ba0155f8e6cd434c8d，原件project_archives/matrix204_parallel64_20261029，私有配置/SDC/库模型指纹单列EXECUTION_FINGERPRINTS。Slurm38447564/38447584/38447776/38447785及两只读DC命令帮助作业均COMPLETED/0:0，不重交。权重/概率存储、SRAM/RNG/比较器/格式/真实广播/ICG仍在核边界外，paced不称最佳数字门控能量。

中央run matrix-int8-par64-204-20261029，任务分支67、完整本地根镜像89，分别保留原66/88个record字节并check/render，不以小子集覆盖全union。新run原件/成员全可访问；历史不可达项见LOCAL_REGISTRY_CHECK.json。源码/结果本地完成，实际推送SHA/回读查同目录PUBLICATION.json；PR待审未合并，Issue保持open，Projects连接器不支持写待维护者同步。

'''
 for p in [R/'PROJECT_MEMORY_ZH.md',W/'PROJECT_MEMORY_ZH.md',W/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md',R/'progress/rayggxia/STATUS.md',R/'work/rayggxia/204/HANDOFF.md']:prepend(p,note,pre)
 p=H/'HANDOFF.md';raw=p.read_bytes();(A/('preimage_'+sha(p)+'.bin')).write_bytes(raw)
 p.write_bytes((note+'恢复先读最新Issue204/PR209及PUBLICATION，核对准确head。结果已齐、无遗留作业；不重跑init.py、不重交旧快照。prepare.py会重建RTL/bench/fixtures，只在新目录运行。下一步审核、质量/真实存储供数和多输出共享边界；不自动追加昂贵EDA或模型实验。\n').encode())
 rn='## 2026-10-29 Issue204：同64路并行INT8对照\n\n新增matrix-int8-par64-204-20261029，最终2top/24PT窗口，另24初版hold违例保留。原生1拍/II1；32位结果等效0.028222798mm²、满速21.2633pJ、同350ns间隔40.18pJ。SC同64并行面积小5.109倍，能量关系见正式报告，不把功率比当节能比。任务67、完整本机union89条，各自保留全部旧record字节；check/render通过，无物理签核/模型PPL。\n\n'
 for p in [R/'digital_circuit_simulation_registry/README_ZH.md',W/'digital_circuit_simulation_registry/README_ZH.md']:prepend(p,rn,pre)
 p=R/'architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md';n='\n\n## 2026-10-29 同64路并行INT8与SC对照\n\nIssue204/PR209；[正式报告](int8_parallel64_20261028/results/REPORT_ZH.md)。按用户指定物理输入并行度，64乘法并行+平衡树、固定N64精确32/22位结果，满速和350ns发帧分别测量；SC面积优势成立、相同完成工作率能量优势未成立，输入SHA匹配但SC近似/数字精确。v1 hold负值与v2实际hold buffer修复原件保留；最终24窗口，中央matrix-int8-par64-204-20261029。无模型PPL/存储供数/后布局签核。\n'
 if n.splitlines()[2].encode() not in p.read_bytes():p.write_bytes(p.read_bytes()+n.encode())
 for file,n in [('.gitignore','architecture_tlm/int8_parallel64_20261028/fixtures/\nwork/rayggxia/204/int8_parallel64/private/\n'),('.gitattributes','architecture_tlm/int8_parallel64_20261028/** -text\n')]:
  p=R/file
  if n.encode() not in p.read_bytes():p.write_bytes(p.read_bytes()+n.encode())
 p=A/'private_control';p.mkdir(exist_ok=True)
 for n in ['par64_server.py','par64_fingerprints.py']:shutil.copyfile(R/'work/rayggxia/204/private'/n,p/n)
 save(H/'VALIDATION.json',dict(date='2026-10-29',owner='rayggxia',issue=204,source_base=s['source_base'],source_manifest_sha256=s['execution_source_manifest_sha256'],memory_preimages=pre,model_corpus='N/A synthetic circuit-only; no inference/PPL',source_packages=2,report_archives=8,transfers_verified=24,final_PT_windows=24,initial_hold_violation_PT_windows=24,final_RTL_outputs=984,final_gate_outputs=984,configuration_and_library_fingerprints=dict(path=str(A/'EXECUTION_FINGERPRINTS.json'),sha256=sha(A/'EXECUTION_FINGERPRINTS.json')),slurm_final=dict(path=str(A/'SLURM_FINAL.txt'),sha256=sha(A/'SLURM_FINAL.txt')),registry=reg,publication='Actual receipt in PUBLICATION.json'))
 print('DELIVERY_READY',len(pre))
if __name__=='__main__':main()
