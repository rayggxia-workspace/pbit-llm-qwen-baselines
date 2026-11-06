# Issue225：归一化权重逐层双缓冲

2026-11-06，rayggxia；task/225-norm-stream-20261106；独立tmp/norm-stream-issue225-20261106；base main8cd4fba009598184bce4f1c806f038299b011ea0。接续225容量阶段，不覆盖旧PR226、旧工作树、旧封存或运行任务。PR和实际远端发布以PUBLICATION.json为准。

## 用户决定及实现

用户确认没有精度损失即可把全模型归一化权重常驻改掉。正式architecture_tlm/norm_stream_20261106。新make_model默认stream_2m；保留resident_2p5与stream_2p5配对。原BF16 gamma按字节搬运，两个16KiB槽、tag/ready/released，所有当前层消费者完成再覆盖；embedding取首层，QKV并行预取下一层/最终gamma。没有新量化、RMSNorm数学变化、FFN/Attention采样变化或资源删减。

实际Qwen32Q/8KV/d128：36层表392192B→片上32768B；每token加载一次392192B。2MiB仍512个4KiB/16B/1RW bank，激活及公共FFN宽状态重排到前256bank，声明2008KiB、余40KiB。核数12/T64、数字1024、Attention8组不变。面积按已有宏价格预计67.541446→64.096551mm²，非新RTL/布局后结果。

旧RoPE/headnorm宏未展开gamma SRAM读，本次三配置共同增加每层512B的明确读取，原算术延迟不变；因此新resident对照不是旧49.56325ms封存的逐拍复现。精度无损来自参数/公式不变；TLM不执行真实数值PPL，不能把数据搬运oracle叫完整模型验证。

## 实际验证与作业

源码本地d3acb0eec66aeed84b36ffe343f0e29d285f32f5；执行6份Python源SHA在SUBMISSION.json，执行包identity dd115edf65dda4804fa061911f1974dd3ba3dddab81fdaf533c4d0d86cf2c03e。8项本地检查PASS，EDA机制门禁38614101 COMPLETED/0:0、4秒，8项同样PASS。三配置两层预检38614102，九项完整36层+lm_head（三配置×三seed）38614103，afterok依赖，不重复提交。具体最新状态读STATUS.json/Slurm，未封存不算完成。

EDA冻结执行根及只读依赖在本地SUBMISSION.json；依赖Issue236 retry_time_audit_ed028cc70e06，manifest7c5cb9b603ca2bd139ac6fa7b75d789e00c316acde994ff3db9bdcbb33c4bb40。输入、价格与bridge SHA在REMOTE_PROBE.json；不能修改其原件。CPU1/任务、最多6并行、12GiB、8小时上限、GPU0，无许可EDA。

## 恢复步骤

1. 先读Issue225、当前PR、本人STATUS及本文件；执行`python -B work/rayggxia/225/norm_stream/ops.py status`，不要再submit。
2. prefix三项成功后完整数组自动开始。出现失败，保留失败/源版本，只提交针对失败的新快照，不能修改已提交6份Python源。
3. `ops.py collect`仅读取SEAL验证SHA后的RESULT/BUDGET，并验证源、能量/面积/队列守恒。九项完整与三个不同部署seed齐全后再汇总均值；部分prefix不得作为完整结果。
4. 对比resident/stream2.5分离搬运影响，再对比stream2.5/stream2.0分离容量和bank重排；检查392192B额外读、headnorm共同读、全36层/final覆盖、原始矩阵工作量与Attention输入不变。报告真实时间、背景及动态能量，不仅面积公式。
5. 正式结果回到同目录和本Issue/PR；更新根同字节阅读副本及Issue28备忘录。Projects无可用写接口，待维护者同步。

未知项：新整机配对时间/能量待封存；新bank外围/布线、PHY等延续原未价边界；Llama/DeepSeek原生适配未做，不把Qwen的2008KiB或PPL直接迁移。原统一入口和在跑任务未被静默改写；新的可选入口默认2MiB供下一轮选用。

追加实际回执：38614102三配置两层前缀全部COMPLETED/0:0，三份SEAL及源SHA已核。矩阵/Attention actions完全相同，流式多读32256B（含下一层预取）；2.5MiB常驻/流式同2.36889ms，2MiB为2.36845ms。两层不是整token，九项完整任务仍待封存。源六份Python未改，PR248 ready/open待审未合并，主体d428823e9e18832937a968db236b6ad5a6de15de、16文件逐内容回读一致。

最新：复用runtime的93份源码逐项manifest核验通过；完整38614103已实际6RUNNING/3等待数组并发额度，0完整封存。长期备忘录canonical/root同字节更新；实际上传回执见PUBLICATION.json，不混入其他任务备忘录未提交改动。
