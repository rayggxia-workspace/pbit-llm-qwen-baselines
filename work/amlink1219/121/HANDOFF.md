# Issue121 交接

负责人amlink1219；任务分支 `task/121-encoding-cycle`；目标 `rayggxia-workspace/pbit-llm-qwen-baselines`，PR基线 `pbit-tlm-attention-details-20261016@46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d`。发布状态以PUBLICATION.json及远端ref为准，不自动合并。

已完成独立编码/恢复算术接口、显式计数标签、有限结果槽RTL、逐输出Resource/Operation调度。28项软件测试、12组cycle/event对照（1536恢复输出）及最终27组RTL（6861输出、108复位清空）通过。RTL CPU作业2767/2773均COMPLETED/0:0，主机10.129.164.156，未申请GPU；日志、归档SHA、实际源码SHA均已核。没有本任务运行中的远程作业。

正式入口 `architecture_tlm/encoding_restore_contract/README_ZH.md`。原计数总线和116的幅度表示不兼容；软件归约边界可接合，尚未提供幅度→原总线转换电路。极小数舍入反例已在软件/RTL验证保留。

后端冻结为116本地已提交 `cd27d980d9cfb68d7ed9761aba70d2faec4d4937` 中4核心文件，初次冻结时远端尚无PR。本分支只发布本任务内容与hash，不提前发布116源码。复现首先获得116公开分支/提交，核对BACKEND_SOURCE.json；若hash变化，重新运行test_adapter/test_review及run_cycle。当前PROFILE为条件保守模型，未完成RTL边沿→全部FFN的直接映射。

服务器唯一新目录：`/home/Weican_Chen/projects/encoding-restore-issue121-20261023`（及revision2）。已有个人116 Icarus工具仅执行未修改；本任务工具构建未发生。远程原源码/编译产物保留于各run-<job>，Git只放小报告。Windows打包工具被系统拦截后未执行或绕过，最终Linux CPU验证已完成，不构成结果缺口。

未完成：116正式发布commit回归与默认FFN接合；多编码组流水；真实模型输入活动与完整质量；T16/T64恢复RTL场景；STA/DC/PT/面积/每完整操作能量。PPA保持null，不能替换旧费用后宣称总能效收益。

下一步：核对Issue116及最新PR后，用README命令在其冻结公开commit复跑；把恢复动作按每输出映射，分开cross-k加法和窄化；不接管其他成员kernel/memory/Attention。Projects权限缺read:project，见PROJECTS_CHECK.json，仓库/PR上传权限不受影响。

## 实际发布

发布回执（Issue121）：科学提交`3e8cb017e71a96aa628b1772810b7fdf12884245`已上传[PR122](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/122)，87项远端Git对象一致，开放待审、未合并。Issue116已回传接合结果；后续元数据提交不改变验证源码。

具体回执PUBLICATION.json、DELIVERY.json。
