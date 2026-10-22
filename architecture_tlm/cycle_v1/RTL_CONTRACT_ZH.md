# 周期执行协议的 RTL 对照

2026-10-23，Issue116。**9 组 / 252 个接受、完成、消费握手已与独立 SystemVerilog 实现逐 ps 对齐。** 这验证的是有限流水、输出握手、FIFO 与单槽跨域 mailbox 的数字协议，不是 SC/FFN/Attention 数据通路 RTL、DRAM 控制器、综合、STA、功耗或 CDC 亚稳态验证。

## 验证对象与结果

`rtl/cycle_contract_pipeline.sv` 是可综合风格的有限在途流水和 FIFO，使用倒计数寄存器、读写指针、ready/valid 与每端口冷却计数。它独立于 Python 内核实现，不调用内核时序函数。单实例按接受顺序退休，输出每次握手后满足配置的 OUTPUT_II；输出 FIFO 满时，在途结果保留，年轻结果不能绕过。

5 组流水案例覆盖 latency=1/2/3/5/7、II=1/2、在途容量=1/3/4/8、输出 II=1/2/3、有限 FIFO 容量=1/2/3/4，以及初始满 FIFO 和延后消费。逐项比较输入接受拍、输出完成拍、FIFO 消费拍及 token ID，并比较实际最大在途/占用。

`rtl/cycle_contract_mailbox.sv` 使用一个稳定保持的数据槽、请求 toggle、应答 toggle，以及各方向两级同步寄存器。源端只有信用返回后才能提交下一项；目的端开始消费后，直到消费计算完成才返回应答。4 组案例采用 100 MHz / 80 MHz，目的时钟相位分别为 0 / 2500 / 6250 / 10000 ps，各传输 5 个 token，比较两端接受/完成时间和 ID。

CDC 的精确定义：请求在源沿提交后，目的第 1 沿更新 sync1，第 2 沿更新 sync2；按本拍读旧状态，消费者在**第 3 沿**接受。因此本例 `cdc_cycles=3` 表示三个目的沿的接受可见性，不能把 `cdc_cycles=2` 直接称为“两级同步器加同步消费者”。返回信用的两级同步通过 ack 操作表示：目的完成后的源第 1 沿接受 ack，源第 2 沿提交信用，后续生产者在源第 3 沿才可使用信用。

所有资源和 FIFO 均无同拍释放旁路；同沿出队腾出的空间不能同沿被入队利用。这是本实现明确的保守契约。capacity=1 / latency=1 的资源因此每两个沿才能接受一次，不能仅根据 II=1 宣称连续每拍吞吐。硬件若有旁路，需要另加契约和测试。

## 运行与可审计证据

- 服务器：`10.129.164.156:21570`，本人 `Weican_Chen`，计算节点 `gpu`；两个作业均只申请 CPU，`CUDA_VISIBLE_DEVICES=""`。
- 工具构建恢复：Slurm **2762**，8 CPU，57 秒，`COMPLETED / 0:0`。复用前作业已安装 bison/flex，补官方 gperf 3.1，再完成用户目录中的 Icarus Verilog 12.0。
- RTL 比较：Slurm **2764**，2 CPU，1 秒，`COMPLETED / 0:0`。使用该作业独立的 Python 3.12.3 stdlib venv；没有安装或修改共享 Python 环境。
- 机器结果：`results/rtl_contract_20261023/RTL_CONTRACT_VALIDATION.json`；各案例保留配置、编译命令、仿真 stdout/stderr、Python 预期与 RTL 实际握手。
- 回传原件的 SHA-256：`85071026f69532defbd57d875fdbe5be0d12a59e07024bdd01b3d0eb9abfe518`。93 项原始制品哈希全部核对。生成的 `.vvp` 保留于原始归档与服务器，正文结果目录省略；省略清单和哈希在 `LOCAL_RECEIPT.json`。
- 冻结源码快照 SHA-256：`7d0a6d3c08b4fda0f1e8e03f30d94fc783ac8a79496df48a74f4ebf14db6059d`。每个执行源文件哈希保留在报告；当前结果不随后续内核修改自动更新。
- 调度首终态、作业脚本、下载回执与原始归档位于 `work/amlink1219/116/rtl/`。初次工具任务 2761 因缺 gperf 退出 127，原失败证据保留，没有将失败任务计作测试通过。

重新运行：

```bash
python -m architecture_tlm.cycle_v1.rtl.validate_rtl \
  --iverilog /personal/tools/bin/iverilog --vvp /personal/tools/bin/vvp \
  --out /personal/new-output-directory
```

输出目录必须新建。不要直接在共享服务器登录节点执行；通过 CPU-only 调度分配运行。比较器保存失败案例和报告，不覆盖旧执行。

## 边界

这不是对整个周期后端的形式证明；这里只检查所列协议和参数。内存乱序返回、地址 scoreboard、真实随机网络、数值 FFN/Attention、跨进程共享状态等另由各自测试约束。数字 mailbox 仿真不提供模拟亚稳态、物理布线、同步器约束或 MTBF 结论。源代码可综合风格不等于本次已运行综合；未报告任何综合面积或可达频率。
