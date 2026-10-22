# Issue110：数字电路仿真统一台账

2026-10-22实际交付：PR111 ready/open，待审、未合并；科学payload a31e010d08e4afe3292316d476d99b1509d10603 已推送，9关键远端blob字节一致，47元数据Git/本机/固定入口一致。Issue110已同步，Projects GraphQL实际INSUFFICIENT_SCOPES/read:project，待同步。没有新电路或模型实验。后续回执提交只更改状态/索引，不改原件。

2026-10-22；负责人jieruiz。已通过GitHub /user核实登录身份；正式目标rayggxia-workspace/pbit-llm-qwen-baselines。基线eb317e4f6fb1b0d8844887401f3275f128ef8a83，PR base pbit-tlm-attention-details-20261016；分支task/110-circuit-simulation-registry，独立稀疏目录C:/Users/86134/Documents/a_P_BIT/tmp/circuit-registry-issue110-20261022。未修改Issue95/107/7执行源码或他人STATUS。

本地已完成35模块/批次记录、516配置行、117原始数字归档发现索引；所有原件不搬移/删除，大波形/网表/库不复制。入口digital_circuit_simulation_registry/README_ZH.md；records是登记主数据，00/01及CSV由registry.py render生成。本机根同名目录是同字节阅读镜像，正式编辑在任务仓库中；合并后从集成维护。

已读最新Issue95/107、PR列表、远端README/AGENTS/TLM索引与双方STATUS。尤其最新38322118随机服务实际PPA已经纳入，不能再说只有功能证据；后端38165794/38215256/38263376归档只做发现/有限元数据查看，未完整审核，不按旧报告断言仍失败。120.8uW旧预算无直接绑定原件，不冒充已核PPA。

实际验证：8项登记守卫；157独立本机文件SHA和26tar成员SHA全部通过，unavailable_here为空；见VALIDATION.json。没有新RTL/DC/PT/STA/GPU/PPL，无本任务远程作业。数值是原结果登记，非本次重新仿真；模块间边界不同不直接排名。

范围：数字仿真台账、README/AGENTS登记规则、本人STATUS、长期备忘录。根AGENTS保留原规则追加；canonical/root长期备忘录保持同字节；只同步小型元数据镜像。PR/实际推送与远端SHA回读见PUBLICATION.json/REMOTE_VERIFY.json；没有回执前只能称本地完成。Projects沿已核read:project不足待同步，不与repo写权限混淆。

复现命令：

```sh
python -m unittest discover -s digital_circuit_simulation_registry -p test_registry.py -v
python digital_circuit_simulation_registry/registry.py check --local --members
python digital_circuit_simulation_registry/registry.py render
```

build_inventory.py仅本次初始盘点快照，输入是本机旧结果；**未来不要用它覆盖新登记**。新增仿真按README模板和registry.py add，在对应任务PR内登记。旧原件SHA变化应调查，不改SHA掩盖；清理临时源目录先补归档位置。后续保留失败/负结果和旧源绑定，未知不填0。

下一步：本任务分支PR交付与评审；后续每次仿真由对应负责人追加台账。Issue保持open等待验收，不自动合并或关闭其他任务。原始工艺文件、外部下载压缩包和本机源码包不上Git；本任务无大型临时原件待回收，保留最小待审目录。
