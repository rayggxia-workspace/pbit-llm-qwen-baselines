# rayggxia — Issue95 概率输出端表征

2026-10-27，连接器身份rayggxia。接续Issue95；分支task/95-pbit8-characterization，base main d83eeb1fc6b89a3dff51b5b62bf79acf665c7166；独立目录tmp/rng-pbit8-issue95-20261027。旧PR188质量研究和其他成员PPA工作保持。

本地完成：已有38322118四种端点100MHz连续窗口三seed复核；旧独立比较器P=12源SHA核验；新增五个8位概率输出端RTL、256x9 sigmoid表、穷举/三seed活动、DC/PT模板及说明。没有新许可EDA/PPA/模型实验。

验证：131072个比较输入，256个表项与80位Decimal及现有TLM一致；65536个LUT×r概率计数；75案例307200计量拍通过。Tcl四项stub解析通过，不代表EDA语义验证。原件本机归档2,764,042B，SHA见work/rayggxia/95/pbit8/RAW_INDEX.json。中央台账74记录check/render通过，其他73记录保持。

main尚未包含整个中央台账工具，本PR仅提交自身record；本机完整联合台账完成check/render。合入台账维护分支时保留其余记录并重新render，不提交一份只含本任务的总览替代全局结果。

源码与便携包完成；发布回执以work/rayggxia/95/pbit8/PUBLICATION.json为准，无回执不得称已发布。下一步用户按README在工艺库下测独立核；STA/功率/面积均未测，不能更新为TLM校准值。Projects待有权限维护者同步。完整交接见同目录HANDOFF.md。
