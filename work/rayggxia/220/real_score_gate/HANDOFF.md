## 真实数据结果已完成，恢复不要重交

源de13b021a375d5492e54190c54c28b70d8cc9005；Slurm3571/3572/3573完成，40成员原包SHA278aaed9d321dae6c57b427091fc52bfc4a45c3a8ae441cc9674fb89ef8726a0。全部原件/11封存JSON/1152期望直方图和全头指标复核，原生logits/NLL及36层通过。原80ae抽取失败/死依赖取消记录FAILED_V1保留，不冒充模型失败。

正式报告qwen3/results/p8_real_score_gate_20261031，原件project_archives/p8_real_score_gate_issue220_20261031/real-p8-de13b021a375.tar.gz及本人远端root同名文件。用validate_archive.py --archive FILE --source-dir experiments/p8_real_score_gate_20261031可重算，不需要大模型。原权重/大激活不放Git。状态及数值见SUMMARY/VALIDATION，发布见PUBLICATION.json。

13组训练矩阵保持；真实行完成率通过，但共同P8尾部/CR额外偏差存在，未知PPL及短训练梯度仍不能标为通过。CR作为备选。未启动长训/新RTL/PPA。PR221待审未合并，Projects待维护者同步。

---

# Issue220真实P8验证交接

负责人rayggxia；复用task/220-attention-ten-case-plan / PR221及本人独立checkout tmp/attention-ten-case-plan-issue220-20261031。不改旧source/既有作业。实验代码experiments/p8_real_score_gate_20261031；原训练矩阵11概率＋2数字和数值合同保持。

CPU小状态门禁→原模型单GPU原生QKV抽取→CPU真实行解析/MC。全部远程经Slurm，自己的source与结果在个人projects/pbit-p8-real-score-gate-20261031-issue220。精确提交、脚本SHA、作业号见新SUBMISSION回执。恢复先核Issue220/PR221/STATUS与队列，不重交健康任务，不修改已提交快照。所有阶段completed封存SHA通过后才可报告结果。

报告分开共同P8尾部、拒绝法有限128地址期望偏差、8192cap完成率和V误差。期望直方图不可当cap内实际成功输出；MC不是字面全部R8位图轨迹，另有固定行整数比较核对。未知Qwen PPL、训练、物理/共享源和PPA均不填。原件留既有授权个人存储，Git仅小型汇总/索引。
