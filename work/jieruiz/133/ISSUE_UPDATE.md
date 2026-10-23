# Issue133 FFN计数器对照交接

负责人jieruiz；分支task/133-counter-rtl；独立目录tmp/counter-rtl-issue133-20261023；base6966739a5223680888bf0315f7bb4f73423a1ae6，PR目标pbit-tlm-attention-details-20261016。

已推送，[PR135](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/135)待审、未合并。

正式实现architecture_tlm/counter_rtl_compare。A逐位/档/符号计数＋末尾有符号恢复；B每拍整数和＋每档累计。SRAM按用户要求全并行外部供权重，内部无额外权重存储，不含随机源/比较器/浮点恢复。本轮未改主TLM或其默认参数。

实际：40组RTL、13408个整数输出逐位通过；A/B帧周期相同；连续T32 PIPE1每帧36周期。6项流程测试、三份Bash语法、8项registry测试通过。RTL源提交6647c56fd305a9ad53c77d75a40841941860a011，实际文件及输入向量SHA见results/RTL_VALIDATION.json与本目录RAW_ARCHIVE.json。模型/数据版本不适用：合成整数激励、seed17；功耗计划seed17/43/101，不是实际LLM活动。

完整64输出Icarus展开600秒超时未完成，最终B64未开始；前序部分/失败尝试保留归档，不能计作完整通过。没有DC/STA/PT/后布局结果，无实际面积或功耗，不能认定B更优。

交付ZIP：C:/Users/86134/Documents/a_P_BIT/sc_counter_compare_20261023.zip；37929 bytes；SHA256 3a9b84019b1e41f51f198601a57fd969c7dbbb4de896b1bd4951221b378c94b5。

下一步：用户解压，按README先运行A/B M1 smoke，再Slurm提交A/B×SS/TT100MHz的M64 T32 PIPE1四项。VCS逐输出golden必须通过后才进PT。回传四个reports包，核验时序、逐bit活动、缺表/超范围，再比较总面积、每帧能量和关键路径。先验逻辑状态差不是PPA差。本机本任务无运行任务，未向远端提交EDA/Slurm。

统一台账counter-ab-133-functional已登记，PPA四项为NOT_RUN；本地镜像只合并本条，保留其他任务已有记录。看板缺少既有read:project权限，待同步；Issue/PR/STATUS交付不等于看板已写入。不合并PR。

验收进度：RTL与同口径流程已交付；工艺PPA待用户运行，任务保持open，PR不自动合并。
