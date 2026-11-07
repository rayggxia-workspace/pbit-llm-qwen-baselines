## 2026-11-07 Issue225：250MHz在本人宿主下独立建目录，不提供完整TLM

用户明确250MHz结果与100MHz分隔，250尚不完整，可先不给完整模型。已建architecture_tlm/sram1216_20261106/250MHz/：README、模块证据目录MODULE_CATALOG、组装状态ASSEMBLY_STATUS和独立validate_catalog。无运行入口/默认导入，整机时间/能量/功率/面积均null；普通池320/640仅候选，未定核数、SRAM时钟或共享QK调度，不影响100。

TT1.2V25℃250MHz，项目55等效面积由rawx.81一次；功耗/能量不随频率猜。204八模块8/8报告来源已验收，本轮核8归档大小/整包SHA、沿用3119成员SHA记录，包含GF64/完整C20T64/前端/后端/state32/数字CIM/OS/WS；整核与组件不重复计费，向量与DOT64单位分开。T8/T32及GU74/Wd53未做新TT250PPA，不改名套价。

198旧九模块18项17正常退出、FMA64/250超时缺3窗；自动归档也超时，无完整报告包SHA，当前只元数据索引，不作完整系统价格。新PV4先闭100门级X，再TT250；共享QK包装/真实K供数/归约32单价II及其他250接口未绑定。已有数据“未绑定”不表示未仿真。若池320不能借512QK，需重映射；外存LPDDR带宽不乘2.5。

11项目录隔离/PVT/单位/缺项校验通过，100MHz宿主/采样/Attention候选三历史manifest的32成果SHA全部不变。无新任务、EDA/GPU/PPL/RTL/PT，不改198/204源或队列。100MHz优先候选combined32未作已验证默认，原因是PV门级X和QK真实供数尚未闭合，不是算法已否定或要求所有电路都做完。

辅助work/rayggxia/225/tt250_catalog_20261107/build_catalog.py、HANDOFF、ISOLATION_VALIDATION和SOURCE_MANIFEST；同Issue225/PR248/工作目录，根250MHz目录为同字节阅读镜像，发布以PUBLICATION为准，PR待审不合并，Projects待维护者同步。

---

