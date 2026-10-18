# Issue16实际验证

执行：`python work/jieruiz/16/verify_layout.py --record`，完成后以`--staged`核对发布Git字节。仅目录/入口调整，未运行新的GPU/DRAM/Slurm任务，不用旧PPL冒充本次模型测试。

- 三个模型project身份/配置路径正确；17个原始配置/源/结果SHA锚点通过。
- 24次实际命令检查：各模型check/info、全部13个动作dry-run、三个TLM真实--help和两个冻结快照verify，既检查根目录也检查仓库外cwd。
- 路径中含空格、原样argv、调用者cwd与子进程退出码透传检查覆盖三模型；../、绝对路径、盘符和反斜杠越界均拒绝。
- 93个本地Markdown链接存在；全部既有实现/结果未移动或修改。Llama1的62项及Llama2的57项冻结输入原字节SHA验证通过。
- 初次检查发现Llama1导航误写trace_validation，已改成实际capture_validation；完整检查随后通过。旧模型源码未改。
- 变更只含三个模型目录、共享分派脚本、根README、本人STATUS和work/jieruiz/16；不提交权重、数据、工艺库或其他成员改动。

`manifest.json`记录源码/文档/模型项目配置SHA、完整命令与精确base。采样数、种子、语料和模型版本未变，沿用各project.json索引的原实验记录；本任务不生成新性能或质量数值。
