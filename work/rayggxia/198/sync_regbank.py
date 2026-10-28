"""Append evidence to own progress and shared reading copies, preserve preimages."""
from finish_regbank import *
stage='''## 2026-10-29：128字概率阈值寄存器及并行比较器EDA完成

负责人rayggxia，继续Issue198 / task/198-attention-compare / draft PR199，base main，复用tmp/attention-compare-issue198-20261027。执行父提交1f4dff93加v2/v3/v4/v5冻结SHA；未新建重复checkout，未运行GPU/PPL。7top/三seed/42条RTL与门级oracle回放，8904执行拍/8610检查拍；84最终PT窗口，全部net/leaf cell活动100%。Slurm38447688及修复38447724完成，早期失败38447560与旧slew38447569原件保留。

SS1.08V125°C100MHz、原SHARK面积×0.81。真实32个X8 ICG门控，128×12/16位阈值库单头等效0.00928746/0.012273444mm²，保持33.17/37.69μW；CE常开时钟915/1220μW。8拍装载+160拍采样完整事务84.722/102.183pJ，装载30.65/40.53pJ已计。加128路比较器：0.015184778/0.020186302mm²、605.808/796.656pJ每事务。11位score库额外0.008540964mm²/头。32头阈值库6/8KiB、0.297199/0.392750mm²，保持1.062/1.206mW；加比较器、11位score及旧控制的模块面积和1.132714/1.292763mm²。36层复用时面积不乘36，能量按1152次query-head外推。完整RNG/LUT/max/转换/地址映射/V/累加均未计，不能称完整Ising PPA。

功能通过但不是物理签核：16位门控wr_data输入hold=-0.010220ns；12位门控hold仅+0.004787ns。比较器每窗口256个低slew库表外推告警，其他五top check_power通过。无缺表/无用户false或multicycle，禁用弧是常量条件传播。无CTS/SPEF/SDF/完整延迟毛刺；合成阈值活动并非真实Qwen，不能和旧p=1/32、S128/B0的控制能量直接拼成实测总能量。8拍装载要求上游16阈值/拍，ROM端口成本没有计入。

正式代码及RESULTS/SUMMARY/REPORT_ZH.md在architecture_tlm/attention_compare_20261027/regbank_20261029；功耗面积目录10_阈值寄存器与全Q头资源估算.md提供参考。原报告1953成员、历史2031成员SHA核验；本地project_archives/attention_compare_issue198_20261027/regbank_20261029，完整RAW包21.7MB留授权EDA服务器，位置/校验在私有COLLECTION。统一run attention-regbank-198-eda-20261029，根台账87→88条check/render且旧87记录字节不改；元数据校验与本轮原件核验分开，未重验全部历史原件。

本地成果已完成，准确远端提交与回读以work/rayggxia/198/REGBANK_PUBLICATION.json为准。PR199仍待审未合并、Issue开放，Projects沿既有限制待维护者同步。下一步匹配真实接口关闭hold/低slew告警，再评估16阈值/拍LUT和合格RNG吞吐；不以本轮估计宣称整机竞争力。

---

'''
def main():
 for p in [R/'progress/rayggxia/STATUS.md',W/'HANDOFF.md']:
  b=p.read_bytes();assert not b.startswith(stage.encode());p.write_bytes(stage.encode()+b)
 rows=[];backup=A/'reading_preimages'
 for i,p in enumerate([WS/'PROJECT_MEMORY_ZH.md',WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md']):
  b=p.read_bytes();pre=backup/('regbank_memory_'+str(i)+'.bin');assert not pre.exists();pre.write_bytes(b)
  assert p.read_bytes()==b;p.write_bytes(stage.encode()+b);rows.append(dict(path=str(p),pre_sha256=hashlib.sha256(b).hexdigest(),new_sha256=sha(p)))
 write(W/'REGBANK_MEMORY_SYNC.json',dict(memories=rows,preimages=str(backup),old_bytes_preserved=True))
 log=R/'architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md'
 if not log.exists():log.write_bytes(subprocess.check_output(['git','show','HEAD:architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md']))
 with log.open('ab') as f:f.write(('\n\n'+stage).encode())
 p=R/'digital_circuit_simulation_registry/ATTENTION_198_INTEGRATION_ZH.md'
 with p.open('ab') as f:f.write(('\n2026-10-29新增'+RID+'：7top/42功能回放/84PT窗口，16位hold和比较器低slew告警保留；参考REGBANK_REGISTRY_CHECK/SYNC及ARCHIVE_INVENTORY_APPEND增量合并。根88记录check/render，旧87原字节保留，不用本分支子集覆盖中央union。\n').encode())
 p=C.parent/'README_ZH.md';p.write_bytes(('2026-10-29新增：[128字阈值寄存器与全部Q头预算](regbank_20261029/REPORT_ZH.md)。真实门控与128路比较器7top/84PT，含装载能量；16位hold/比较器库表外推未签核。\n\n').encode()+p.read_bytes())
 note='''# 阈值寄存器与全Q头资源参考（2026-10-29）

Issue198 / draft PR199，中央run `attention-regbank-198-eda-20261029`。原SHARK面积×0.81为用户约定55nm折算；SS1.08V125°C，100MHz；功率/时序不缩放。本轮实际DC/门级/PT，非芯片实测。

|项目|12位阈值|16位阈值|
|---|---:|---:|
|单头128字门控库面积 mm²|0.009287|0.012273|
|单头保持功率 μW|33.17|37.69|
|单头8拍装载能量 pJ|30.65|40.53|
|单头8+160拍库事务能量 pJ|84.72|102.18|
|库+128比较器事务 nJ|0.6058|0.7967|
|32头阈值库面积 mm²|0.2972|0.3928|
|32头阈值+比较器+11位score+旧控制面积 mm²|1.1327|1.2928|

36层复用时面积不乘36。8拍装载假设每拍16阈值，ROM端口本体未计；若单端口需128拍。32头复制不是唯一调度，报告列H=1/4/8/32的面积与批次权衡。

16位门控输入hold−0.010220ns，比较器每窗口256个低slew库表外推；12位hold余量仅4.8ps，无CTS/SPEF/SDF。合成三seed活动，不是Qwen活动；旧控制能量不同激励不得直接合并。RNG、LUT/max/转换、KV地址映射、V读取/累加未计。

正式[完整报告](../tmp/attention-compare-issue198-20261027/architecture_tlm/attention_compare_20261027/regbank_20261029/REPORT_ZH.md)（本机阅读镜像相对路径）；Git内请查 `architecture_tlm/attention_compare_20261027/regbank_20261029/REPORT_ZH.md`。原件和SHA见 `work/rayggxia/198/REGBANK_ARCHIVE.json`，run [记录](records/attention-regbank-198-eda-20261029.json)。不另建功耗台账。
'''
 name='10_阈值寄存器与全Q头资源估算.md'
 p=R/'digital_circuit_simulation_registry'/name;p.write_bytes(note.encode())
 q=WS/'digital_circuit_simulation_registry'/name;assert not q.exists();shutil.copyfile(p,q)
 print(json.dumps(dict(memory_synced=True,registry=read(W/'REGBANK_REGISTRY_SYNC.json'),reference_mirror_equal=sha(p)==sha(q))))
if __name__=='__main__':main()
