# Issue182 存储改进
负责人jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines；task/182-memory-hierarchy，PR base main5273e5d9。
范围：标准2ch DDR4-1866/16GiB DRAMSys；SRAM同8MiB由16bank/16GBs改64bank/64GBs；DMA预取与本地program分离，显式一波响应缓存，保留原Attention/随机/FFN数值合同。
独立目录tmp/memory-hierarchy-issue182-20261025；未修改179未提交资料、其他成员#118/#117及暂停#116/#123。
本地13独立生命周期/工作量/容量检查通过，完整回归与DRAMSys运行待完成。初始Git HTTPS失败，API获取GitHub签名main commit原件并验证SHA后导入，树及两个父已存在；没有伪造新基线。
不自动合并，完整面积/能耗仍未知；新版响应缓存、加宽广播/接口需要PPA。Projects待权限核验。后续复现及发布以本目录最终RESULT/EXECUTION/HANDOFF为准。

执行更新：本地0855eab4三组完整36层Link对照已完成，1412.979260/1343.787260/879.747880ms。局部结果完成mtime早于下一次model.py修改，原件SHA通过。
正式完整DRAMSys执行7e44b6a4d49d7ba4237c84a105f9a56338fc7f35；数字chunk65536在阵列扫描中保持不变。
Slurm2912两个tiny真实桥接门禁通过；全模型Slurm2913_[0-10]%8，1CPU4GiB每项，无GPU。远端/home/Hongjie_Zeng/projects/pbit-memory-issue182-20261025/execution_7e44b6a4/。结果待收；不得改冻结source或重跑健康项。
小基准2911完成8/8，旧启动失败2910保留。DRAMSys连续吞吐约27.59GB/s，小基准不是全模型。小证据在work/jieruiz/182/dram_microbenchmark；大trace留远端。
