# BF16成熟算术与N64本工艺结果

最新入口：[结果与口径](results/REPORT_ZH.md)、[完整数值与原件索引](results/FINAL_SUMMARY.json)、[INT8经典划分](INT8_CLASSIC_ZH.md)。

CVFPU与common_cells精确提交及许可见UPSTREAM.json、vendor/；两处DC2018等价兼容改动见COMPATIBILITY_PATCHES.json。冻结执行manifest保留原字节。fixtures由prepare.py、work/rayggxia/204/bf16_ppa/prepare_matrix.py生成并存在源ZIP；重新生成后必须重施记录的兼容补丁，不能把原冻结目录当可变实验目录。

本轮为前布局综合/门级/PT及单独复位契约STA，不是布局签核或芯片实测；未运行模型推理/PPL。
