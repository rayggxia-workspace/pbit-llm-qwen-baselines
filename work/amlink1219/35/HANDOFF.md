# 本轮补传状态（2026-10-19）

权限已恢复，当前为发布准备阶段；尚未推送/创建PR。实时状态以PUBLICATION.json及本人STATUS为准。以下交接保留原执行时点；其中无push权限/未发布描述仅指原时点。原manifest应按原交付提交验证。

# Issue35 可继续执行的交接

更新时间2026-10-19T00:58:24.860054+08:00；负责人amlink1219。目标rayggxia-workspace/pbit-llm-qwen-baselines，分支task/35-attention-e01，本地目录`E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/workspace_projects/pbit-attention-issue35`；base3553996。执行快照879050031ac1cc7757e3b7f54e19c25dc40faf72；不要修改服务器已执行快照。最终本地发布提交由Git日志/外部delivery_receipt标识，避免自引用。

已完成：模型/数据8SHA；原始tokenizer/profile及完整tokenIDs身份；CPU2160 39/39；GPU2161完整BF16 PPL11.652735047455899、299077目标和真实prefill-lastquery QK/V无扰；CPU2162 pilot12/12、2163 full465/465。均COMPLETED/0:0，首个终态已保存在本目录terminal文件。早期2159因测试config遗漏FAILED/1:0，原快照5525511保留；未将失败结果冒充模型结果。

执行入口experiments/attention_e01/run.py与run.sbatch；完整配置/输入/源manifest、命令和环境见qwen/results/attention_e01_20261019/raw。逐案例caseID和采样指标完整，原始NPZ留个人服务器/home/Weican_Chen/projects/attention-e01-issue35/outputs；stage_summary含位置/大小/SHA，回收归档及小文件逐SHA核验通过。登录节点仅轻量检查/编辑/传输，CPU与GPU计算均Slurm；CPU隐藏GPU。没有当前运行作业，不重交旧作业。

完整协议、三输出契约、M/S/seed/profile、有限链限制见实验README和正式RESULTS。真实行只覆盖固定一个2048token窗口的三个layer/head，小M前缀分布不是QK筛选；没有完整随机Attention PPL、物理RNG、RTL/PT或PPA。S<=512不足ESS，后续E1c与更广真实覆盖尚未执行。

远端代码交付未完成：amlink1219当前push=false/triage=false；Issue35可更新，Projects待权限。无需更换账号/旧库，无PR创建或分支推送。权限恢复后先核身份、remote/pushurl、最新Issue/PR/分支；按explicit文件范围push task/35-attention-e01并PR至确认base，回读并更新Issue。Issue保持open直到PR验收；Issue33计划仍在另一工作树，不接管FFN Issue32/PR34。

本机辅助控制与恢复回执在 `E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/outputs/pbit_attention_e01_20261019`，包括server_control.py、stage/submit intent与receipt、源snapshot tar及失败记录。它们含本机SSH入口引用，未作为业务代码上传；不输出凭据。恢复先读实际job receipt和terminal，网络模糊失败不得重放提交。服务器原始下载manifest在本目录original_model_download_identity.json；原始版tokenizer和prior-server另存版不可混写。

Issue35实际结果摘要已通过本人账号更新并回读一致；远端协作回执REMOTE_SYNC.json。Projects本次只读查询返回INSUFFICIENT_SCOPES，缺read:project；未改权限或看板。代码/完整报告仍未推送，无PR。结果内容提交9d0b80f，后续状态回执提交由Git日志标识。
