# Issue78 全局广播与伪异步更新

2026-10-21；jieruiz；task/78-ising-broadcast；base e4990c15b40f664cea7f9db43175b68347ce588b；目标rayggxia-workspace/pbit-llm-qwen-baselines。

独立稀疏目录：C:/Users/86134/Documents/a_P_BIT/tmp/ising-broadcast-issue78-20261021。已读根记忆0/1/7/12、远端README/AGENTS/两位成员STATUS、Issue37及最新open任务；Issue76为其他成员训练设计，保持分离。原Issue73作业2585仍运行，不取消或重交。

已完成：有限κ方程、全同步/随机分块/稀疏使能NumPy行为模型、合法输出等待、无兜底cap；6项CPU数学/转移/边界测试通过。平坦输入发现全同步2周期振荡；原固定spacing4会只读空状态，故新路线增加独立随机间隔读出，并保留逐阶段非法率。

尚未完成：远端合成诊断与模型CPU PPL、任务分支推送/PR；不得把本地脚本写成已执行结果。计划个人服务器项目`/home/Hongjie_Zeng/projects/pbit-qwen-ising-broadcast-20261021-issue78`，独立不可变snapshot；只读复用既有权重/数据/标定，不复制模型。

准备按Slurm提交CPU诊断、CPU BF16/SDPA门禁和afterok的18配置PPL数组。128目标固定后缀只做初筛，所有24层scored decode替换，原FFN和多token前缀准确；不等于完整WT2。

下一步：封存执行SHA与source包；提交后在本文件追加真实job ID、路径、哈希。核对JSON终态，失败保留null PPL，不用分布指标估造PPL。至少3seed记录，κ选择区分平衡泄漏与动态偏差。Projects历史缺read:project，待有权限后同步；Issue78保持open至PR验收。
