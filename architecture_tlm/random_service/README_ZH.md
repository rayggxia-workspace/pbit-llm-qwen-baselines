# 随机源服务与核心RTL v1

Issue #95，基线83e15289434af50fc09c35e699d8b39965389d98。Python ≥3.10，标准库即可；本次使用Python3.12。用户自行做工艺综合/功耗仿真，本实现不输出估算W、J或mm²。

## 交付内容

| 后端 | 状态 | 每次接受请求的输出 | 状态推进 | 启动 |
|---|---:|---:|---|---|
| `lfsr32` / KIND=0 | 32bit | 1×8bit随机字，附1个比较结果 | Galois展开16步 | 新32bit种子 |
| `lfsr32_shared64` / KIND=1 | 32bit | 64×8bit随机字＋64个比较结果 | 同一16步更新＋GF输出网络 | 新32bit种子 |
| `bivium` / KIND=2 | 177bit | 20×8bit随机字＋20个比较结果 | 非线性反馈展开160步 | 新177bit种子＋5拍/800步预热 |

第三种是Bivium-B非线性反馈生成器，不是普通线性LFSR，也不是密码学认证实现。共享64路精确复用项目2026-10-15的默认映射，不重新搜索种子或训练连线。其任意两路联合秩16、总秩32；512个输出bit不等于512个独立bit，不能直接保证Attention全候选联合分布。

目录：`backends.py`整数参考，`model.py`逐周期协议/种子总线，`service.py`调用适配，`sampler_adapter.py`接现有采样器，`rtl/`可综合SystemVerilog，`tb/`测试平台，`verification.py`逐沿核对/活动波形，`diagnostics.py`有限统计诊断。`DESIGN_QUESTIONS_ZH.md`保存选择、疑点和剩余验证。

## 物理随机性如何传到上端

```text
物理噪声核心 → 读出/采样 → 检查/必要调理 → 同步合格32bit字接口
  [本次不实现模拟、调理、CDC]                  │ valid/ready + qualified
                                  共享种子总线（模型按包轮询）
                                           ↓
                               rng_seed_ingress：1拍或6拍拼包
                                           ↓ seed_valid/seed_ready
                              PRNG装载 → Bivium预热 → 本地随机服务
```

本版有意采用**直接新种子分配**：每个端点每个epoch取得自己的新数据包，没有免费SHAKE派生、没有相同种子广播到所有PRNG。LFSR用1个32bit总线拍；Bivium用6拍192bit，低177bit进入状态，15bit明确记为丢弃。将来可另加经过验证的根种子扩展模块，当前不假装已经有其RTL。

上游`qualified`只是供给协议声明，不能替代物理熵证据。未合格字使入口锁定fault，复位后才能恢复；不自动使用固定种子继续。多位异步物理接口必须先握手同步/异步FIFO，不能逐bit双触发器同步后直接拼字。

复位后`seeded=0`，请求不能成功。零状态包被明确拒绝，不偷偷换成1。默认每100,000,000个时钟沿到期一次，10ns时钟下约1s；`reseed_cycles=0`表示仅启动播种。计时从装载开始，包括预热和空闲；到期后停止接受新帧，排空旧输出再接新种子。用户保持输出ready为0时，重播种等待，数据不会丢失。

FFN的保存/重放窗口通过SAVE锁定epoch；周期到期可以延后，但`reseed_deferred_cycles`明确统计。RELEASE后执行待处理换种。无限不释放会无限延后，这是调用方必须遵守的有界窗口约束。

软件来源三类严格区分：
- 默认`os`使用操作系统CSPRNG，每次运行重新获取；不是已验证的物理熵。
- `trace`读取用户提供的合格字和来源元数据，可回放物理采集/仿真数据；耗尽报错，绝不循环回放假装新熵。Spectre噪声轨迹也必须标为仿真而非硅实测。
- `fixture`必须显式传固定seed，仅做可复现测试。执行回执保存所有实际种子字和装载epoch。硬件的真正随机启动取决于接入真实合格熵源，RTL没有能力自行创造该证据。

## 周期和调用语义

`RandomNetwork.tick(requests, readies, commands)`是一整个网络的一个时钟沿。多个本地端点在同一tick并行执行；只有种子总线共享。端点没有隐藏请求队列，只有一个响应寄存器；首帧延迟1拍，输出可消费时II=1，是否满足目标频率由综合/时序决定。

tick返回`pre`为沿前信号，`accepted/consumed/seed_accepted`为该沿握手，`valid/words/bits/state`为沿后状态。第c次tick接受的帧，在边界c+1可用。下游反压时响应保持、PRNG不推进；同沿消费旧帧可接受新帧。不要将保持期间多个时钟沿重复算成新随机样本。

```python
from architecture_tlm.random_service import *
net = RandomNetwork({'x': Endpoint('lfsr32')}, SeedWords(mode='os'))
port = RandomPort(net, 'x')
port.command(1)                         # SAVE，并锁定当前epoch
a = [port.shared_input([128]*64) for _ in range(32)]
port.command(2)                         # RESTORE同一状态，不是重播种
b = [port.shared_input([128]*64) for _ in range(32)]
port.command(3)                         # RELEASE，允许到期重播种
assert [r['bits'] for r in a] == [r['bits'] for r in b]
print(net.report())
```

