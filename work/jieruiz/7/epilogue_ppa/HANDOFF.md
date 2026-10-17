# SwiGLU PPA 交接

2026-10-17，负责人 jieruiz；Issue #7 的工艺表征续接，未创建重复 Issue。
正式目标 rayggxia-workspace/pbit-llm-qwen-baselines，基线 dac6e0426da6421ccc62077275e236532ca3c3da。
分支 task/7-epilogue-ppa100，独立目录 C:/Users/86134/Documents/a_P_BIT/tmp/ffn-epilogue-ppa-20261017。
原 tmp/ffn-cim-issue-7-20261017 和 PR #8 不修改；PR base 为 task/7-ffn-cim-scheduling。

## 完成

- ppa 下 DC、VCS 端口逐周期 TB、PT PX、活动向量/裁剪审计、单位/逐单元汇总、Slurm快照/校验恢复、报告归档与上传包。
- 100MHz，TT 1.2V25C / SS 1.08V125C，各18窗口；真实运行仍未执行。
- 原算术 SV/LUT/黄金模型不变，不强制分离组合逻辑。组合门共享无法精确归属于某一个功能算子，按未归属组合逻辑报告。
- 已读最新 Issue #7/PR #8，README main与任务分支；两分支无 AGENTS.md，遵守工作区用户给定规则和待审治理PR。无该RTL子目录额外AGENTS。
- Issue 分工评论 https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/7#issuecomment-6232866285。

## 实际验证

本地工具 Icarus 10.1、Python 3.8；ppa/local_test.py 运行18窗口，每窗口4096测量周期+8排空，
active/burst/idle有效结果4096/1024/0。每拍数值、valid、饱和和inexact核对，VCD窗口无X/Z。
测试截断波形/X拒绝、断点结果篡改拒绝、功耗单位/细胞求和、负slack标记；Bash -n通过，Tcl info complete通过。
这些不是 DC/PT 命令实际执行验证。版本兼容尚需服务器首跑；Python运行主流程仅标准库，兼容3.6。
可复现命令：

```powershell
python architecture_tlm/rtl/ffn_epilogue_20261017/ppa/local_test.py --iverilog C:/Users/86134/Documents/a_P_BIT/sc_weight_storage_or4_20261014/tools/iverilog/bin/iverilog.exe --vvp C:/Users/86134/Documents/a_P_BIT/sc_weight_storage_or4_20261014/tools/iverilog/bin/vvp.exe --ivl-lib C:/Users/86134/Documents/a_P_BIT/sc_weight_storage_or4_20261014/tools/iverilog/lib/ivl --out C:/Users/86134/Documents/a_P_BIT/tmp/ffn-epilogue-ppa-validation-20261017
```

Windows旧版MSYS/Icarus在沙箱中DLL加载失败，经受控权限执行成功；首次路径斜杠不兼容已修复并全部重测。
LOCAL_TEST.json 是上述验证摘要；大型VCD留本地tmp，不上传Git。没有模型/分词器/训练数据，均为合成事务，故BF16参考/PPL不适用。

## 下一步

按正式ppa/README_ZH.md上传zip，用户服务器 source ~/.bashrc 后解压，验证清单并提交all。
默认2个array task各4核8GB8h，TT/SS各综合一次。无服务器任务ID，因为尚未提交。
结果results/JOBID_0.reports.tar.gz、_1.reports.tar.gz及logs目录；检查SHA、POWER_CALCULATED、summary、coverage与时序。
不得把FLOW_COMPLETE当布局后时序清零。负slack、覆盖不足、check_power警告均需审查，任何X/Z禁止直接忽略。
项目看板权限缺失，待同步。原PR和本次PR均不自动合并/关Issue。

## 发布状态

本地已完成；远端发布链接与提交在最终同步后追加。工艺结果尚无。
