## 2026-11-28｜通用模块合同与FP24数值接口

Issue225/PR266，rayggxia，task/225-cim-bank32-20261124。正式入口[模块合同](architecture_tlm/module_contracts/README_ZH.md)，[数值合同](architecture_tlm/module_contracts/FP24_ZH.md)。用户确定中间数值接口采用FP24 E8/M15；局部23bit计数、W8、P8码/符号/尺度、事件与地址继续保留各自格式。任务描述采用形状/模式、存储引用、全局K范围、init/continue/final、状态所有权、采样/RNG与依赖，不是已综合指令字。

核对本地20261128五核FFN/单层Decoder：FP24共享状态12×128项＝4.5KiB payload；sigmoid沿P8重建g→S8/F3→原P8 LUT；三AND直连Wd。旧prefill仍21bit/64bit，旧model_rtl_services与主TLM未自动切换。本轮不改上游RTL或冻结实验，未跑新RTL/STA/PPA/PPL/GPU/Slurm。20项描述符合同检查通过，包括跨命令状态保留、拒绝隐藏FP32、错误尺度、K重叠、缺提交依赖及提前重用状态。

优先下一步：prefill替换为23bit/FP24并适配init/continue/final与四beat捕获；数字/Attention桥接保留native_math而非假定FP24运算；补underflow收集及BF16舍入溢出；用实际状态组织/转换worker价格回填TLM。未知周期/II/PPA在contract.json为null，不继承旧64bit价格。PR待审，不合并；Projects未操作，Issue28远端备忘录待原维护流程同步。

### 恢复与验收

- 任务checkout：C:/Users/86134/Documents/a_P_BIT/tmp/cim-bank32-tlm-issue225-20261124；本地Git HEAD仍9da829cfb084b757fec9b3b0b52c68f2e6b3ffc8，发布基线670d2ea2b17b0da6ee0f194f88c7f1a2b79a360d，API发布后以PUBLICATION.json为准。既有脏文件保留。
- 运行：`python -B architecture_tlm/module_contracts/validate.py --self-test --output architecture_tlm/module_contracts/results/VALIDATION.json`，20项PASS；仅字段与执行计划一致性，不是RTL数值/PPA复验，不新增虚构电路台账run。
- 当前合同和示例可独立检查，无GPU或工艺库依赖。上游RTL来源只读、未随本次发布复制，其绝对位置与字节SHA见SOURCE_BINDINGS。
- 当前数字矩阵仍依模块原生数制，FP24公共接口需要显式桥接。ReLU/GELU/GeGLU等属于扩展模式，不写成已支持。
- 当前示例验证器有意只接收K64整块；尾块必须新增lane mask及最大值排除规则。M与K范围是目标记录，不证明旧RTL命令字段已扩宽。
- 下一步先完成prefill适配与一层真实数据依赖回放，再更新主TLM；不要把本合同当已经完成整机替换。
- 无新远端作业。发布仅PUBLICATION_INDEX内文件；不推旧origin，不合并PR。Projects未同步，Issue28远端备忘录按原流程待同步。
