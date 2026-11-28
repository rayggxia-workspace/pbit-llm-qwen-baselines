# 通用计算模块与FP24交接

2026-11-28，Issue225 / PR266。用户确定跨块部分和与模块间数值结果先采用FP24 E8/M15。

- 正式合同：`architecture_tlm/module_contracts/README_ZH.md`，数值细节`FP24_ZH.md`，机器记录`contract.json`。
- 本地正式文件：`C:/Users/86134/Documents/a_P_BIT/tmp/cim-bank32-tlm-issue225-20261124/architecture_tlm/module_contracts/`。
- 20项描述符合同检查通过；不是新RTL/PPA/PPL结果。
- 新五核FFN/单层Decoder已有FP24；旧prefill、旧多层model_rtl_services和主TLM仍需适配。本轮仅明确合同，未擅改原模块。
- 优先补prefill的init/continue/final、四beat捕获接口、格式转换、underflow与BF16溢出，然后绑定实际周期/II/能量/面积。
- 发布状态以`work/rayggxia/225/common_compute_fp24_20261128/PUBLICATION.json`为准；本地阅读入口不表示已合并。
