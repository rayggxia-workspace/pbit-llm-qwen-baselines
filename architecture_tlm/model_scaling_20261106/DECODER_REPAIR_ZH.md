# SC100跨模型残差地址绑定修复

2026-11-08，Issue245 / PR247；与前端成本近似无关。

首批三个worker在完成各自Qwen case后，进入Llama100 SC时报unmapped activation live object:136192+64。原QK供数包装器闭包里的compact-SRAM真实submit仍引用Qwen5KiB残差边界；Llama需要6KiB、DeepSeek需要8KiB。旧胶合只把新decoder写到外层函数globals，未绑定到真正使用vector_address的函数。

本次仅对SC100且hidden>2560，沿真实submit闭包找到唯一使用该decoder的globals并绑定现有模型映射。没有增加SRAM、端口、核数、价格或前端服务，也不改变量化/采样算法；其他30个完整case继续原不可变源码。Qwen4928个旧映射16B字逐项不变，三模型真实100MHz内存包装层复制残差、读取元数据及排空通过，物理容量保持1114112B。

远端独立修复快照161da0452c99，manifest e0dab7ae23936722ae3ebf6aabe803699093f44f7021732450840120b40d46fa；旧快照3a7dd5e0679e不改。38634043两项Llama/DeepSeek native冷单层门禁均已0:0完成，并逐SEAL/SHA核验；38634044已成功提交恢复。

- lost array38634114_[0-2%3]：先分别重做原失败的12/13/14（修复源），再接回未启动的20/21/22、28/29/30（原源）。
- DeepSeek修复38634115/16/17：afterany各自原worker0/1/2，保留它们前面的健康工作，之后补24/25/26。
- 新汇总38634118严格等待原数组结束及恢复成功；只接受36个唯一、全层含head、native、VALIDATION/SEAL/SHA通过的case。6个指定SC100 case接受修复manifest，其余30个必须保留原manifest。只取消旧依赖已无法满足且仍PENDING的聚合38631676。

2026-11-08 22:38北京时间实核：7/36完整case已核验；原5健康worker与3恢复worker运行，3个后续修复及新汇总等待依赖。不将单层门禁或运行中写为完整结果。实际CPU分配3核/任务，Python逻辑线程1；无GPU。旧失败输出保留，后续其他错误须单独核查，不能因允许成本近似而忽略执行失败。

恢复只读命令：`python -X utf8 -B work/rayggxia/245/mainline_20261108/repair_status.py`。不得重执行repair_submit.py。准确root、作业及封存SHA见delivery/DECODER_REPAIR_RECEIPT.json和REPAIR_STATUS.json；辅助脚本/本地预检与发布回执在同一work目录。CLI443不可用，正式发布由连接器完成；PR待审不合并，Projects待维护者同步。
