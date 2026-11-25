2026-11-25最终：原GPU本人队列已空；原四档完整48/48分片和12/12配置/seed、6316补跑/6317汇总均sealed完成。逐元素GU16/Wd32完整PPL均值10.753594，GU64/Wd128 8.975547；旧组64四档分别22125.753736/28.551581。动态64/32/16的10项8窗初筛亦全完成。学院Issue263仍34/52逻辑分片，完整WT2七项齐，coarse32/fine128三seed均值9.446296/9.406494，任务仅coarse32 PIQA齐，主池62220保留运行、62221等待。总览experiments/t64_dynamic_scale_20261125/ALL_SUBMITTED_RESULTS_ZH.md。

最新2026-11-25 16:01：原GPU可登录；23/48分片封存SHA、逐窗目标SHA、36层覆盖核验；完整5/12配置。lane16/32 seed101/202 PPL10.758346/10.749732；group64原四档16/32三seed PPL22080.554872/21999.098386/22297.607950。lane303 shard2 CUDA超时，仅补该片6316 afterany6309；6317新汇总，旧6310取消；6309健康任务保留。64/128未完成。小结果392758B/416成员已本地保全，归档SHA89de5e55655050808c1e80b9a8310ca2351a4a77c8a3ae871857566c2d650d72。新动态PoT EDA1871089仍Priority排队、未跑PPL。下一步读single_retry_v2/collection/SUMMARY.json与全部sealed结果，不重跑健康片。详见FULL_WT2_PROGRESS_ZH.md和SINGLE_RETRY_SUBMISSION.json。

Latest launch verified: original shards6304/6306 completed (73 windows each); continuation6309 RUNNING on assigned GPUs0/6 only, each >32100MiB free at selection. Collector6310 pending. Numerical snapshot and prior completed reference unchanged. See resource_resume_v1/RESOURCE.json and RECEIPT_*.json; final collection/SUMMARY.json only after all46 retries complete.

# T64组共享尺度PPL交接

资源接续（最新优先）：BF166299完整完成PPL11.537160。原6300_0/1/3资源OOM；5/6确认被占满后取消；7…47仍未启动即取消；保留健康2/4（实际6304/6306），不重跑。原依赖父数组的6301取消。新6309（afterok:6304:6306，Slurm请求5卡，仅使用分配范围内空闲≥24GiB的卡，最多2worker）接续其余46片；6310 afterok:6309组合原健康片与新片并调用冻结runner汇总。RESUME_SUBMISSION.json含精确命令、resource_resume.py SHA和各类状态。新目录resource_resume_v1，collection索引与结果均留该目录；不要等待旧6301或将旧3次OOM写成算法失败。原数值source/manifest均不变；只新增资源包装器，不覆盖已提交快照。学院GPU也可连接，但Issue263已有健康任务，本轮不重复其部署或评测。

更新：GPU6298已completed，311.289秒，两项原生无操作逐位检查通过；6299及6300首四片已运行。新两窗口初筛、消融和实际T64表范围见experiments/t64_group64_scale_20261125/results/SCREEN_ZH.md。3071目标的组64两档PPL20911.71/31.54，不是完整WT2；完整结果未出。封存RESULT及SCALE_TABLES的SHA已本地核验。下方提交时快照保留。

2026-11-25，rayggxia。Issue225 / PR266；原task/225-cim-bank32-20261124和独立工作目录复用。

用户要求同一T64训练权重验证每64共享尺度，GU16/Wd32和GU64/Wd128，采用随预算细化的分层。正式代码experiments/t64_group64_scale_20261125/，源码提交b44974f9c44c22ea238d06b571de4d4d3245a6c0。未改其他owner冻结源码/原始PPL/TLM默认。

尺度：x/g/u分别每连续64项共用最小覆盖档；保留T64各组四档原表，不是全局同四个绝对值。逐元素选档为同预算配对。前级16/64层，每层1次；后级4×2×4或8×2×8，每联合格1次。三流AND直接作为Wd事件，没有重新统计再编码。sigmoid仍为原生true-scale P8 g恢复到S8Q3后查冻结P8 LUT；不使用浮点精确SiLU。准确Attention，T64原配套non_ffn保持，无重新训练/校准。

Slurm新任务：CPU6297（6项通过，0.046秒测试）；GPU门禁6298运行；BF16完整参考6299、12配置的四分片数组6300_0…47、汇总6301均afterok等待。48分片不是48独立配置；三seed12组完整WT2292窗/299077目标。数组并发上限4，另一个BF16独立参考；其他用户已有3张卡运行。只能从封存completed RESULT/SHA与逐窗位置/36层覆盖核验后认定完整。

服务器root=/home/Hongjie_Zeng/projects/zhj/t64-group64-issue225-20261125/run-v1；source=source-b44974f9c44c。全部新文件在zhj。模型/数据复用授权只读既有存储，INPUTS.json为原身份清单同字节副本。不需要本机保持在线。

SOURCE-b44974f9c44c.tar.gz为16290字节，SHA aba0a2f3dcbe14914558a9bca79b3a1e0fb2c99af7b8019f3b946e79db68b526；EXECUTION_MANIFEST SHA fc4305b1992d28a118786d91545c7b4cb0c4c1196362b33ad02972dad5dc0ca8。SUBMISSION.json含精确命令/全部ID，SETTINGS及其SHA保留。只读复用runtime SOURCE_MANIFEST SHA eb23a172efbd18e3e56060a6b10d2bfcde33fc7a014c5b10949038921ffb9076，逐文件在进程中核验。

下一步：读取outputs/gate/RESULT.json和SCALE_TABLES.json的实际T64指数范围/预估吞吐；门禁失败应保留run-v1并新快照修复，不编辑已提交源码，不重跑健康分片。门禁通过后依赖自动执行，未结束时不能写已有完整PPL。汇总outputs/SUMMARY.json会检查同轮BF16、各shard身份及目标连续覆盖，不混入旧Issue206未训练权重成绩。当前未完成新PPL，无新电路PPA；Projects无写入工具待维护者同步。
