# 筛选＋PV 的 K 读取专题交接

- owner：jieruiz；Issue #9；分支 task/9-screen-k-traffic；base pbit-tlm-attention-details-20261016 @9608c0d06cf8b421cbbd348aca4fc84c5990aae7。
- 独立目录：C:/Users/86134/Documents/a_P_BIT/tmp/screen-k-traffic-issue9-20261017/；目标 workspace 仓库，origin 为历史个人仓库，不向其发布。
- 开始前已核验本机真实登录、Git 根/分支/远端、fetch 后远端基线；读取最新 README、TLM 索引、治理 AGENTS、相关 Issue/PR 和本人 STATUS/交接。
- 并行只读协作：k_v_traffic_audit 核对源码与已有计数；sparse_k_methods 读取 NSA/SparQ/Quest/SeerAttention-R 等原始资料。均不改文件、不建立其他 Issue/PR；实现与发布只在本任务工作树。
- 已完成：旧 v3/v5 的 QK 稀疏、GQA union、Link256 burst、摘要、V reload 分解；原选择器重建逐项校验；共享 uniform 理论最小 union 计算；正式中文报告。
- 原始校准输入由 a_P_BIT/architecture_tlm/configs/ 复制原字节，散列匹配历史记录；原发布配置 JSON 值一致但字节散列不同，未重写历史。archived_inputs 局部 -text 属性保留原字节。
- 数据是 SYNTHETIC_GAUSSIAN_LOGITS，不是实测Qwen；未运行数值推理，无模型/分词器/语料的新哈希或 BF16/PPL。新架构质量测试前必须重跑匹配 BF16 并满足语料/模型复现要求。
- 未运行新 DRAMSys、RTL/DC/PT 或远程作业；没有本任务运行中 job。当前没有把理论共享随机数或组共同预算启用到运行时。
- 所有小型源/配置/结果 SHA 见 manifest 和 audit.json；原始大型轨迹/工艺库/权重未上传。
- Projects 看板缺 read:project，待有权限后补同步；Issue/PR正常交付，未把本地完成说成合并。

## 可执行复核

```powershell
cd C:/Users/86134/Documents/a_P_BIT/tmp/screen-k-traffic-issue9-20261017
git remote -v
git status --short
python architecture_tlm/audit_screen_k_traffic.py --output new-screen-k-audit.json
git diff --check workspace/pbit-tlm-attention-details-20261016...HEAD
```

恢复时先读 Issue #9/PR 最新讨论。工具拒绝覆盖输出；新生成 JSON 除机器路径外以记录值为准。下一步先捕获真实同一 decode 实例的全部 Q 头 logits/masks，量化 group overlap 与保留 attention mass；再测试组级共同预算和64B实际DMA，随后再集成筛选与v6 PV。不要把降低PV样本数当作已经降低前面K读取。