阻塞适配器便于TLM调用，顺序Python调用就是串行服务。需要多个消费者同时发起时使用单次`net.tick({'x':q_x,'y':q_y})`。返回的等待周期、更新次数和总线活动来自同一条时间线，不由CPU运行时间换算。

概率统一显式为9bit `q∈[0,256]`、比较`R8<q`，包含精确0和1端点。旧A8的0..255仍可原样传入；旧权重q/127不能无声明变成q/256。本版不提供旧双随机权重编码的透明替换。`uniform_below(1..256)`用拒绝处理范围，失败仍收费，禁止有偏取模捷径。

硬件`rng_endpoint`每次都生成原始字及比较结果；即使只使用随机字，操作账本仍记这一实现的比较。综合可能裁剪未连接输出，回填成本时必须对应实际top和端口用途。组合翻转、毛刺、时钟树无法从功能操作计数推导，需用户门级/功耗工具测量。

## Attention适配

26个Bivium端口可在一帧提供520路8bit随机字；使用其中512路，额外8路活动仍收费。辅助公平位用另一端点，不复用候选随机字。`FullFrameArray`检查容量，禁止悄悄分波；默认拒绝GF共享后端，只有显式相关实验可放开。

`TimedSamplerSource`已通过可选`draw_at/fair_at`接口接到现有赢家保持/校正拒绝采样器。旧理想源和默认入口保持不变。慢播种、预热、等待均进入采样器时序；真实PRNG操作记在源账本，等待不能当作更新。源报告为累积值，多个查询汇总只能加差分或最终总计一次。

驱动经显式`SigmoidTable`转q/256：步长0.125、最近网格/四舍五入概率，有饱和端点。它改变目标分布，不能继承理想Softmax/PPL。LUT查表和阈值写入以配置吞吐计时/计操作，**尚未交付这两块的RTL或工艺时序**；源核心/入口的周期精确性不等于整个Attention已是周期精确RTL模型。动态旧q8驱动和新q/256概率是两次不同量化。

## 运行与验证

从仓库根或便携包根运行：

```bash
python -m unittest discover -s architecture_tlm/random_service/tests -v
python -m architecture_tlm.random_service.demo --output run_new/demo.json
python -m architecture_tlm.random_service.demo --mode fixture --fixture-seed 17 --output run_replay/demo.json
python -m architecture_tlm.random_service.verification --output rtl_new --iverilog iverilog --vvp vvp --vcd
python -m architecture_tlm.random_service.diagnostics --output run_new/diagnostics.json
```

输出目录必须是新的，避免覆盖证据。默认验证3后端×3固定seed×900沿，包括启动零包拒绝、周期重播种、回压、保存/恢复、复位和不合格字故障；每沿比对沿前握手、沿后数据/内部状态。另有64路FFN完整前端测试。大波形和编译产物不进入Git，生成命令和小汇总保留。

`trace`文件格式：`{"provenance":"采集来源/版本/质量评估及是否物理实测", "words":[32位整数,...]}`。需要的样本率应以原始源质量/调理吞吐另定；`--word-interval`是**调理后的32bit字间隔**，不能当成每个裸源的独立位率。

## 操作统计和工艺回填

PRNG更新/预热、递推步数、输出bit、比较、输出寄存器写、种子总线bit、装载、保存/恢复、回压/播种等待分别计数。复位导致未消费响应被取消，`frames_generated`与`responses_consumed`可以不同，不应强行相等。周期总数和原始bit数不代表有效独立样本数。

所有面积/能耗为null，绝不使用原TLM占位pJ。本次提供的RTL、活动向量、VCD和`POWER_SIM_ZH.md`用于用户标定。各硬件resource只统计一次；不要同时加整宏PT总能耗和该宏各操作能耗。

## 参考与来源

- 本项目`rng32x64_design_20261015/manifest.json`和`rng32x64.sv`：GF映射、Galois掩码0x80200003、16步跳转；提取后的文件记录原SHA，旧文件不修改。
- 本项目`architecture_tlm/rng_reference.py`：独立Bivium逐位参考，本次用它交叉校验新Python实现。
- [OpenTitan prim_lfsr](https://opentitan.org/book/hw/ip/prim/doc/prim_lfsr.html)、[Bivium/Trivium包](https://github.com/lowRISC/opentitan/blob/master/hw/ip/prim/rtl/prim_trivium_pkg.sv)：参考生成器概念/公开递推；未复制其控制与安全功能，不宣称完整兼容。
- [UnarySim](https://github.com/diwu1990/UnarySim)：参考逐拍随机字、阈值比较、流指标分离的建模方式；没有移植其PyTorch实现，也未继承其任何质量或PPA结果。我们的新增重点是供给/种子/回压与RTL对照。

本轮没有运行模型PPL、GPU、Slurm、DC/PT或新Spectre。PR验收范围是接口/模型/RTL功能交付，非完整芯片PPA或随机独立性验收。

