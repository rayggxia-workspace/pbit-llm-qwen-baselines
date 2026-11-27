# Prefill面积文献及INT8对照交接

Issue225/PR266，rayggxia，task/225-cim-bank32-20261124，复用tmp/cim-bank32-tlm-issue225-20261124。源基线ad0ba743525041e3ae1d566221f172ba6c91a439；新改动在同目录prefill_core_sizing_20261127。仅研究/已测数据重计，不启动远端任务，不改decode默认或冻结数值结果。

用户怀疑28nm4B/2K prefill是否必需上一轮大面积；补充允许Attention INT8。文献和本项目矩阵数据表明不必：旧96/192核属未优化点；INT8替换可减少大量BF16复制价，P-CIM局部吞吐密度也确实输给DCIM，能量与吞吐/面积应分开说。

复算：python -B architecture_tlm/process_28nm/prefill_core_sizing_20261127/review_int8_area.py。依赖AREA_REVIEW_INPUTS.json和同目录原RESULTS.json；三文件最小快照结果字节一致。原estimate/RESULTS保留。INT8_REVIEW_VERIFICATION通过，源码/数据SHA在新机器摘要；四份原价来源与三作者文件SHA见SOURCE_VERIFICATION.json。

下载原件在本地tmp/pdfs/prefill_area_20261127，DUET/MFSA PDF及SoulMate作者PNG，约5.3MB，原件不上传Git。SoulMate脚注2 Input32/Output32/context1024是重要纠正，不要当1K或2K全量prefill；DUET 28nm仅阵列校准，系统7nm。MFSA cell/die面积严格分开，不强套1GHz给本项目。

新候选：权重广播到8token簇，每核16而非128行，保持DRAM权重总复用128；状态载荷12→1.5MiB，以512个4KiB bank分布到2MiB物理预算保带宽。本地CIM写8倍、FFN计算+program .710秒。尚无真实bank/队列/广播控制/PPA验证；不宣称完整1.8秒/47mm²新芯片。INT8 Attention的模型精度也未评估。当前21bit局部结果增量价仍未知，旧19bit价格仅说明量级。

下一步优先小形状多token广播与状态驻留的有限调度回放，再比较共享P-CIM后端的确定性位串行prefill；不接管其他对话训练和RTL，也不重交健康任务。个人STATUS/项目备忘录本地同步，Issue28远端按维护流程待同步；PR未合并，Projects未操作。已推送状态以PUBLICATION.json为准。
