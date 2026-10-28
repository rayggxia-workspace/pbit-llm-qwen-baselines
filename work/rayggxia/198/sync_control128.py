"""Append dated evidence without replacing other tasks' memory or registry."""
from finish_control128 import *
stage='''## 2026-10-28：128节点控制EDA已完成，按能量与时间联合选型

负责人rayggxia；Issue198 / task/198-attention-compare / 草稿PR199，base main，执行源父提交5f4f5bde及CONTROL128_SOURCE.json精确SHA。工作目录tmp/attention-compare-issue198-20261027复用，未新建重复checkout。

用户明确不能为了面积牺牲功耗和时间。8个top重新DC；本机168回放106227拍，服务器336个RTL/门级回放212454拍通过；56个PT窗口、8top额外时序审计完成。G16融合、binary winner、10位计数、弹性流水主候选：原面积0.014409360mm²×0.81=55nm折算0.011671582mm²；稀疏p=1/32三seed、S128/B0全query平均0.922946nJ、161.667拍/1.61667μs、570.833μW，7.210516pJ/输出。串行2.246279nJ/415.667拍且面积更大，排除；G32能量仅低0.83%、面积高10.79%且setup余量更小，保留备选。提前保持dense有收益但setup仅0.052158ns，暂不主选；公平随机源本体仍未计。

全1压力首帧至首输出3拍、稳定II1、完整query133拍，不能视为独立有效样本。S64/256/512、burn32功能/周期已测，没测相应能量；不由硬件结果决定模型必须burn0。候选局部7位index不等于KV物理地址；不包含概率驱动/随机源/token映射/V读取/累加，也没有给其附加串行调度。

SS1.08V125°C100MHz、IO delay0/slew.1ns/load.02pF/setup uncertainty2ns/hold.1ns；无SDF/SPEF/CTS/毛刺完整建模。全部整体hold负；主候选−0.056977ns来自cfg_ready→configured，内部reg-reg setup/hold为+2.801410/+0.134473ns。仅SS内部通过，不是全接口/FF hold/物理签核。PWR-981虽100% net/cell标注仍保留；禁用弧p/C/c、无loop-breaking/user false/multicycle。不缩放功率/时序。时钟持续空闲445.9μW，未实现/假扣ICG。

正式结果architecture_tlm/attention_compare_20261027/control128_20261028/RESULTS_ZH.md及RESULTS/COMPARISON/TIMING_AUDIT.json。本机原报告2426成员、额外时序96成员SHA核验，完整大包仅授权EDA远端；恢复索引work/rayggxia/198/CONTROL128_ARCHIVE.json，私有原件project_archives/attention_compare_issue198_20261027/control128_20261028。统一台账新增attention-control128-198-eda-20261028；84→85条增量check/render通过，旧记录不变。仅schema check不冒称对全台账原件重哈希，本轮新原件核验单列。

DC38444217/38444227，replay/PT38444238/38444263，timing38444334，collection38444378；无本轮GPU/PPL。首次依赖提交在创建job前拒绝，已有作业完成后重提，原失败回执保留。当前本地实现/测试/归档/台账完成；准确分支上传SHA和回读见CONTROL128_PUBLICATION.json。PR199待审、未合并，Issue保持开放，Projects沿既有限制待同步。下一步修接口hold和标注，再结合真实候选激励及外部接口成本，不启动未经要求的昂贵模型重跑。

---

'''
def main():
    for p in [R/'progress/rayggxia/STATUS.md',W/'HANDOFF.md']:
        b=p.read_bytes();assert not b.startswith(stage.encode());p.write_bytes(stage.encode()+b)
    backup=A/'reading_preimages';rows=[]
    for i,p in enumerate([WS/'PROJECT_MEMORY_ZH.md',WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md']):
        b=p.read_bytes();pre=backup/('memory128_'+str(i)+'.bin');assert not pre.exists();pre.write_bytes(b)
        assert p.read_bytes()==b;p.write_bytes(stage.encode()+b);rows.append(dict(path=str(p),pre_sha256=hashlib.sha256(b).hexdigest(),new_sha256=sha(p)))
    write(W/'CONTROL128_MEMORY_SYNC.json',dict(memories=rows,preimages=str(backup),old_bytes_preserved=True))
    log=R/'architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md'
    if not log.exists():log.write_bytes(subprocess.check_output(['git','show','HEAD:architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md']))
    with log.open('ab') as f:f.write(('\n\n'+stage).encode())
    p=R/'digital_circuit_simulation_registry/ATTENTION_198_INTEGRATION_ZH.md'
    with p.open('ab') as f:f.write(('\n2026-10-28新增'+RID+'：336回放/56PT/8top内部STA审计，whole STA violations；参考CONTROL128_REGISTRY_CHECK.json（85记录）与CONTROL128_ARCHIVE_INVENTORY_APPEND.csv增量合并。保留其他分支catalog/record，不整目录覆盖。\n').encode())
    p=C.parent/'README_ZH.md';b=p.read_bytes();p.write_bytes(('2026-10-28最新128节点控制结果：[面积/能量/时延联合比较](control128_20261028/RESULTS_ZH.md)。G16融合主候选，336回放/56PT完成，保留hold与活动映射告警；不含概率驱动/V通路。\n\n').encode()+b)
    d=read(W/'CONTROL128_SUBMISSION.json');d.update(status='all DC/replay/PT/audit/collection completed; PR pending review',replay_preflight=38444238,replay_rest=38444263,timing_audit=38444334,collection=38444378,functional_server_checks=336,functional_server_cycles=212454,power_windows=56);write(W/'CONTROL128_SUBMISSION.json',d)
    print(json.dumps(dict(memory_preimages_preserved=True,registry_records=85,source_snapshot_unchanged=True)))
if __name__=='__main__':main()
