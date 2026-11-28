# 会话TLM：Prefill到连续Decode

2026-11-28，Issue225/PR266。正式入口`architecture_tlm/unified_v6/SESSION_ZH.md`，结果在同目录`results/session_control_20261128/REPORT_ZH.md`。

本地正式checkout：`C:/Users/86134/Documents/a_P_BIT/tmp/cim-bank32-tlm-issue225-20261124/`。运行`python -B architecture_tlm/unified_v6/run_session.py --prompt 4 --generated 2 --out <新目录>`；12项回归`test_session.py`。

Qwen3-4B36层全宽、4输入/2输出的控制/事务回放完成。KV从0到5位置，首输出后一次decode；五核/12FP24槽/GU16/Wd32/PV64。完整时间约354.648ms、首输出256.298ms、后续间隔98.350ms，仅宏级访存/合成Attention地址条件，不能替换旧Ramulator结果或当模型PPL。

当前可运行完整流程，默认并未改变。原生LPDDR、真实Attention轨迹、128/2K输入以及完整能量/面积尚待接；总能量/面积未填造，明确为null。发布状态见任务work的PUBLICATION.json，PR保持待审。
