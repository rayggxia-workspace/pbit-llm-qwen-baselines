## 2026-11-25 Issue225：T64组64尺度PPL配对已提交

资源接续最新：BF166299完整PPL11.537160已完成；6300元素0/1/3因其他用户进程占用被分配卡而OOM，5/6同类冲突取消，未启动7…47取消；健康2/4（6304/6306）保留。6309依赖两健康片后，以Slurm分配范围内≥24GiB空闲卡最多2worker接续46片；6310新汇总，旧6301取消。数值b44974f9c44c、模型/语料/原manifest不变，资源包装器独立SHA，失败证据留存。所有新文件仍在原zhj/run-v1/resource_resume_v1；结果用collection显式链接健康片及接续片，不覆盖旧失败目录。学院服务器已可连接，其Issue263旧任务健康，本轮未重复部署。以RESUME_SUBMISSION.json和新HANDOFF为准，不把旧“48分片运行”当当前状态。

后续门禁已通过：GPU6298 completed/311.289秒，原生lane及IID64 no-op均逐位一致，峰值19.229GiB；完整6299和6300首四片已开始。两窗口3071目标seed101，lane16/32=11.662464、group64=20911.713726；lane64/128=9.611378、group64=31.539994。第0窗口仅x共享11.609371、仅g/u共享20814.004247（逐元素9.216181），主要损失在g/u组共享。不是完整WT2。实际T64表已独立核验：x全部指数−6…9，g−4…8，u−5…9；最高档分别0…9、2…8、1…9。正式初筛experiments/t64_group64_scale_20261125/results/SCREEN_ZH.md；封存回执/原表在本交接目录。完整结果仍运行，不重提健康分片。

用户要求固定T64训练100M权重，GU16/Wd32与GU64/Wd128分层，验证x/g/u各连续64共用一档。原四档表、W8、整数归约/恢复、sigmoid量化/LUT和AND直连Wd保持；准确Attention和T64原non_ffn；各预算与逐元素选档同轮三seed配对。前级16/64层各1次，后级4×2×4或8×2×8各格1次；不是全局相同四个绝对尺度。旧Issue206完整14.884为未训练官方FFN，不作本T64成绩。

代码experiments/t64_group64_scale_20261125，source b44974f9c44c22ea238d06b571de4d4d3245a6c0，提交回执b6d4db8f1a8697ae4c12cf0ddf902f924a0aa681已推PR266，未合并。CPU6297六项PASS，GPU6298门禁运行，完整BF16参考6299、数组6300的48分片（四case×三seed×四片）、CPU汇总6301依赖等待；不是已出完整PPL。原GPU服务器已恢复连接，ssh显式-F .ssh/lab-server-ai.ssh_config；新文件均在/home/Hongjie_Zeng/projects/zhj/t64-group64-issue225-20261125/run-v1，原权重/语料只读复用。

源码归档16290B/SHA aba0a2f3dcbe14914558a9bca79b3a1e0fb2c99af7b8019f3b946e79db68b526；manifest fc4305b1992d28a118786d91545c7b4cb0c4c1196362b33ad02972dad5dc0ca8。交接tmp/cim-bank32-tlm-issue225-20261124/work/rayggxia/225/t64_group64_20261125/HANDOFF.md，精确命令SUBMISSION.json。依赖自动启动，无需本机在线；恢复先看sealed gate/full/summary、SHA和36层/逐窗计分覆盖，不重跑健康分片。暂不改TLM尺度字段/默认，不宣称21bit电路或物理PRNG数值验收。
