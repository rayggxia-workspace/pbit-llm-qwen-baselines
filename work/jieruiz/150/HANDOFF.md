## 2026-10-23 Issue150：FFN固定多档完整PPL

负责人jieruiz，task/150-fixed-multiscale，PR153待审未合并；执行49bc6bd1356413585c99dad6513d25cc34cff090。Slurm2840/2841/2842已产出全部封存结果：21项完整WT2、12候选selection、4holdout，0缺失/无效，299077计分token、24层所有forward输入覆盖通过。固定W8/A8共享64随机分层、原准确attention，非物理IID或RTL性能。无需重跑。

TRAIN独立拟合/选优后冻结d2_h0：每层每64通道x/z各自固定S、S/4、S/16、S/64，无在线absmax/扩档。BF16 11.652735；W8 11.681130；固定mean 11.691441。三seed均值：动态32 11.736131、固定32 11.851810、只固定x32 11.746519、只固定z32 11.838450；动态64 11.693775、固定64 11.736412。全固定64接近原动态32；省前端但采样翻倍，尚不能称能耗更低。主要质量差距在z，未测联合随机attention/跨语料。

正式报告qwen/results/static_multiscale_20261023/REPORT_ZH.md，完整数值SUMMARY；实际表SELECTED。原件83文件9.95MB已压缩为510435B，project_archives/fixed_multiscale_20261023/SEALED_RESULTS_49bc6bd1356413585c99dad6513d25cc34cff090.tar.gz，SHA6829e50ba08f8c25d7611c5aac5eba6b96232df46ad652dc8a35fd06ed7dd13e，逐成员核验；Git只留必要摘要、固定表和RAW_INDEX。服务器ROOT /home/Hongjie_Zeng/projects/pbit-qwen-static-multiscale-20261023-issue150不改，按索引恢复。交接work/jieruiz/150/HANDOFF.md。Projects查询缺read:project待同步；sacct关闭，完成依据签名校验JSON而非sacct。无新RTL/PPA/TLM，不自动合并/关闭Issue。

## 执行与恢复

1. Issue150、PR153；base pbit-tlm-attention-details-20261016@6966739a5223680888bf0315f7bb4f73423a1ae6。发布分支task/150-fixed-multiscale；GitHub核验身份jieruiz。
2. 数值执行仍是49bc6bd。后加collector/报告不进入已提交的snapshot。模型/数据/源码/配置/SHA和Slurm命令见SUBMISSION、PACKAGE及RAW_INDEX。原BF16同轮重跑后才校准。
3. 先按RAW_INDEX恢复归档到新目录；运行collect_static.py --input 恢复目录 --output 另一目录。不要修改封存JSON或把摘要目录当原件目录。全部完成，无本任务剩余GPU评测，不取消他人作业。
4. 三seed结果及方差见SUMMARY.json。只有TRAIN selection选档，holdout/test没有调参。K=T分层不是自然IID；fixed_mean不是整个随机非线性网络的数学期望。动态控制数值复现旧Issue46。
5. 硬件只明确可取消在线absmax，仍需选档/转换/恢复；2160组E8约2.11KiB元数据，不包括计数/标签，尚无功耗面积实测。不改默认TLM。
6. Helper task/150-fixed-scale-kernel已在干净状态回收；原提交7b25c20/305493f仍有Git ref，等价交付6054792/6b5cb47已纳入主分支，不删除实验历史。
7. Projects API实测INSUFFICIENT_SCOPES/read:project；Issue/PR可以更新，看板待有权限维护者同步。未合并、不关闭Issue，不创建定时。
