## 2026-10-27 Issue95：8位比较器与sigmoid LUT功耗表征代码

负责人rayggxia；task/95-pbit8-characterization，基线main d83eeb1f，目录tmp/rng-pbit8-issue95-20261027。用户问随机源能耗与8位比较器/LUT是否测过，缺少则补代码。38322118已有SS1.08V125C/100MHz布局前暂定PT：stream三seed均值LFSR162.4667uW/1.624667pJ帧、GF64 1355.3333uW/13.553333、Bivium1204uW/12.04、FFN共享字639.6uW/6.396；均含端点/比较/控制，不能叫裸PRNG或单比较器。旧独立64路比较器37962470是P12（W8是权重），已对执行源SHA；旧Chimera输出/LUT为16位。物理共享读出仍DC工作点预算，无完整动态功耗。

新增architecture_tlm/random_service/pbit8_char：8位LT、q9/256端点比较、signed8/8→256x9 sigmoid组合表、寄存表、LUT+比较+输出寄存五核；无PRNG/转换/ICG，不改现有模型。表与TLM SigmoidTable全部256项一致；用于tanh概率时上游须输入2h。131072比较输入、65536 LUT×r概率枚举，75案例/307200计量拍通过；三seed、idle/fixed50/random/sweep/cadence64。Tcl仅四项stub解析，未执行许可EDA/STA/PT，新增功率/面积仍null。

便携包远端上传/pbit8_char_20261027_v1.zip，22870B，SHA eccf79970d17b94a7f1f0b56c9df3e0e8da0ef4e2f1ea63e2bcadd3299383448；README含工艺库步骤/功耗窗口/调用计数/疑点。原始波形归档project_archives/pbit8_char_issue95_20261027/rtl_v2.zip，2764042B，SHA790662130d25fd30102733499ea62bc26f88d3f87b03495dc80eac21d3b4efa7。rtl_v1沙箱DLL错误未进入Icarus，同源码v2沙箱外通过。中央新增rng-pbit8-95-20261027，联合74记录check/render；main无完整registry工具，仅交自身record不覆盖其他分支台账。代码/结果本地完成，发布状态以work/rayggxia/95/pbit8/PUBLICATION.json为准，PR待审不算已合并。无远程任务、无新模型/PPA；待用户实测后回填。同步记忆时保留根目录比canonical多出的两项Issue186更新，不丢并发内容。

---
