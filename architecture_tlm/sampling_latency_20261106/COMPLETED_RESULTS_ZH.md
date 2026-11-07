# 当前1216KiB完整TLM已完成
2026-11-07，38617087两项status=completed，RESULT/SEAL及冻结源码SHA经collect核验，原件逐字节归档。本表是原Attention，不包含新的PV128/归约32/QK共享候选。
|采样|含lm_head ms|lm_head阶段ms|扣lm_head阶段ms|
|---|---:|---:|---:|
|前64后64|51.43301|7.07502|44.35799|
|前8后32|51.40648|7.07546|44.33102|
扣头保留final norm与已重叠预取，非无头硬件重跑。此前两层外推约51/44ms及旧head代理现在被本完整结果替代。
以当前完整T64重建快估profile后，T8/T32快估51.38117ms、原生51.40648ms，绝对差−0.02531ms／约−0.0492%；这是单seed单配置校验，不是通用误差保证。
正式COMPLETED_CURRENT_PROFILE.json／COMPLETED_CURRENT_CHECK.json／COMPLETED_RESULTS.json绑定来源SHA。旧REFERENCE_PROFILE和两层外推历史原件不改。
