## 2026-11-08 22:51：独立250MHz完整评估2/3seed已完成

38629485的seed17/503已完整36层＋head并0:0完成，SEAL/VALIDATION/工作量/账本与原字节SHA通过，已归档project_archives/tlm_energy225_20261108/0和1。时间均50.418948ms，片上25.206577/25.206643mJ，外存4pJ情景总198.370253/198.372088mJ，覆盖22.086073mm²。末seed1009已完成36层及finalnorm、head运行，预计CPU墙钟20～60分钟，不承诺。

正式250MHz/FULL_PARTIAL_20261108.md/JSON，仅部分结果、未算三seed最终汇总；不与245不同胶合源混seed。三模型245目前7/36已核，5健康＋3恢复worker运行，暂无新错误。未重提/改冻结源，无新GPU/RTL/PT/PPL。PR249仍draft/open未合并，Projects待同步。

---

# Issue225 / PR249：有效TT250接入与能量账本

负责人rayggxia；复用tmp/tlm-unified250-issue225-20261107、task/225-tlm-unified250-20261107。开工远端PR249为4b68739ca7c09eede55ba8a7379123dc63a407e9，base为PR248的task/225-norm-stream-20261106；100/250仍隔离，不自动合并。已核对身份rayggxia、Issue225、249/248/244/247及本分支STATUS/交接；不动其他目录untracked材料。

已完成9个源/校准文件接合，FFN_PROFILE绑定delta_pipeline_v3（输入profile SHA c4be790270d496177bb6a5a0c33cc6700b636f840840523bbd92559683dc747f）。单一合同驱动76/140ns服务和19/35拍，SS100参数保持；原负结果与provisional证据保留。新增energy_ledger，按资源唯一归属、SRAM全物理容量、root gating逐项核对，FFN gross+剩余idle与增量+全idle等价。旧FFN已有正确口径，没有发现该项重复计费；物理CIM接口/全NoC/PHY等仍是明确未标定边界，不伪称芯片全实测。

四项测试通过。local_layer是解析136.46GB/s30ns完整尺寸单层，1.085720ms；执行时run/bootstrap最后账本导出字段尚未添加，原始结果不重写，来源SHA照存。正式最终执行代码在新冻结snapshot.zip/MANIFEST，增加5件封存校验。38629484原生单层门禁COMPLETED，1.195020ms、22.086073mm²、4.671014mJ（含外存4pJ/bit）；5件+SEAL逐SHA复核，归档project_archives/tlm_energy225_20261108/gate，索引COLLECTION.json。

完整36层＋head为38629485_[0-2%2]，seed17/503/1009；各1CPU12GiB8h，最多2并行，0GPU。精确执行目录/manifest/runtime/dependencies SHA见SUBMISSION.json/MANIFEST.json；快照c1820e20bc73不可改写，不重交健康作业。当前完整结果尚未结束。

重要纠正：配置m256_v2_s4_n4_tmicro4_r16的r16是16路FP32归约，不是SparQ维数。SparQ仍32维，QK单层2621440MAC、投影26214400MAC；完整L层另加head389M MAC。ops.collect只收completed封存件，并独立核对这两项。旧跨模型文档的r32→r16所谓缺口是误读，应按本条纠正，而非改变筛选算法。

恢复：Codex附带Python运行本目录ops.py status / collect；collect保留同SHA结果，不覆盖其他输入。执行后已整理profile的job/status/ICG文字，并补派生incremental/frame兼容字段；EXECUTED_FFN_PROFILE保留原字节，PROFILE_NORMALIZATION列两SHA，原数值输入和SS100保持。ASSEMBLY_STATUS同步960KiB及当前作业；原catalog不改。上传前按实际文件清单add，公开接合代码/数值/小汇总/SHA，私有owner执行包/轨迹和PDK不复制。

正式说明ENERGY_CLOSURE_ZH.md。根阅读镜像13文件已同步ROOT_SYNC，长期记忆/STATUS已同步。源07bc39de3f75b3a10628862879921bfde8ae91a4共30文件远端回读一致，PR249正文与Issue225已更新；PUBLICATION记录回执。PR仍open/draft未合并，完整token尚未封存；Projects待维护者同步。
