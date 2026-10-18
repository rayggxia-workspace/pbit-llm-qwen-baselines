# jieruiz 项目进度

更新 2026-10-18T18:30:38+08:00；实际登录@jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines。

## 当前Issue22：Qwen短流能耗与RTL

- Issue：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/22；负责人@jieruiz。
- 分支task/22-qwen-short-stream；base=pbit-tlm-attention-details-20261016 @3553996bf014a29dee7fdb2250a3965e8fd881a4；checkout=C:/Users/86134/Documents/a_P_BIT/tmp/qwen-short-stream-issue22-20261018。
- 本地已完成：旧Qwen A8固定W/share64协议和源SHA核对；源码提交62a34e7可复算4组同功率TLM敏感性；独立重跑4组数值一致；100MHz旧锚点与附加功率假设核算；DC/PT模板和明确回填范围。
- 条件结果：T4096/256/128/64的SC核+前端为64.496/4.046/2.031/1.023mJ/token，整模型170.495/59.802/56.724/55.395mJ/token；不是新PT、GPU、详细DRAMSys或同精度结果。
- RTL独立子目录tmp/qwen-short-stream-rtl-issue22-20261018、分支task/22-short-stream-rtl；实际36配置252帧/202496有效样本逐拍通过，7组代表活动窗口通过；已cherry-pick为87a8102且最终源码/摘要/zip逐SHA核验通过。含内/外源、帧计数复用、精确G1、seed重播和strat256无RNG更新控制。
- 正式成果：qwen/energy/short_stream_20261018/，sc_short_stream_20261018/；辅助资料work/jieruiz/22/。权重/概率由外部帧内稳定接口提供，不新增银行；SRAM与上游seed保持另计。
- 证据限制：Qwen分层64/128尚未测PPL，本轮未提交GPU训练/评测；具体xorshift序列也未做模型质量验证；没有DC/PT工具或工艺库运行，不报告新面积/功率。TLM外存为Link，成本若干仍是旧占位。
- 复现修复：Windows autocrlf改变3个旧Qwen锚点工作副本；恢复为已签SHA的Git blob字节，并用窄范围-text属性防再转换；旧源内容及manifest未改，5锚点检查通过。
- 当前远端状态：Issue22开放；任务分支已推送，PR #25待审未合并：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/25。实际数据提交`92db8122028b0a5d329d8e9e4eccd680b7912768`；Issue评论已同步。Projects缺read:project待同步；其他工艺/模型任务不覆盖。
- 下一步：PR已上传，等待审阅；工艺方依据包内ppa说明回填PPA后再替换旧代理，精度补测另冻结协议。

## 其他仍开放任务

Issue19的阶段基线PR20已合并40ea9f1，回执PR21合并3553996；其剩余Slurm评测不因本任务而取消或标记完成，见work/jieruiz/19/HANDOFF.md。治理/DS-CIM/FFN后处理/筛选的其他待审分支保持原状态。

本地交付包：`C:/Users/86134/Documents/a_P_BIT/sc_short_stream_20261018_issue22.zip`，114436bytes，SHA256 `2963729f0886ba44623babd9a9e5a47fd28bfda59687450046919639149bdbca`；release源提交`c9c78588e706d882bb80ce99e92487ad2c654046`。

发布回执：2026-10-18T10:37:26.188552+00:00，PR #25、Issue22评论和精确head已核实；PUBLICATION_RECEIPT.json记录实际动作。无新权限阻塞，Projects待同步。
