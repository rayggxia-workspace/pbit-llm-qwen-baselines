# Issue204：参数化模块能耗完整交接（2026-10-28）

rayggxia；task/204-matrix-t32，同PR205，base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166。执行基线9f762ced3d25b47bf3963fbf38ff8d321850854b；复用tmp/matrix-t32-issue204-20261028。新目录architecture_tlm/module_energy_20261028，不改旧冻结PPA或模型/整机默认。

用户授权测试不同输入/输出精度popcount和不同位宽移位相加，补时间累计器与组合验证估算边界。33个固定top全部VCS功能PASS，99次RTL回放/162396逐周期比较；另完成对应门级回放和396个PT窗口（3seed×sparse/dense/replay/idle）。全部所报setup/hold非负，最小2.643270/0.007787ns，功耗表范围警告保留；无CTS/SDF/SPEF。

关键结果：pop8/16/32/64 full输出dense单次0.05251/0.09941/0.19720/0.39630pJ；pop64少一个输出LSB面积只降约0.54%、dense能量约1.20%。9位饱和累计4.8554pJ/33拍（清零+32次）；六平面9位固定恢复1.3190pJ/35拍驻留一次。77/54/50状态位组合分别84.6883/69.4633/67.9817pJ/35拍，55nm等效面积6647.90/5524.07/5447.09µm²；54→50只省2.13%能量，48点积相对OR基线额外NRMSE0.969%→1.538%，非模型质量。

未经校准的独立模块和对bank高估约23%、对单平面约26%–27%；统一独立端口20fF与内部连接负载不同，且有相关性/综合/控制差异。用bank54校准后预测bank50，三seed最大绝对误差0.637%，仅是N64/同输入的位宽配置留出验证，不能宣称跨规模/全芯片普适误差。popcount+恢复树两项不足；必须补mask/OR、累计器、时钟/控制、调用次数与组合校准。共享输入计数属于随机输入量化+数字后端的独立对照，不能冒充本OR4路线收益；匹配确定量化数字参考仍待独立开展。

V1 manifest f454a321，349归档成员：旧Python不支持Path.write_text(newline=...)，38441318共33任务在EDA前失败，全部日志保留。V2仅修复driver，manifest cb9fb058b35c723970752bde9fd4e6ee4496808b2a380ad626e899c68ef5b8da，350成员。成功Slurm38441385功能、38442559四类pilot、38442655其余29类（全量4并发）；无遗留任务，勿重交已完成33/396。Windows Icarus DLL错误623导致本地功能工具不可用，pyslang0错225警告，实际功能门禁来自服务器VCS。

67报告归档、2源包原字节、远端/本地大小SHA和全部成员SHA已核验，stable project_archives/matrix204_module_energy_20261028。报告/完整JSON：architecture_tlm/module_energy_20261028/results；执行索引EXECUTION_INDEX.json；传输TRANSFER_VERIFICATION.json；中央新run matrix-modules-204-20261028，84条union check/render、83旧record原字节保留。源码和结果已推送，科学源080729c314e2e0e62efada3e32d4c27c7eac4bb5，68文件完整tree及10关键回读核验，实际回执PUBLICATION.json；PR205待审未合并，Projects既有权限限制待维护者同步。

边界：组合top没有人为I/O寄存器；顺序top含真实计数/控制/结果寄存器，CE非ICG。bank为预解码7幅值位W和乘积符号，abs(W)显式限127；SRAM/概率保持、RNG/比较器、编码/符号预处理、物理广播、最终格式恢复在外。pop缩输出位是丢LSB、单位2^DROP；固定移位与可变对齐分开。非16 pop的replay为IIDp=.35，align replay为随机字，其余由旧M8合成回放派生，均不是模型数据。原PT samples字段0为占位元数据错误，派生表按stim en补32样本/帧，原始字节不改。

后续：先用这组数据估相同接口/频率/负载附近的算术配置，扩大输入规模时补signed-popcount/增量宽度（当前累计器D6只对应OR后16路），并做新组合校准；新存储/随机前端/真实ICG/物理连线独立补齐。报告不按状态位比例推功耗，不把纯算术表当整机PPA，无新PPL/GPU。
