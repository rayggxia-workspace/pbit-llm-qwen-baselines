# 架构检查台：先看执行事实，再审硬件假设

Issue104，负责人jieruiz，集成基线`eb317e4f6fb1b0d8844887401f3275f128ef8a83`。

直接用浏览器打开 [model-inspector.html](model-inspector.html)。这是自包含离线页面，不需要下载库、上传数据或启动服务器。也可在本目录执行 `python -m http.server 8840 --bind 127.0.0.1` 后访问本机页面。页面的源码链接指向准确Git版本；结果的封存提交与产生结果的执行提交分别记录。

用户需要能自己检查，而不是依赖口头解释。本版提供五个检查面：

| 检查面 | 能看到什么 | 不会假装已经知道什么 |
|---|---|---|
| 整机与模块 | 21个可点模块，输入输出格式、当前实现、屏障、代码行与SHA | 不把合成事务画成真实模型数值执行 |
| 次数与周期 | 保留输出、提议/拒绝、源lane工作、FSM服务周期、FFN波数/恢复；串行换算尺 | 不把S、sweep、CTMC时间或lane×cycle当硬件周期 |
| 执行时间线 | 52项完整phase，按层查看；资源忙时与等待；有标注的事件前缀 | 不把历史80事件补画成几千万条完整底层轨迹 |
| 存储与格式 | 静态SRAM区域、独立残差/x/z/部分和、局部计数状态、时钟、K/V物理读 | 不把预留量当动态live占用，不把计数状态当免费 |
| 证据与全面检查 | 每情景独立不变量、执行/配置/结果SHA、缺项能量、未闭合清单 | 不把通过模型账本检查等同于物理正确、质量无损或最优 |

整机默认仍使用足量本地随机接口。已合并PR97提供实际源握手；PR103仅验证薄前端/小接口，尚未接入完整decode。页面不改变这条边界。新训练筛选器PR94也不是本批默认max4路径。

## 新增的观测接口

之前的完整52项结果保留全量phase，但只保留前80条底层event、前16条简略attention行，缺少逐query的FSM分解。本次没有改写原件，而是在模型旁路增加：

- `stage_busy_ns`：原Scheduler已有的全量stage服务汇总。
- `stage_cycles/stage_calls`：采样FSM每阶段周期和发生次数，不受详细trace开关影响。
- `sampler_audit`：每`token/layer/head`的候选、输出、proposal/attempt、拒绝、源lane工作、起止、时钟和逐阶段账本；不保留全部比特流或地址列表。

四项新观测在 `results/observed_v3/`：完整Qwen24层2K seed0校正拒绝，共336个query；另有赢家/拒绝/串行的微型连通样例，各2个query。完整Qwen的旧序列化字段与原封存结果严格逐项相同；没有调整时间、动作、能量或容差。执行`124d37d2dca5020451b6e64f19ddede882042371`。每份观测的模型/上下文/seed/S/时钟和SHA独立展示，不能拿微型或Qwen数据替代另一个模型。

串行诊断只展开到每attempt服务宏，输出搬运单列；新增字段本身不使模型成为全芯片周期精确仿真。

## 建议逐项检查的顺序

1. 固定模型、上下文、seed、FFN/Attention方案，先核版本与证据。数字BF16、数字W8、随机FFN对照分开。
2. 从embedding逐模块点击到lm_head。检查维度、精度、残差旁路、编码/恢复、权重驻留、KV追加及gu→SwiGLU→down屏障。
3. 进入次数页。先明确计数覆盖单query、单层还是全token，再看并行宽度、II、配置/源读取/归约/仲裁/反馈/输出。赢家默认8倍输出预算必须单列；输出数量不是ESS。
4. 查看阶段时间线与等待。完整phase可以合计到墙钟；不同资源busy及等待不能重新相加。旧event只展示保存前缀的前10条，原件完整80条可由链接查看。
5. 查看SRAM/局部状态、K/V并集和物理字节。确认“无随机流SRAM”没有掩盖源状态、计数器、保持电路和阈值寄存器。
6. 逐项检查未闭合表。在权重供给、计数状态、格式转换、源调度和器件成本落实前，不能用不同缺项的小计相除宣称整机能效。

## 复现

Python3.10+，标准库；在Git根执行：

```sh
python architecture_tlm/inspector/build.py
python -m unittest architecture_tlm.inspector.test_inspector -v
python -m unittest architecture_tlm.checks.test_observation_hooks_v6 -v
python work/jieruiz/104/validate.py
```

`build.py`校验52个原件与基线Git blob逐字相同，运行阶段/采样/容量/字节/版本不变量，解析准确源码行并绑定SHA，核验新观测来源/逐query覆盖与阶段守恒，然后生成页面。`snapshot.json`为构建中间件，不必进入Git；离线HTML已包含所需数据。

若要重新执行新观测，先提交精确源文件，再使用全新输出目录：

```sh
python architecture_tlm/inspector/observe.py --output NEW_ABSOLUTE_OUTPUT_DIRECTORY
```

旧JSON数组与Python内存tuple须在JSON线格式下比较，不以容差掩盖差异。前两轮导入/比较器诊断保留索引及本地归档；详见Issue104辅助资料。新观测属于CPU上的合成事务，不是PPL、GPU、PT或真实DRAMSys执行。

本次结果与主要发现：[CHECK_REPORT_ZH.md](CHECK_REPORT_ZH.md)。
