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
