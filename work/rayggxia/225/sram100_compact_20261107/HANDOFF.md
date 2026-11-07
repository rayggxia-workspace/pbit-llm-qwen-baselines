# 100MHz SRAM缩减交接

负责人rayggxia，2026-11-07；Issue225/PR248，分支task/225-norm-stream-20261106，base main；独立checkout为tmp/norm-stream-issue225-20261106。250依赖PR249须同步本轮100代码，保留其独有TT时序失败profile及960KiB默认，不能覆盖本人另一分支STATUS。

已完成：默认1088KiB/272bank，逻辑对象1056KiB/无DMA SRAM区域，前端176bank带宽保留；Attention8×48、scratch34KiB、输出47KiB。最紧1056只保168前端bank实测较慢3.03%，保留选项与负结果。两80KiB投影槽和全部算术资源/采样/信用不改。SRAM100_ZH.md/RESULTS.json为正式入口，CURRENT_100MHZ已更新。无新EDA/GPU/PPL/RTL/PT或电路台账run。

四项新增与八项历史布局检查通过；两轮5个冷单层封存，原始RESULT/BUDGET/SEAL共15份未重写。初轮源89bb0b9f，二轮c2d860f6；compare.py核对同轮源/输入、动作/帧/外存字节地址与队列，并保留初轮不同执行提交。原1216两轮均1.20762ms，新默认1.20615ms，面积34.14593→33.28471mm²。全芯片能量/原生整token为空，不能直接外推为新TPOT。

恢复：在本checkout运行test_sram100.py --project ../.. -v，或compare.py读取现有封存；不要覆盖已有out，不重复健康回放。若确需新回放，run_sram100.py --project ../.. --configuration compact1088bw --out <新目录>。受控源/输入由原bootstrap和10文件SHA校验；没有复制库、轨迹或私有执行实现。

上传状态见PUBLICATION.json；依赖分支同步见DEPENDENT_SYNC.json。PR待审，不合并、不关闭Issue。Projects待维护者同步。后续若要再省32KiB物理容量，应优化bank映射/宏组织并验证供数，而不是再次隐藏8个端口的代价。
