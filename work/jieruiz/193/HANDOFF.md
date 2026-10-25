# Issue193交接（实现冻结，验证进行中）

负责人jieruiz；task/193-ffn-calibration-stage1；base main d83eeb1fc6b89a3dff51b5b62bf79acf665c7166。独立目录tmp/ffn-calibration-issue193-20261025。正式范围architecture_tlm/ffn_calibration_stage1；不改PR192/TLM默认、旧RTL或PPL。

已实现：精确计数、4/7档整数恢复、64位饱和累加、单帧chain、9 fixed tops、独立integer/TB、Slurm→VCS→DC→可选PT-STA脚本。29流程单测通过，暂无许可EDA或远端作业。

本地最终9case Icarus验证进行中：C:/Users/86134/AppData/Local/Temp/ffn193_final_functional。预检M8/B7/T128超过240s软件超时，已保留preflight_timeout.json，正式runner上限900s；M1三seed/M8一seed，全部仍包含多个极值和回压帧，非PPL统计。

下一步：读取summary结果，封存小回执/源码manifest，中央台账仅新增record，不从旧维护分支整目录覆盖main。写最终验证、ZIP、推送PR，更新Issue193/STATUS和备忘录。不自动合并。Projects缺read:project待同步。
