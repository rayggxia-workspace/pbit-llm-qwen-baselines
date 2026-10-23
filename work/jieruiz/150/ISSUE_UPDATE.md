固定四档内核和评测协议已实现，原始执行快照49bc6bd1356413585c99dad6513d25cc34cff090。CPU2840已完成；prepare2841正在运行原BF16复测、TRAIN校准与六候选选择；full数组2842_0-19最多2GPU，afterok等待prepare。输出为个人服务器 `/home/Hongjie_Zeng/projects/pbit-qwen-static-multiscale-20261023-issue150/outputs/49bc6bd1356413585c99dad6513d25cc34cff090/`。

原始attention保留。档间比2/4/8，各0/1bit余量；校准和选优只读TRAIN，先冻结SELECTED再holdout/test。当前无新PPL结论，不覆盖旧Issue46结果。执行回执和源码/模型/语料SHA随任务PR发布；未合并，不关闭Issue。看板权限/同步另行核实。
