# rayggxia 当前任务

更新时间2026-10-22；GitHub连接器实际账号rayggxia。Issue95：随机源操作模型与核心RTL。
分支task/95-rng-service-rtl；PR base pbit-tlm-attention-details-20261016@83e15289434af50fc09c35e699d8b39965389d98。
工作目录C:/Users/86134/Documents/a_P_BIT/tmp/rng-service-issue95-20261022。

本地实现、验证和用户交付包已完成；已发布PR97 https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/97 ，开放待审、未合并。源提交970260e21ebcf98822b9cf47b643fb8360a31e2f；最终元数据head见远端分支。实际账号rayggxia经连接器发布，Git原生直连fetch连接失败的本地状态见PUBLICATION.json，不能因此把已发布说成未发布。
成果architecture_tlm/random_service/；原Attention增加可选计时源接口，保持旧默认。3种后端、外部种子传输与缓慢重播种、操作统计、核心SV、测试平台与功耗仿真说明。
验证47项Python通过；14100沿三后端Python/RTL对照、FFN250沿/120帧通过；便携包19项检查与示例通过。入口work/rayggxia/95/VALIDATION.json、RTL_VALIDATION.json、ACTIVITY_VALIDATION.json、DELIVERY.json；硬件PPA留给用户，本轮未运行DC/PT/模型/GPU/Slurm。
疑点DESIGN_QUESTIONS_ZH.md；下一步用户按POWER_SIM_ZH.md仿真工艺PPA并评审；恢复时先确认远端head/树SHA，再继续同一目录。Projects待同步。完整交付包远端上传/rng_service_v1_20261022.zip及同名目录；原始运行按RAW_ARCHIVE.json归档。
完整交接work/rayggxia/95/HANDOFF.md。
