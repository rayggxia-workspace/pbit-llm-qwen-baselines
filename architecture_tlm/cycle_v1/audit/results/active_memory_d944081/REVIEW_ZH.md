# PR125 已发布 ActiveMemoryKernel 的隔离兼容审查

结论：在本次固定源码与当前 GQA 图范围内，没有发现阻止将其作为**后续探针候选**的 P0/P1 问题。这里没有采用、修改或合并 PR125 的实现，没有运行 2K，也不是全 Kernel 输入空间的等价证明。

- 仅从 `fi23` 的 Git 对象读取公开 commit `d944081a22dc346a3a50d505633e5d15c857ba78`，未读取该工作树的未发布文件。
- 路径：`architecture_tlm/ffn_cycle_integration/active_memory.py`；Git blob `17d400e9e58fa271127eb0fdb1a3ef93ac6f9087`；原始字节 SHA-256 `7e4c9534e40b493956a2ae94b6b6b1cd97e4a0d6052e6aff75637828941d4296`。
- 实际被测 root HEAD `cb5aa82db084b813a8bdfeb6a5721a864e2fff08`；所有导入的项目 Python 文件逐个 SHA 记录在同目录 `RESULT.json`，以这些实际源码散列为兼容边界。

## 独立验证

检查器 `audit/verify_active_memory_candidate.py` 在自身进程内加载公开源码，临时替换 GQA 工厂的 Kernel 类；没有修改 root 文件。37 个既有独立审查方法全部通过，合计运行 5.914 秒：

- 17 个 GQA 方法中，47 个实际构图场景分别运行原 Kernel cycle/event 和候选 cycle/event，共 188 次执行。每个场景四方比较完整 `equivalence_payload()` 和整个 GQA state，检查结束时 live-memory 表清空。
- 四方场景包括 32 个随机稀疏图、非连续/无序候选、重复采样、混合 exact/PV、native PV、replay winner/rejection、slot/window/operand 为 1、不同返回顺序、有限带宽和延迟 histogram 屏障。继承独立标量数值断言，不把候选自己的结果当数学 oracle。套件中另有直接调用工厂的地址/容量拒绝、失败采样与字节污染检查，它们保持原 Kernel 路径；不能计作候选四方覆盖。
- 20 个 core 方法在候选上通过独立手算时序、随机 DAG、随机字节内存与 native clock-process 断言；这些方法未全部另做原 Kernel 对照，不能与上面的四方场景混称。
- 另加 1 个动态内存图，四方执行 4 次：先读后写、写后读、连续写、callback 动态增加请求、尚未注册的 producer、部分依赖完成与 CDC。读回初始 `ABCD` 和最终 `WXYZ`，完整执行 payload 四方相同。

## 代码审查判断

`_live_memory` 包含已登记且尚未完成的所有请求，包括依赖未满足的请求，并保持登记顺序。完成通知发生在原 Kernel 已经固定本拍全部 accept/complete 决策后的 COMMIT 阶段，因此删除 live 项不会给同拍接受提供旁路。地址冲突仍按原登记序选择第一个重叠且至少一方写的请求。

依赖 cache 的 missing set 由完成通知逐项删除，最后一个依赖完成时调用原 `_dependency_ready`，保留 earliest/born/CDC 规则。`Operation` 原合同拒绝重复依赖，故集合化不会丢失合法重复项的 stall 文本。未来 producer ID 可先登记 waiter；动态加入、已完成依赖及跨时钟 visibility 已覆盖。

独立 AST 规范化对照表明，候选 `_next_event_time` 相对本次 root 版本仅新增“当前缺失依赖原因与已经报告的 accept stall 相同则跳过该 pending 项”的三行逻辑；其余事件选择一致。依赖完成通知会更新 cache，因此部分依赖变化、最终可见性、内存 bank/response port 和 native process 事件保留原路径。

## 保留边界

这是依赖 Kernel 私有状态和 `_next_event_time` 源码副本的主机模拟优化。后续 Kernel 改变完成写入机制、内部字段或事件选择时，必须重新核对和运行兼容检查；不应自动把当前结论推广至其他版本。直接在回调外修改 `completed`、私有图状态或缓存并不是本次支持的合同。

所有 operations、trace 和 memory read payload 仍保留；live scoreboard/cache 的通过不证明大图的内存或运行时间可承受，也不证明 2K 会在预算内完成。此审查不新增硬件吞吐、PPA、STA、完整模型或 PPL 证据。
