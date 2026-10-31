# Issue222交接（2026-10-31，推理已完成）

负责人rayggxia；目标rayggxia-workspace/pbit-llm-qwen-baselines，task/222-sparq-sampling-budget / PR223；base main7d42c7d3。复用独立稀疏目录tmp/sparq-sampling-budget-issue222-20261031；本地133b45a1与API远端8c0748c2执行科学源历史不同，不force/reset。

Slurm3554/3555_[0–2]已完成。不要重交。远端个人root /home/Hongjie_Zeng/projects/pbit-sparq-budget-20261031-issue222，冻结source-8c0748c2a130及results/8c0748c2a130；runtime SHA c20dfbe48b64f144f4b5096afbda83fba70a960b009372bdb8cbf9bd724b4df8。旧Issue198源只读不改。

正式结果qwen3/results/sparq_budget_probe_20261031/REPORT_ZH.md、SUMMARY.json、RESULTS.csv、ARTIFACT_INDEX.json、validate_results.py；原小包本地project_archives/sparq_budget_issue222_20261031/，服务器同root/results-8c0748c2a130.tar.gz，SHA d8bec56cafd920f02e6223b03208974711bc3e52f15b1a6de475a77b10f9ba4e。python validate_results.py --archive FILE --output TEMP，41封存/25主结果/36层/512目标/NLL/身份复核通过。没有新增完整WT2、训练或PPA。

建议K128及S32/64/128，S128基线；K256作为长上下文/质量敏感性检查。S8/16无训练退化大；S64相比准确SparQ仍+7.21%。需记录512目标短流范围，不覆盖历史完整WT2。P8阈值和赢家状态规则均实际执行，独立Philox不等于真实全局共享硬件。

下一步：在Issue220交接给训练Agent有版本的预算建议；不自动启动训练。原十组历史不抹去，不把不同S当只改变筛选的配对。CR/Gibbs本次未测；N_CR128的P8数值门禁仍未解决。恢复先读Issue222/PR223/220/221及最新STATUS，不接管别人的作业或修改冻结快照。PR待审不关闭Issue；Projects当前无写入工具待维护者同步。
