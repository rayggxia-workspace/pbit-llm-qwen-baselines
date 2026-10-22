# 固定 f94c9db 的公开合成 GQA 执行

本轮原样运行固定 `f94c9db` 生产模块。输入由 `run_gqa.synthetic_gqa(7)` 生成，7 query/1 KV，D16/Dv12，12物理token、每head4或5个候选。K/V slot、operand slot、memory window 均为1；采样模式每head保留4个样本，使用明确的每head native源实例、seed=0+head。

| 模式 | 时间 ns | 操作数 | K物理union | V物理union |
|---|---:|---:|---:|---:|
| exact | 5810 | 220 | 6 | 6 |
| systematic PV | 10400 | 352 | 6 | 6 |
| winner | 15050 | 439 | 6 | 6 |
| corrected rejection | 15500 | 617 | 6 | 5 |

四例均通过 cycle/event 全 payload与全部head状态比较、实际输出写回字节、独立head数值/轨迹oracle、共享物理读计数、row/operand/metadata信用恢复与消费者生命周期门。执行前20项生产/旧query测试通过。具体source/fixture SHA、配置、结果、完整gzip trace和HTML在各case内，`MANIFEST.json`逐项保存成果散列。

这是公开合成协议/数值接合回归，不是真实模型fixture、PPL、全层、STA或物理PPA。真实Qwen 7query/1KV fixture保留在服务器，由独立CPU-only作业执行，只回传白名单报告；不能与本目录混称。

复现：从仓库根运行 `PYTHONPATH=<repository> python -X utf8 -P work/amlink1219/116/gqa_validation/replay_synthetic.py --out /new/results`。新目录拒绝覆盖，具体源版本由各case START/summary记录。

`event_only_receipt.json` 是另一次两head exact小例的公开回执，实际使用待提交event-only runner，源码字节已由其source_sha256记录，随后该代码固定为d390407。其`checked=false/equal=null`验证显式跳过双模式时不会冒称比较通过；该例不并入上述四例双模式数量。
