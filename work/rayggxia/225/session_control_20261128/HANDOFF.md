## 2026-11-28｜Prefill到Decode会话TLM已接通

Issue225/PR266，rayggxia，task/225-cim-bank32-20261124。入口[SESSION_ZH.md](architecture_tlm/unified_v6/SESSION_ZH.md)，[结果](architecture_tlm/unified_v6/results/session_control_20261128/REPORT_ZH.md)。软件层模板/容量规划、有限任务/资源池、共享DMA/SRAM及本地引擎控制已串成会话；复用原unified_v6事件内核并同字节打包最小依赖，不改原decode默认或上游RTL。

实际完成Qwen3-4B全宽36层、4输入/2输出、seed17、250MHz五核、GU16/Wd32/PV64：从空KV写入prefill，各层KV最终5位置，首输出后仅一次decode，GU/Wd合计1094400/547200帧。宏访存条件下TTFT256.297724ms、后续间隔98.350092ms、总354.647816ms；final Norm+head合计24.223736ms。宿主591.41s，本地执行无Slurm/GPU任务。完整JSON通过独立MAC/字节/KV/封存SHA复核；12项单测通过。小形状17/503/1009三seed与原有逐拍SRAM/64B请求后端对照通过。

**范围**：这是控制完整、数值/外存后端尚待升级的会话TLM。Attention地址是合成fixture；两种DRAM均解析带宽/延迟，不是新Ramulator回放；不能替换旧51ms/token封存结果或声明PPL。FP24统计格式/动作及存储，不做4B数值前向；完整能量/面积为null，只计已知SRAM/4pJbit分项。当前计划4行只允许3输出组并行，12槽限制导致五核不能假定全满。prefill RTL仍是旧21/64参考，未假称完成移植。

下一步接真实Attention轨迹与现有模块服务、原生LPDDR，再做128/2K输入和状态/核数扫描，补齐FP24/23bit等价格。长输入尚未运行。STATUS/HANDOFF/源manifest与本地项目备忘录同步；无新数字电路run。PR待审不合并，Projects未操作，Issue28远端备忘录依既有维护流程待同步。

### 恢复

- checkout：C:/Users/86134/Documents/a_P_BIT/tmp/cim-bank32-tlm-issue225-20261124，本地Git HEAD仍9da829cfb084b757fec9b3b0b52c68f2e6b3ffc8，API发布基线b35fcebd0e1b00f54b82f77d5eeca4b952889dae；准确远端状态以PUBLICATION.json为准，不推历史origin。
- 命令：`python -B architecture_tlm/unified_v6/test_session.py`；`python -B architecture_tlm/unified_v6/run_session.py --prompt 4 --generated 2 --out <新目录>`；`python -B architecture_tlm/unified_v6/verify_session.py <结果目录>`。Python标准库，无GPU/EDA环境需求。
- 正式结果来源`work/rayggxia/225/session_control_20261128/full36_v3`，执行快照`execution/v3`，SOURCE_MANIFEST逐文件SHA未变。早期smoke01失败、v1/v2开发长跑已中止，未封存为完成；v3完成，无当前任务运行。
- 代码SHA、模型revision、硬件配置、种子和精确完整命令见SOURCE_BINDINGS/EXECUTION_SOURCE_MANIFEST；不加载权重和文本，因此无新模型权重/数据SHA。数字逻辑台账未虚增电路run。
- PUBLICATION_INDEX是唯一提交白名单。新普通源码/结果小于1MiB；依赖内核为原Issue227文件同字节快照，不含工艺资料。保留原脏文件及其他成员目录。
- 原生外存未接，不因短合成逐拍对照通过就泛化长Qwen性能。真实地址、Native LPDDR、长输入及完整价格属于下一步。
- 根模块交接指针已同步；Issue28远端备忘录待原维护，Projects未操作。PR不自动合并。
