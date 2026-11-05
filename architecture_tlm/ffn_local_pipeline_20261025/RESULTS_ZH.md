# 封存结果自动汇总

单位：ms；合成事务时序，无模型精度或实测芯片性能含义。

## 完整36层decode（含词表输出层）

| 方案 | 整机/token | FFN总计 | Attention core | QKV/O投影 | 词表输出 |
|---|---:|---:|---:|---:|---:|
| full_old | 407.1426 | 268.5761 | 22.5782 | 81.4697 | 34.0448 |
| full_dual_shared | 315.2362 | 176.6803 | 22.5681 | 81.4713 | 34.0453 |
| full_dual_bypass | 307.0491 | 168.4882 | 22.5723 | 81.4733 | 34.0448 |

## 单层因果扫描

下列只比较FFN相位；不把单层总时间当完整模型时间。非FFN算子不随FFN新调度改变；SRAM翻倍实验会同时影响其他算子，所以不能拿其整机变化归因于FFN。

| 方案 | FFN/层 | 相对双缓冲shared变化 |
|---|---:|---:|
| layer_dual_shared_Rfull | 4.641025 | -6.54% |
| layer_dual_shared_nl128 | 5.938200 | +19.59% |
| layer_digital_bf16 | 6.476587 | +30.43% |
| layer_old | 7.521200 | +51.46% |
| layer_serial_new | 7.271800 | +46.44% |
| layer_dual_shared | 4.965650 | +0.00% |
| layer_dual_bypass | 4.739650 | -4.55% |
| layer_dual_shared_sram2x | 4.794037 | -3.46% |
| layer_dual_shared_restore4x | 4.388350 | -11.63% |
| layer_dual_shared_array2x | 3.947300 | -20.51% |

## 守恒检查

通过：相同FFN有效工作/采样计数、外存权重与系数字节、Attention事件；shared双缓冲与旧版SRAM字节完全相同；bypass只减对应FFN权重/系数shared写入+读取。
- bypass减少shared逻辑访问：5.014658 GiB/token。
- SRAM内部动态能量模型（不含其他电路）: 25.532273 → 25.532273 → 13.131418 mJ/token。

## 逐项证据

- [full_old](results/case_0/RESULT_SUMMARY.json)；执行提交 `6f73ef65602a15cbbada807929936e8299502205`。
- [full_dual_shared](results/case_1/RESULT_SUMMARY.json)；执行提交 `6f73ef65602a15cbbada807929936e8299502205`。
- [layer_dual_shared_Rfull](results/case_10/RESULT_SUMMARY.json)；执行提交 `6f73ef65602a15cbbada807929936e8299502205`。
- [layer_dual_shared_nl128](results/case_11/RESULT_SUMMARY.json)；执行提交 `6f73ef65602a15cbbada807929936e8299502205`。
- [layer_digital_bf16](results/case_12/RESULT_SUMMARY.json)；执行提交 `6f73ef65602a15cbbada807929936e8299502205`。
- [full_dual_bypass](results/case_2/RESULT_SUMMARY.json)；执行提交 `6f73ef65602a15cbbada807929936e8299502205`。
- [layer_old](results/case_3/RESULT_SUMMARY.json)；执行提交 `6f73ef65602a15cbbada807929936e8299502205`。
- [layer_serial_new](results/case_4/RESULT_SUMMARY.json)；执行提交 `6f73ef65602a15cbbada807929936e8299502205`。
- [layer_dual_shared](results/case_5/RESULT_SUMMARY.json)；执行提交 `6f73ef65602a15cbbada807929936e8299502205`。
- [layer_dual_bypass](results/case_6/RESULT_SUMMARY.json)；执行提交 `6f73ef65602a15cbbada807929936e8299502205`。
- [layer_dual_shared_sram2x](results/case_7/RESULT_SUMMARY.json)；执行提交 `6f73ef65602a15cbbada807929936e8299502205`。
- [layer_dual_shared_restore4x](results/case_8/RESULT_SUMMARY.json)；执行提交 `6f73ef65602a15cbbada807929936e8299502205`。
- [layer_dual_shared_array2x](results/case_9/RESULT_SUMMARY.json)；执行提交 `6f73ef65602a15cbbada807929936e8299502205`。
