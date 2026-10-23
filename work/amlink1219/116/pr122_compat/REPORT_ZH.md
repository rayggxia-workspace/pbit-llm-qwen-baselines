# PR122 与 Issue116 当前核心的兼容复验

结论：固定 PR122 `8007d98f15676ad316180ee18b5d1b29aa00af95` 的未修改软件，调用 Issue116 `e2695e294d6b7fcb73ec9257cb63f2fe2fef0cc8` 的四个后端文件，28 项软件/协议测试与 12 例接合矩阵均通过，未发现本边界的接口不兼容。

执行方式是从固定 Git 对象导出独立源码目录，只包含该包的 8 个 Python 文件及 2 个既有算术 oracle。10 文件 SHA 同时核对 PR head 与 scientific commit `3e8cb017e71a96aa628b1772810b7fdf12884245`。未修改 PR122 工作树，没有将其业务代码合入本任务，也没有改动旧 v6 或历史结果。

后端通过该包已有 `--backend-root`/`ENCODE_CYCLE_BACKEND` 接口加载。执行 checkout 是本任务的 cycle23-core；加载前逐字节验证 `__init__.py`、`contracts.py`、`kernel.py`、`memory.py` 与指定 `e2695e2` 完全相同。精确 SHA 见 `results/START.json`，实际命令及每条退出码见 `results/COMMANDS.json`。Python 3.13.3 使用 `-I`、清除 `PYTHONPATH`，独立目录与本任务后端是明确输入。

新执行证据：

- 28 项算术、adapter、独立协议回归：包括 W=-128 计数表示、FP32 次正规舍入、latency/II、有限结果槽全事件守恒、停顿、逆字典序组名、跨组 FP32 累加顺序、两个 adapter 同 Kernel、后端缓存绑定。
- T16/T32/T64 × 两种计数表示 × 1/4 恢复 lane 共 12 例；每例两组 64 输入和 64 输出，合计 1,536 次完整输出恢复。每例 cycle/event 全 payload、数值、动作及直接 W8 dot 参考均相同。
- 12 例均为 2,970,000 ps；这是下游单加法器 II2/初始300ns停顿条件，测试计数生产不计真实 SC 时间，不能据此比较完整 FFN 随 T/lane 的性能。
- 新 3 个输入 JSON、12 个 case JSON 与 1 个代表性完整 trace 共16份，与 PR122 的原冻结结果逐字段完全相同；比较不是只看总时间。`results/COMPATIBILITY.json` 保留原记录 SHA 与每份比较状态。
- `results/MANIFEST.json` 覆盖本轮新结果、日志和执行回执的字节 SHA。

PR122 原有 27 RTL 场景、6,861 输出仅作为其冻结回执引用。本次没有调用 Icarus、没有提交 RTL 作业，不能把它们计入本任务新执行数量。引用文件是该固定 commit 的 `work/amlink1219/121/VALIDATION.json`，SHA `45d8b476d62ce5cd2732c3c1def1c35682732806331caf56c4a80ffdf46d032b`。

复现命令（目录须全新，backend checkout 四文件必须仍等于固定 e2695e2）：

```text
python -X utf8 -P work/amlink1219/116/pr122_compat/replay_compatibility.py --backend-root . --source-directory /new/independent-source --out /new/compatibility-results
```

本轮只建立该接合 API 在固定版本间的软件兼容证据。它未将编码/恢复包装接入完整 FFN 数据流，也未统一 RTL 和 TLM 的逐沿协议，更不构成 STA、PPA、PPL 或全模型完成结论。
