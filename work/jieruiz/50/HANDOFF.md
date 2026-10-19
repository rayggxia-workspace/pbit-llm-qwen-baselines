# Issue50：三种短流FFN接入实际Attention，准备阶段

2026-10-19，负责人jieruiz；Issue50，task/50-joint-ffn-attention，依赖PR47@5518a0a与PR49执行源11f1d6ee；工作目录tmp/qwen-joint-issue50-20261019，PR base为task/46-fixedw-multiscale。只读导入上游实际max4筛选＋有限CTMC＋V gather源码，moment.pt运行制品不重复上传，来源/SHA见UPSTREAM_MANIFEST。Attention成员Issue48/Slurm2380保持，不访问其个人目录。当前无新模型结果；下一步CPU/GPU门禁、每目标24层联合调用审计、同协议后缀三seed与有依据的完整cached确认。Projects缺read:project待同步。