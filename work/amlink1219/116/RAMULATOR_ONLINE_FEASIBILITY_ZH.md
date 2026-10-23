# 在线 Ramulator1 接合：本轮不实施的边界与下一步

结论：本轮不能可靠地把真实在线 Ramulator1 后端压缩成25分钟实现、再保留至少20分钟独立审查。因此保留现有 banked 后端，未修改 Kernel，也未新增仅能包装成功却不能证明因果一致的适配器。

## 已存在的可复用材料

- 固定 ONNXim 上游为 `a1e86296e080fa1c82f8ad3f1b6de1079c192afc`，个人服务器源码目录 `/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/ONNXim-archive`。
- 实际静态库 `build/lib/libramulator1.a`，SHA-256 `55d8f59f1c04ed7b35c33251220b1603e6ff6bb426869a5bc309393f4df8e0d5`。这证明构建产物存在，不是 cycle_v1 已调用它。
- `extern/ramulator_custom/include/ramulator/Ramulator.hpp` 的 wrapper 提供 `isAvailable(addr,bool)`、`push(addr,bool,core,void*)`、`tick()`、每通道 `isEmpty/top/pop`。
- 底层 `Memory.h` 提供 `virtual double clk_ns()`、`void tick()`、`bool send(Request)`；`clk_ns` 来自 speed entry 的 tCK。当前 wrapper 不公开该方法，真正桥接应导出并核对所选器件配置，不能用宿主假定频率。
- 本任务 cycle_ops 子代理只读核实 `DDR4.h` 的 DDR4_3200 tCK=0.625ns，可精确表示为625ps。其 readme 中的钟速仍须和具体实例化配置绑定。
- 同一代理核实 `Controller.h`：453行调用 `issue_cmd`，最终 WRITE 命令在476–478行立即执行 callback；READ 在472行设置 `depart=clk+read_latency`，353–361行 pending 到期才 callback，每通道每 tick 至多一个 read 返回。WRITE callback 因而是命令发出 ACK，不能直接宣传为与 READ 等价的物理完成/写恢复完成。必须明确写可见性、写依赖解除点以及库内部后续 timing 约束，不能随意补一个猜测延迟。
- 原 statlist 会写当前工作目录 `ramulator.stats`；每次实验应使用独立个人运行目录，避免覆盖其他实验结果。

上述新库/API证据来自本轮队友的实际只读文件检查；没有新增 Ramulator 作业或包装运行。此前 ONNXim 的 MOVIN/COMP/MOVOUT 试验仍是明确的外部有限窗口服务探针，不因此升级成 Ramulator 证据。

## 为什么不能直接替换 plan

`MemoryRuntime.plan` 当前是无副作用的 bank 端口预留与固定 `due_ps` 计算。Kernel 在读旧状态阶段调用它，多次查询 stall/future-ready，并用 shadow 状态决定同沿多个请求。把有副作用的 `send` 放进去会让查询变成提交，造成重复发送、拒收后的信用无法回滚以及遍历顺序依赖。

`_Flight.due_ps` 又被完成排序、返回端口、事件跳跃及执行/堵塞计费同时依赖。真实异步返回前不知道完成时间，不能给一个“估计 due”后离线改总耗时；需要显式 arrival 状态和回调到达事件。ClockProcess可以推进外部库，但它本身不会自动提供现有 MemoryRequest 的 RAW/WAR/WAW、跨 burst 完成或返回信用。

## 最小正确后续实现

1. 定义 descriptor 与 burst 两层身份。请求按真实地址/事务大小拆分，保留 byte mask、write payload、部分接受位置；拒收保持相同 ID/地址/数据，不能重发已接受 burst。
2. 明确有限 frontend queue、backend outstanding 和 return/operand queue。外部 callback 不能被反压时，发送前预留足够返回信用；拒收不计费，实际接受只计一次。
3. 后端 tCK 和 Kernel 时钟统一为整数ps。明确 tick、send、callback到达、Kernel可见性顺序，并保留旧状态握手契约；无活动时不能跳过会改变 refresh/队列状态的外部边沿。
4. 拆分命令发出、返回到达、数据可见和下游消费。独立确认 WRITE ACK语义；每个 descriptor 仅在全部所需 burst 达到约定完成点、返回队列可交付后解除依赖。
5. 在独立可选 MemoryBackend 接口中管理异步 flight、arrival、事件时刻、统计。保持现有 banked 默认分支及历史结果完全不变，不用私自修改 `_flights` 的临时补丁绕开协议。
6. 固定独立 C++ driver 与 Python接合，给相同请求序列，比较实际accept/reject、burst ID、每回调时刻、写依赖、响应队列和最终字节；覆盖拒收、乱序、window1/return1、跨line与RAW/WAR/WAW，再做一个实际query的逐拍/event对照。

这项工作需要新后端与核心接口的独立验收，不应挤占当前GQA共享缓存正确性和私有真实输入回执的审查时间。
