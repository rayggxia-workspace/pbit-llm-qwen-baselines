# Issue193第一轮校准包交接

负责人jieruiz；分支task/193-ffn-calibration-stage1；base main d83eeb1fc6b89a3dff51b5b62bf79acf665c7166。独立目录tmp/ffn-calibration-issue193-20261025。源码冻结提交55c607dc4f21fe6cbf1355db4b949b4396cd977f已推送；本次结果提交和PR状态以PUBLICATION.json为准。Issue193保持开放，不自动合并。

## 已完成

- 正式目录architecture_tlm/ffn_calibration_stage1，4RTL模块、9固定top、独立整数oracle/TB、VCS/Icarus入口、DC/可选PT-STA及Slurm脚本。
- 最终9case功能通过、9 fixed top含SYNTHESIS展开通过、29流程单测通过。M1计数核3seed，M8扩展1seed；每个counter运行9完整帧并包含极值/回压/复位。不是PPL误差试验。
- counter末采样后6拍out_valid；restore 4/7档握手8/10拍；acc1拍；完整链frame接受至最终握手80/146拍。同步reset正常计时，无false/multicycle豁免。
- 240s Icarus宽通道超时已封存，900s上限正式运行9case通过（总墙钟约530秒）；软件仿真速度不代表电路时序失败。
- 没有运行许可VCS/DC/PT、没有Slurm作业、没有55nm PPA；100MHz仅目标。coeff/rshift的真实模型编译、质量闭环、SRAM/PRNG/比较器/非线性/BF16仍在边界外。

## 成果与哈希

ZIP：C:\Users\86134\Documents\a_P_BIT\ffn_calibration_stage1_20261025.zip，110224 bytes，SHA256 `51d2f5a5052ba8f45299d2447a07dcf161b8e4ddf4998b910215549f0ec7ab81`。
证据小归档：C:\Users\86134\Documents\a_P_BIT\project_archives\ffn_calibration_stage1_issue193_20261025\validation_evidence.tar.gz，SHA256 `201714aa8b41011a28a218972be190e8155bc536d1a5cf27b30dfedea15985b2`。
源码、配置和各测试哈希见SOURCE_MANIFEST.json及results/local_validation/final/summary.json。独立计数矩阵有部分已停止的重复验证，原件独立标注，未算作完整矩阵。

## 台账

新增ffn-stage1-193-rtl-20261025；root联合阅读索引67→68，原67条逐SHA不变，check/render通过。main尚无完整registry实现；本PR只增此record，不能带入其他未合并的67条。正式56条台账在pbit-tlm-attention-details-20261016 d6d3399，后续集成需将新record加入该目录catalog/render。REGISTRY_CHECK.json记录边界，不把根68条都说成远端已合。Projects无read:project待同步。

## 下一步

用户按RUN_FIRST_ZH.md设置55nm SS库和许可环境，先用submit_smoke.sh提交2小case。读取RESULT.json/setup/hold关键路径后决定改流水线；不要用工具退出码或RTL周期替代STA。时序确定后再定义活动窗口提取PT功耗。当前不重跑PPL，不改PR192或TLM默认。
