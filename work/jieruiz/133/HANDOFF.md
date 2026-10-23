# Issue133 FFN计数器对照交接

## PPA v2续接（2026-10-23）

沿用本Issue/分支；开工已核验jieruiz、PR135 open/head7f38018与本地一致。
RTL/TB未改。修正VCD校验位宽被末尾声明覆盖的问题，新增SHA冻结提交、
4项M1 smoke、数值功耗/面积/每完成帧能量汇总、单元互斥分类和失败回传。
本机及新包解压9单测通过；Bash语法、Python3.6 AST、Tcl完整性通过。
新增小RTL A/B共64输出及4个活动/空闲窗口，逐窗口90个输出/时钟bit通过。
完整M64未重跑，无DC/VCS/PT新结果。旧功能/失败结果保留。
包sc_counter_ppa100_20261023_v2.zip（含全部RTL/TB），运行入口RUN_PPA_ZH.txt；
SHA、验证归档、实际发布状态见PPA_V2_DELIVERY.json及后续回执。
先Slurm提交smoke，回传4包确认后才提交all；不自动依赖提交以免失败悬挂。
统一台账原record补充v2，不制造新的已测PPA；看板权限待同步。
本段本地完成，是否已推送以回执为准；下方已推送描述是此前v1。

实际回执：013859d/7753168本地提交；HTTPS push因low-speed超时失败。
PR135远端已回读仍7f38018，open未合并；Issue评论6362207999已同步阻塞。
最终包47271B，SHA84169483a9175f7a12a1a5c5540c237fe85d501826b793b1da300ea56d7aad7f。
新manifest为UTF-8 LF；最终包31文件校验与解压后9测试通过。网络恢复后推送本分支。

负责人jieruiz；分支task/133-counter-rtl；独立目录tmp/counter-rtl-issue133-20261023；base6966739a5223680888bf0315f7bb4f73423a1ae6，PR目标pbit-tlm-attention-details-20261016。

已推送，[PR135](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/135)待审、未合并。

正式实现architecture_tlm/counter_rtl_compare。A逐位/档/符号计数＋末尾有符号恢复；B每拍整数和＋每档累计。SRAM按用户要求全并行外部供权重，内部无额外权重存储，不含随机源/比较器/浮点恢复。本轮未改主TLM或其默认参数。

实际：40组RTL、13408个整数输出逐位通过；A/B帧周期相同；连续T32 PIPE1每帧36周期。6项流程测试、三份Bash语法、8项registry测试通过。RTL源提交6647c56fd305a9ad53c77d75a40841941860a011，实际文件及输入向量SHA见results/RTL_VALIDATION.json与本目录RAW_ARCHIVE.json。模型/数据版本不适用：合成整数激励、seed17；功耗计划seed17/43/101，不是实际LLM活动。

完整64输出Icarus展开600秒超时未完成，最终B64未开始；前序部分/失败尝试保留归档，不能计作完整通过。没有DC/STA/PT/后布局结果，无实际面积或功耗，不能认定B更优。

交付ZIP：C:/Users/86134/Documents/a_P_BIT/sc_counter_compare_20261023.zip；37929 bytes；SHA256 3a9b84019b1e41f51f198601a57fd969c7dbbb4de896b1bd4951221b378c94b5。

下一步：用户解压，按README先运行A/B M1 smoke，再Slurm提交A/B×SS/TT100MHz的M64 T32 PIPE1四项。VCS逐输出golden必须通过后才进PT。回传四个reports包，核验时序、逐bit活动、缺表/超范围，再比较总面积、每帧能量和关键路径。先验逻辑状态差不是PPA差。本机本任务无运行任务，未向远端提交EDA/Slurm。

统一台账counter-ab-133-functional已登记，PPA四项为NOT_RUN；本地镜像只合并本条，保留其他任务已有记录。看板缺少既有read:project权限，待同步；Issue/PR/STATUS交付不等于看板已写入。不合并PR。

远端核验：b1c1999584b4c74433b02b80bd4bd2bfdd6d37cc的7关键文件原字节一致，见REMOTE_VERIFY.json；Issue评论回执见ISSUE_RECEIPT.json。最终科学包未变。辅助脚本finalize.py/metadata.py/remote.py、validation_*目录和候选源仅本地保留，未上传；所需原始日志/向量已SHA归档，交付包自带可复现生成/验证代码。已回收本任务53个可重建vvp中间文件640147114字节，记录REMOVED_REBUILDABLE_VVP.json。
