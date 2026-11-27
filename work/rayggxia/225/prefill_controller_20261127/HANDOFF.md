## 2026-11-27｜Prefill控制RTL原型与实测开销回填

Issue225/PR266，rayggxia，task/225-cim-bank32-20261124。独立目录architecture_tlm/process_28nm/prefill_controller_20261127，[报告](architecture_tlm/process_28nm/prefill_controller_20261127/REPORT_ZH.md)。16项矩阵命令FIFO、动态派核/组K依赖、每块8KiB驻留最多32行、每核双结果槽、共享16KiB DMA和两路32通道交错状态SRAM；Prompt sequencer单独遍历prompt/层/最后位置head。沿上游真实整数采样核，未改decode默认或上游源。

本地Verilator5.054，29个进程/215项检查PASS，三seed17/29/43、随机回压、T8..128、3行尾块、40/152长K、1/4/5/6核。独立事件整数oracle逐项一致；命令队列16项满等待、双结果槽填满、DMA256×64B credit满、取消排空重启均覆盖。状态双II1的2048beat为1027拍，同bank2050、同地址4096拍；没有把冲突当成无成本。32行跨token权重复用使对应权重读取4MiB→128KiB（−96.875%）。

实测GU16/Wd32最短行间隔21/37拍，旧预算18/34为核级简化；本次复用的RTL DMA每核128包×II2使8KiB装载下限256拍，不是CIM写口的32拍，6核实际首行接收需376～389拍。仅回填两项下限并保留旧数字/Attention宏预算、128输入/27GB/s有效外存：MiniCPM3-4B 6核由1.228→1.545秒；若回填实测装载区间则约1.664–1.677秒。均为组件预算，完整prefill Decoder、数字计算与激活物理映射尚未接入；GU/Wd合成码分阶段回放，不是完整FFN模型/PPL，也无新PPA/STA。优先DMA每核发包与行间交接，再做整层集成。

中央run prefill-controller-225-20261127，任务与根镜像分别增量check/render，通过并保留旧记录。SOURCE_BINDINGS/RUN_MANIFEST记录准确源码/原日志与可执行文件SHA。旧decode/64bit状态/价格不改，无远端作业；PR待审不合并，Issue225广义工作保留，Projects未操作，Issue28远端备忘录按原维护流程待同步。

### 执行与恢复

- 正式任务Git根：C:/Users/86134/Documents/a_P_BIT/tmp/cim-bank32-tlm-issue225-20261124。本地Git对象HEAD仍9da829cfb084b757fec9b3b0b52c68f2e6b3ffc8；本轮执行基线远端23a1fd51ce7ed4aa53913895897a1aee4cbdda03，加本目录未提交源码，准确字节见SOURCE_BINDINGS。API发布后以PUBLICATION.json为准，不把本地HEAD写成远端最新。
- 命令：python -B tools/build.py --kind state/prompt/matrix（分别调用）；matrix最终--jobs8；python -B tools/run.py；python -B tools/summarize.py；python -B tools/record.py。准确命令和工具链见BUILD、SOURCE_BINDINGS、RUN_MANIFEST。
- 上游依赖根为本机architecture_tlm/rtl_stage2_integration_20261121，仅只读引用，未自动发布上游未公开源码。独立state/prompt可直接构建；matrix需具备该依赖包或后续正式发布版本，--rtl-root可指定。
- 无Slurm作业或GPU模型任务。本轮没有prefill PPL、功耗/面积新标定、STA或完整模型TTFT。
- 优先下一步：接统一激活SRAM供数及层任务展开/数字矩阵服务；改DMA支持同核更密集发包或多包并行，明确写口与上游端口带宽；然后完整层/模型prefill回放。输入码接口按6核满载约需GU5.71/Wd5.19GB/s，加尺度元数据。
- 本地STATUS保留旧未提交历史并增加本轮块；发布STATUS在最新远端历史上增加同一块，历史部分可能与本地旧副本不同。优化证据原JSON不改，新精确证据在中央run与SOURCE_BINDINGS。
- 发布范围仅PUBLICATION_INDEX；不提交上游工艺库、编译中间件、波形或大权重。PR不合并。Projects未操作；Issue28远端备忘录待原维护流程同步。
