# 24/32位状态精度：数值/PPL交接

2026-11-27，Issue225/PR266，负责人rayggxia，同task/225-cim-bank32-20261124。推理源0d1e85176fd52205669148296c585a06c47bc369，51文件冻结；9个新文件远端内容和原字节blob匹配，索引文件首次读回失败后重读匹配。上游RTL只读，19原源/结果SHA均匹配，未覆盖其实现或默认配置。

CPU62257已COMPLETED/0:0、26项PASS；GPU62258 run_v2正在运行，尚无完整新PPL。程序依次执行16组GPU整数oracle（真实40/152块和不同输出恢复指数）、完整BF16、64位无操作logits及旧pilot字节一致，再跑64/32/24位同8窗9215目标、seed101。32/24若不超过64位1%自动接完整WT2，1%仅资源触发。64位完整参考只读复用原健康x一位实验。

固定T64/W8、GU16/Wd32、x/g/u64共享基准+S/S2，准确Attention，不训练。按形状/采样上限/W8上限/输入尺度选择公共单位，不取最终输出；先合并各输出恢复指数，逐tile RNE后W位状态更新，溢出报错，无饱和/回绕。模拟GPU内宽容器不代表存储W=64；每次累加都显式检查窄状态，原最终恢复/LUT规则保持。

初稿run_v1漏合并输出恢复指数，不作为验收结果。仅该新GPU62256已撤回；CPU62255及所有旧源/日志/目录保留，旧x实验62244/62245未取消或重交。修复后独立run_v2，严禁回写v1/上游RTL。

RTL field_raw从恢复g（RNE24）取sigmoid地址，而现有PPL从P8重建g取地址；本轮保持后者，只评估位宽，不冒称完整RTL codec质量闭合。公共尺度服务仍是宏接口，PPL不证明其面积/时延或RAM仲裁。分析ASSESSMENT_ZH.md。

原12槽载荷64/32/24位=12/6/4.5KiB；不当面积比例。默认64位与TLM/RTL保持，不新增硬件台账run、不合并PR，Projects待维护者同步。待新PPL及真实局部误差后再决定32或24。

## 2026-11-27｜窄位宽PPL快核已验证并切换并行

Issue225/PR266，负责人rayggxia。原T64/W8、GU16/Wd32、x/g/u组64基准+S/S2、准确Attention不变。原逐tile Python参考约93秒/窗；融合Triton核通过16独立oracle、4长K逐位及计数对照、24/32各一个真实模型原窗含NLL逐项一致，计时33.005/24.887秒。独立原件SHA/覆盖复核通过，FAST_VALIDATION.json；无新PPA或默认修改。原数值源0d1e8517，分宽度接续128432ba。

Gate62262 COMPLETED/0:0，前两次失败62260/62261原件保留。用户明确授权取消慢62258/旧接续62259后，快测62263（32位）/62264（24位）已RUNNING。32位已19窗原件复用、余273；24位292待算。预计两卡约2～3h，随连续吞吐修正。已通过的8窗9215目标PPL为64位11.4068403048、32位11.4645418153、24位11.4897787234；后两者相对+0.506%/+0.727%。完整WT2尚待核验，不当成已完成。

正式入口experiments/t64_narrow_state_20261127/PERFORMANCE_ZH.md，私有work/rayggxia/225/narrow_state_20261127/fast_full_v1/SUBMISSION.json、SWITCH_RECEIPT.json及STATUS_OBSERVED.json。根local_tools/dynamic_scale_225_20261125/check_narrow_fast_full_20261127.py只读。无训练，默认64位及RTL/TLM不改，PR不合并；Projects待同步。
