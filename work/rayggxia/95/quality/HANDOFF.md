# Issue95 分层随机质量续作

2026-10-23，负责人rayggxia，连接器身份已核实；沿用Issue95。新最小目录tmp/rng-quality-issue95-20261023、task/95-rng-quality，基线6966739a5223680888bf0315f7bb4f73423a1ae6，目标pbit-tlm-attention-details-20261016。原95目录有旧API发布index，保持不动；本次新分支与其冻结交付分开。

实际执行8a862a38cf6e4e46f50e719f8b2b3877db745c75，配置与8文件字节SHA见正式quality/results/20261023；追加审阅/绘图没有修改原执行文件。189案例均完成，9机制测试通过；逐189NPZ/来源/输出算术和GF关系1269检查通过，浏览器2图/189行/3宽度通过。原始物理归档SHA d57893e605adc7b1463094a6ab717afcccab76915230e35fd619400f10a29760，9成员重新核对。没有新Spectre/RTL/PT/GPU/Slurm/PPL。

实际命令（仓库根）：

```
<bundled-python> -m unittest architecture_tlm.random_service.quality.test_quality -v
<bundled-python> -m architecture_tlm.random_service.quality.prepare_physical --archive C:/Users/86134/Documents/10月_MPW/analog_results/zero_cap_readout_38237164.tar.gz --audit C:/Users/86134/Documents/a_P_BIT/analog_pbit_20261016/review_38237164/archive_audit.json --out C:/Users/86134/Documents/a_P_BIT/project_archives/rng_quality_20261023/physical
<bundled-python> -m architecture_tlm.random_service.quality.run --physical C:/Users/86134/Documents/a_P_BIT/project_archives/rng_quality_20261023/physical --out architecture_tlm/random_service/quality/results/20261023 --raw-out C:/Users/86134/Documents/a_P_BIT/project_archives/rng_quality_20261023/digital --frames 4096
<bundled-python> -m architecture_tlm.random_service.quality.audit_results --results architecture_tlm/random_service/quality/results/20261023
python -m architecture_tlm.random_service.quality.report --results architecture_tlm/random_service/quality/results/20261023 --delivery C:/Users/86134/Documents/a_P_BIT/远端上传/rng_quality_20261023.html --archive C:/Users/86134/Documents/a_P_BIT/project_archives/rng_quality_20261023/results
<bundled-node> work/rayggxia/95/quality/check_report.cjs
<bundled-python> work/rayggxia/95/quality/register.py
<bundled-python> digital_circuit_simulation_registry/registry.py check
<bundled-python> digital_circuit_simulation_registry/registry.py render
```

bundled-python是C:/Users/86134/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe；bundled-node是同dependencies/node/bin/node.exe。绘图python为系统Python38，模型使用bundled Python。browser检查使用独立无头Edge，auto-review允许，无用户浏览器profile。

关键负结果：VN去偏后rho仍明显；GF前4路q128固定异或为0；同种子端点完全同流。未测试同时物理阵列通道、健康/熵率认证或长周期量产换种；当前1024拍及预收集1字/拍是隔离质量的测试设置。结果不是对整机默认的修改。

用户文件远端上传/rng_quality_20261023.html。稳定归档project_archives/rng_quality_20261023内physical、digital、results；Git只提交摘要、来源和小图。189原始NPZ逐SHA见SUMMARY；完整JSON2.28MB归档有索引。根台账与canonical同步时须保留其他任务的并行登记；当前PR未合并，引用本PR，不覆盖他人状态。Projects连接器未提供操作，待同步；不自动合并/关闭Issue。

## 当前发布阻塞

本次尚未创建新PR。发布前两次GitHub compare调用均出现chatgpt.com/backend-api/ps/mcp的HTTP传输异常；本机git ls-remote也报getaddrinfo线程启动失败。不是权限审批拒绝，未切换GitHub身份。前期Issue95的范围评论已成功，不能将它当成果上传。PUBLICATION.json明确pushed=false；上述“当前PR”指原97/113已合并交付，本轮需另建后续PR。

本地台账46记录check/render通过；根阅读入口已有另3条并行增量，本次仅添加同字节的新record，保留其全部原件并重建为49记录。根与canonical记忆在相同旧hash上追加，仍同字节；任务分支只追加本轮入口，不夹带其他未发布记忆。没有后台计算或远端作业。

网络恢复后：核实账号rayggxia、目标workspace仓库、最新集成和本任务分支；将新record与最新catalog合并重建，保留其他并行任务。按明确范围上传此分支/新PR，关联Issue95并附着本聊天；更新回执和STATUS，不重跑189项。SOURCE_MANIFEST及稳定归档支持原件复核。
