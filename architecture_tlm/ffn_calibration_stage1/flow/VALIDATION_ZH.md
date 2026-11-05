# Issue193 流程脚本本地验证

验证范围仅限 `flow/` 的控制、解析和封装逻辑。没有运行 DC、VCS 或 PT，没有向 Slurm 提交作业，没有工艺面积、slack 或功耗结果。测试中出现的面积、PVT 和 slack 都是显式合成 fixture。

实际执行：

```text
python -B flow/test_flow.py --tmp-root C:/Users/86134/AppData/Local/Temp/pbit_issue193_flow_tests
29 tests, OK, 0 skipped
```

包含 Python 报告解析、功能源码 SHA 门禁、独立快照、超时回执、回传包排除库和网表、Slurm 仅准备路径、环境文件变化后的失败回执，以及真实 Tcl 解释器中的语法完整性和 PVT 表格/命名块解析。明确检查同步复位没有 false-path 或 multicycle 例外。

额外执行：

- Git Bash 对 `run_case.sh`、`submit_smoke.sh`、`submit_all.sh`、`env.sh.example` 分别执行 `bash -n`，均通过。
- 全部五个 Python 文件 `ast.parse` 通过。
- 所有新文件检查为 UTF-8/LF，没有 CRLF；库条件解析器保持原文件字节和记录 SHA。

首个远端 smoke 仍需验证：服务器真实 VCS/DC 版本、库 `report_lib` 的格式与单位、Synopsys 命令兼容性、实际综合运行时间和时序。不把 Tcl 的 `info complete` 当作许可工具已执行。工具格式不匹配时保留失败证据，不能改成默认通过。
