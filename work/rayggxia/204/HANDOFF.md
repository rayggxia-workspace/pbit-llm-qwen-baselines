## 2026-10-31 Issue204：非线性到Wd集成PPA已交付

负责人rayggxia，PR219/base task/206-group64-scale，科学结果提交36426f4ed48cce32cd3bd06bcf95ee62aa4accb7，open待审未合并。工作目录tmp/matrix-t32-issue204-20261028；本地历史分支task/204-bf16-baseline不整支推送，远端为task/204-gu-unified-code。

用户确认从已编码g/u开始。N64/M8/T32，SS1.08V125℃100MHz，34拍/340ns输出8点积；64完整Sigmoid LUT、192比较器及三流AND共用前端实际驱动8列固定Wd。raw面积仅乘.81一次。8/9位等价weighted归约436.6733/479.8533pJ/帧、.110074043/.118259255mm²；OR4/signed9为458.7733/467.9533pJ、.083171610/.087664291mm²。逐拍加权树后每列一个signed19累加器，与位平面exact的激励和oracle字节一致，不是输入先计数。

8配置/48PT全部完成，RTL及门级各11496逐拍PASS，100%映射叶单元活动覆盖；Slurm38475207/38475302/38475377/38475382均COMPLETED/0:0，无本轮遗留作业，不重交。68返回原件及1720归档成员SHA验证；两冻结源包不改。小源码ZIP SHA d99d30965a036efb1d3fc097a3cb61cbe4c188b73559eed15010a9e7b6bfe30d。15发布文件blob逐一远端核验。

报告/小汇总/源码索引：architecture_tlm/nonlinear_wd_integrated_20261031/results/。统一run nonlinear-wd-integrated-204-20261031，任务71/根镜像103/本PR47各自check/render PASS，保留旧record；未上传全局路径或归档CSV。源/原件归档project_archives/nonlinear_wd204_20261031；本地PUBLICATION.json、TRANSFER_VERIFICATION.json、REGISTRY_CHECK.json及LOCAL_RECOVERY.json可恢复。72生成fixture和54审核helper文件逐SHA归档后回收，本地PR目录保留。

weighted setup只15.3ps/1.8ps、hold30.1ps，功耗ramp告警保留，未物理签核。OR4与signed9饱和是近似；四档尺度和活动为合成，未做模型质量/PPL。GU/写前编码/SRAM/真实随机源与广播/跨K/BF16恢复/CTS/SDF/SPEF不在本轮。两共享LFSR旧价格24.8769pJ/帧仅条件代理，不当集成实测。下一步：审阅本PR，按真实活动验证近似质量并闭合实际外围/物理时序，不自动启动昂贵模型或新EDA。Projects写能力受既有工具限制，待维护者同步。Issue204保持open。

