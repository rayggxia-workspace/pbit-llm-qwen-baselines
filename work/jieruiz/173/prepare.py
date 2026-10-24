from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parents[3]
for p in (ROOT/'qwen3/and_direct').glob('*'):
    if p.is_file():
        s=p.read_text(encoding='utf-8').replace('\r\n','\n')
        if p.suffix=='.py':ast.parse(s)
        p.write_bytes(s.encode())
entry='''## Issue173：有限三流AND直连Wd（2026-10-24）

负责人jieruiz；branch task/173-and-direct-wd；base PR172@38de0796，依赖task/171-nonlinear-width。独立目录tmp/qwen3-and-direct-issue173-20261024。用户授权模拟非线性随机流直接进入固定W8，在输出端累加；无z重编码。A8+符号/signed8 sigmoid驱动/P8+true-one；独立三流，事件跨Wd输出共享，定点恢复系数16位，输出signed52与整数RNE BF16。gate/up恢复仍FP32参考，不是全链bittrue。

本地9项功能通过，CUDA1项待Slurm；fixed_scale runner因本机缺transformers未运行，服务器必须通过后才启动PPL。计划8段×128目标后缀、全36层，BF16及旧路径/条件均值控制，T64/256/1024/4096各3seed。源码与SHA冻结后Slurm提交，当前未提交。无训练/RTL/PPA，无看板同步权限核验；发布回执待补，不能写成远端完成。

'''
p=ROOT/'progress/jieruiz/STATUS.md';p.write_bytes((entry+p.read_text(encoding='utf-8')).encode())
(ROOT/'work/jieruiz/173/HANDOFF.md').write_bytes((entry+'''下一步：提交冻结源码，运行package.py，上传只读快照到/home/Hongjie_Zeng/projects/pbit-qwen3-and-direct-20261024-issue173，sbatch五分片。源不可改；失败另快照。结果核验complete.json documents及sidecar SHA、36层覆盖、三seed、同轮BF16后形成报告；分支PR base为task/171-nonlinear-width，不合并。原输入模型/校准直接复用只读路径，配置包含全部SHA。
''').encode())
print('Prepared LF source, parsed Python, STATUS/HANDOFF')
