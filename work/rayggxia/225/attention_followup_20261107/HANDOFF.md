# Attention后续交接文档任务

负责人rayggxia，Issue225/PR248，分支task/225-norm-stream-20261106，沿已有独立工作树。仅编辑本人文档，198和249只读。当前本地文件已完成，远端以PUBLICATION回执为准。

用户要求查看Attention最新改动、整理文件给其他对话。已核PR199 head4ed760ffd3742add846d211900e9e866e2039418、PR248的100MHz六核默认、PR249早期整机快照。正式文档architecture_tlm/module_handoff/ATTENTION_NEXT_ACTIONS_FOR_AGENT_ZH_20261107.md，根镜像同字节。

已完成内容明确复用：250 v2返回wake4ns和同宏TT SRAM单价、有限QK/PV与原生模块回放；256三seed586.136us/378.57uJ/13.61588mm²，含共享池+672KiB SRAM的首层至O范围，非整token。下一步只列三项：普通投影按MAC消费节拍的有限FIFO/信用、返回写/计算读仲裁、宽分数max差值→8位LUT/P8前端宏事件/合同。48KiB/组与PV64/128均后续可选，不作为新前置门槛，不重做Ising/训练/全片RTL。

宿主接合差距有源码证据：PR249/root250 bootstrap仍bind早期attention_unified250_20261107 vendor；unified_clock只改mem/request/common，不含v2 ingress wake；计价也仍旧SS。整机对话需新快照接v2/TT计价并逐tick验证，旧健康任务不改/不重交。100MHz6核/16-32/640FMA/PV128/归约32与250的256/64/4采样/16归约分隔，不套TT价或直接改100资源。

本轮只读审阅和文档/索引，无新服务器/GPU/native/RTL/PT/PPL、无新数字台账run，不修改198/249源码或100/250默认。来源记录源文件SHA与公开blobSHA、两默认隔离检查；任务辅助work/rayggxia/225/attention_followup_20261107。文档发布以PUBLICATION为准，PR248待审不合并，Projects待维护者同步。

---


正文是给其他对话直接执行的说明，不代表已执行三项优化。来源固定到PR1994ed760f与PR249608d021。sources/VALIDATION给默认隔离、公开blob原字节检查，代码不修改，不新增RTL run。恢复先核最新PR199/248/249及各owner交接；若源更新，补新版本说明，保留旧快照记录，不将v1原生结果改成v2成绩。

下一步由用户转发正式Markdown给Attention/宿主对话，按文内分工推进。本人没有代发聊天、没有提交或取消远端作业；PR不自动合并，Projects无写接口待维护者同步。
