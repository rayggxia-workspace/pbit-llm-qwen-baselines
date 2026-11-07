## 2026-11-07 Issue225：用户选定100MHz FFN六核，SRAM维持1216KiB

新增architecture_tlm/ffn6_100mhz_20261107，真实构造默认6公共核，组合现100MHz sharedQK/有限供数；前16/后32分层、18/34拍，8核回退/12核对照。CURRENT_100MHZ.json在sram1216宿主下指向新入口；旧冻结参考和250目录不改。目标C19、GU18/Wd19bit、外传20bit及跨K64bit仅宏合同，按旧C20每核价，不假称新C19实测。

同实际1216KiB/304bank/32权重槽/两state口两信用的冷完整形状FFN，本地解析外存136.4606GB/s30ns：5/6/8/12核589.06/566.26/568.40/576.48us。四配置帧6080+3040、算术/随机动作和外存地址sum/xor守恒，写量相同，输入缓存读随核数真实改变；12类检查通过。非新原生LPDDR整token/PPL/PT。5核比6核慢约4.03%；粗权重吞吐5核120.47、6核144.56GB/s，峰值136.46理想最少6核，额外串行开销余量约20.19ns/帧；实际110GB/s理想可5，不能称通用全系统最小。

SRAM维持1216KiB：32槽256KiB/写并行、GU96KiB、24KiB入口保持及其他分区不动，核内两结果槽已经随核价删除不重复扣SRAM。GU峰值76KiB、Wd20KiB顺序复用；未来96→80KiB仅省16KiB/.108mm²，未实施。新覆盖面积33.692mm²（上一12核41.562），完整新TPOT留null。未提交服务器/GPU/EDA任务，无新电路run。

顺带修复PR248审核P2：活跃fastsim只支持原profile带宽的采样数扫描，100/10GB/s现在拒绝，固定带宽参考保持；核数扫描用实际worker，不更改校准profile互相抵消。原封存执行源不改；root旧fastsim为owner SOURCES固定引用而保留，新修复位于本任务checkout及PR。首次namespace导入/漏math两小错误已修，不称有效实验；6/8/12原runner字节及仅CLI扩到5的差异保留。发布以PUBLICATION为准，PR248待审，Projects待维护者同步。

---


