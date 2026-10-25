# Issue182 存储改进
负责人jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines；task/182-memory-hierarchy，PR base main5273e5d9。
范围：标准2ch DDR4-1866/16GiB DRAMSys；SRAM同8MiB由16bank/16GBs改64bank/64GBs；DMA预取与本地program分离，显式一波响应缓存，保留原Attention/随机/FFN数值合同。
独立目录tmp/memory-hierarchy-issue182-20261025；未修改179未提交资料、其他成员#118/#117及暂停#116/#123。
本地13独立生命周期/工作量/容量检查通过，完整回归与DRAMSys运行待完成。初始Git HTTPS失败，API获取GitHub签名main commit原件并验证SHA后导入，树及两个父已存在；没有伪造新基线。
不自动合并，完整面积/能耗仍未知；新版响应缓存、加宽广播/接口需要PPA。Projects待权限核验。后续复现及发布以本目录最终RESULT/EXECUTION/HANDOFF为准。
