实际交付完成：PR180已合入main，merge5273e5d9fdae811a714f1a278fee6e776c5675af；head0d97e2b5a2c01270568835964b2f4d581133a197。无运行中本任务进程；以下合并前条件文字由本行及MERGE_VERIFIED回执更新。

# Issue179 / PR180 交接

负责人jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines；分支task/179-latest-ffn-tlm-main；PR base main。用户明确允许本轮验证后合入main。原main fae12982e0a92dea1f81648a5eeee148974c4a87；依赖导入d6d33995754fcdcea99286e4ce43f91647aa231a；最新算法参考216f2b9939e9984f140290c98edb05db3aad5c0f，但没有合并训练PR178。

实现与执行：首轮9c8dc057；最终数值时序执行3a9ddfb1f9c3493df46478f3a802a8c69119b389。第一轮源warmup1152拍，第二轮用现有160bit展开端点对应的5拍(800步)作为宏参数。原件各run封存；不重写第一轮以冒充第二轮。新独立非线性源仍是有限宏，不宣称与现有源映射及独立性已验收。

本地：C:/Users/86134/Documents/a_P_BIT/tmp/latest-ffn-tlm-issue179-20261024 。仅最小源码和小型结果，未复制模型/数据/工艺库/历史大轨迹。无服务器/Slurm/训练任务，没有新增定时；昨天训练未动。

入口：architecture_tlm/README.md；unified_v6/FFN_CURRENT_ZH.md说明流程、数制、状态、周期和缺失模块；RESULTS_CURRENT_ZH.md为本轮结果。运行`python -m architecture_tlm`，默认Qwen3-4B、latest FFN、screen_rejection。保留`--ffn-profile legacy`。完整配置及SHA在每个EXECUTION/RESULT/MANIFEST中。

验证已完成：74项机制检查；7组完整36层Qwen3-4B decode；8组完整形状单FFN敏感性；15组三seed小形状整机检查。校正拒绝1152行各128有效输出、随机位及提案/周期守恒通过。全部本地运行结束，12份封存MANIFEST（含4组旧warmup结果）原字节SHA通过。最终记录UNITTEST_3a9ddfb.txt/RESULTS_CURRENT_ZH.md/DELIVERY_AUDIT.json。首次依赖精简漏rng_reference导致一项失败，已补齐；UNITTEST.txt失败原件和UNITTEST_FINAL.txt均保留。曾在本地新worktree初始化发现空索引，未发布的错误提交已纠正，交付分支相对main只有明确新增/修改，无删除历史文件。

未闭合：GU定点系数编译与FP32训练参考舍入等价；新NL独立随机源/全局seed仲裁；本地全宽权重宏；代表性计数、恢复、ROM、64bit转换STA/PPA。完整能耗/面积null；价格小计不可比。DRAM本轮为link，不是新DRAMSys执行；已有bridge接口保留。其他成员#118/#123候选未被替代或自动接入。

发布核对：PR180状态、head及main合并SHA以PUBLICATION/MERGE回执及Issue179为准。只有最终PR核验后才执行合并。Projects缺read:project，PROJECTS_CHECK.json记录实际查询失败，待有权限成员同步。下一位agent先读最新Issue/PR及根备忘录，再改同一统一入口，不再复制出v7。
