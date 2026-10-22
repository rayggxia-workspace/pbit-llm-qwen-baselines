# Issue95 随机架构可视化续作

2026-10-22；负责人rayggxia。用户要求把当前架构画成可核对的文件；本次没有修改模型、RTL、默认配置或PPA。

- 交付：architecture_tlm/random_service/architecture-view.html；模板为同目录architecture-view.template.html。
- 用户独立副本：C:/Users/86134/Documents/a_P_BIT/远端上传/rng_architecture_20261022.html。离线可开，四页为架构、逐拍协议、共享与规模、核对清单；导出仅为本地JSON。
- 原实现：970260e21ebcf98822b9cf47b643fb8360a31e2f，PR97已合并27bf9c483e2b772b4fcdb4c988b3d86074c80049。
- 文档发布基线：eb317e4f6fb1b0d8844887401f3275f128ef8a83；目标pbit-tlm-attention-details-20261016；新文档分支task/95-rng-architecture-view。接续Issue95，不新增Issue。
- 工作文件复用tmp/rng-service-issue95-20261022；其本地HEAD仍83e1528及此前API发布保留的46项staged文件。不要把该index当成本次差异，不重置；本次API树只提交明确的可视化文件和个人STATUS追加。

## 来源与边界

时序直接导出Endpoint / SeedIngress，3后端×4场景，372个时钟沿。固定测试材料不是物理熵；12/6拍换种参数只是显示协议，默认仍1亿时钟拍。不是按成功更新次数触发。

共享中层目前是种子调度模型，尚非共享PRNG服务簇或完整分发RTL；GF64与一个随机字共享64比较器不同。PR103另有FFN分层前端，不能把其功能标作原通用RTL已包含。

后续接合证据：architecture_tlm/unified_v6/RNG_COMPATIBILITY_ZH.md，冻结执行36d5e1085e82a982c9e689a467b3b2042ca36f4d。FullDecode默认未全面切换，不继承旧52项结果。

PPA证据：远端上传/rng_service_v1_20261022/architecture_tlm/random_service/POWER_RESULTS_38322118_ZH_20261022.txt，报告SHA256为8c2e65d1f5e8eaecfdcccdeec2742467e9547f808d2b1b9b8f31597efe4477f7。后续v3执行快照、100MHz布局前临时标定，不是原v1源码的自动回填或整机实测；本次无EDA实验。

## 验证和恢复

在仓库根运行 `python work/rayggxia/95/build_architecture_view.py`，导出HTML和ARCHITECTURE_VIEW.json；核对其model_sha256及source_commit。构建脚本的用户副本位置按本工作区布局生成。

本机使用bundled Python / Node、Playwright及无头Edge运行 `node work/rayggxia/95/check_architecture_view.cjs`；脚本内Playwright路径为本机依赖路径。12时序场景、11模块、计算器/错误输入/核对导出检查通过；1440/768/390宽度无横向溢出，无JS错误，亮暗模式截图已检视。回执VISUAL_CHECK.json。截图与测试导出在visual_check/，不是用户确认，不发布。

验收待用户阅读架构图和PR评审；不关闭Issue。Projects看板权限/同步未核实。维护备忘录入口拟追加见MEMORY_VISUALIZATION_APPEND_ZH.md，避免覆盖其他任务正在维护的唯一备忘录。
