# amlink1219 项目进度

更新时间：2026-10-19T00:58:24.860054+08:00；负责人amlink1219。正式目标rayggxia-workspace/pbit-llm-qwen-baselines；本地工作目录 `E:/BaiduSyncdisk/p-bit/DAC_2026_Draft_Proceedings/DAC_2026_Draft_Proceedings/workspace_projects/pbit-attention-issue35`，分支task/35-attention-e01，PR base pbit-tlm-attention-details-20261016 @3553996。

## Issue35：Attention E0/E1 实际执行

- 代码执行源879050031ac1cc7757e3b7f54e19c25dc40faf72；Slurm2159漏fixture失败保留，2160 CPU39/39通过，2161完整BF16 PPL11.652735047455899/299077目标与原值相等，真实QK/V捕获无扰。2162 pilot12/12、2163 full465/465均完成0:0，无错误或超时；当前无本任务运行作业。
- 正式代码experiments/attention_e01；结果qwen/results/attention_e01_20261019；本人辅助/交接work/amlink1219/35；服务器/home/Weican_Chen/projects/attention-e01-issue35。大trace与每case数组留该目录，仅回收小型记录和SHA。
- 本轮数值结果：当前三个真实行的M2048/S128，数字systematic的V NMSE均值均低于串行Ising；有限输入/seed，不是全模型PPL或器件优势证明。无RTL/PT/TLM或物理随机源验证。
- 本地完成、服务器实际完成、本人Issue35结果摘要已同步并回读；push=false、triage=false，分支未上传、PR未创建，Projects待同步。不得冒称远端代码已交付/已合并。下一步在获得权限后核对最新Issue/PR和base，显式推本任务分支并建PR，回读提交/结果SHA。

## Issue33：此前计划

- 调研与623行总计划在独立工作目录pbit-attention-issue33、提交e1e564d；尚未推送。Issue35仅实现并执行其中有限E0/E1范围，不代表整个计划完成。保留该任务原进度/交接，不覆盖它的分支。
