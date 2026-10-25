# 本轮实际使用的DRAMSys SG桥接器

这里收录服务器已有的`bridge_sg_v6_audit.cpp`原字节，SHA在SOURCE.json；不是另外实现一套DRAM时序。CMake只去掉未使用的旧target，其余配置保持。上游DRAMSys固定9f15aaf1fe6f05ff16a2e521a20a96f3bfe29d52，DRAMSys5.6 / SystemC3.0.2 / DRAMPower6.3.1。主上游许可见UPSTREAM_LICENSE.txt，各依赖许可仍在各自项目，下载版本/归档SHA见dependency_manifest.json。

```sh
cmake -S architecture_tlm/unified_v6/probes/dramsys_bridge -B build/dramsys-sg -DCMAKE_BUILD_TYPE=Release
cmake --build build/dramsys-sg --target pbit_dram_bridge_sg_v6_audit -j 4
export PBIT_DRAMSYS_BRIDGE="$PWD/build/dramsys-sg/pbit_dram_bridge_sg_v6_audit"
python -m architecture_tlm --memory-profile mature_ddr4 --ffn sc --attention screen_pv --output output/new-run
```

需要CMake3.25+、C++17工具链、依赖下载网络；用户可以用DRAMSYS_SOURCE（参数写作`-DDRAMSYS_SOURCE=/path/to/source`）及各FETCHCONTENT_SOURCE_DIR参数指定已校验的只读缓存。仓库不复制完整依赖或生成物。首次运行前将执行代码提交；不能指向已经存在的结果目录。

接口是JSON-lines和真实非阻塞TLM四阶段请求。功能握手必须包含scatter_gather_v1。SG每批至多256个span由Python侧限制/排序/验证，32个64B burst信用跨span滚动补充；bridge仍逐宏请求完成后响应，不是全局无限乱序。所有DRAM bank/row/refresh冲突由DRAMSys处理。严格单向actor时间在Python接入层检查。

本轮重新从这个CMake、相同C++和服务器只读依赖源码在独立目录构建成功，Slurm2993；8个SG/串行微基准与原桥时延误差小于1e-6ns、core能量相对差小于1e-10，地址/字节/突发一致。没有再跑整模型，也没有证明整个缓存源码树等于官方Git树；SOURCE.json明确记录该边界。全模型原来使用的二进制SHA仍是900e8257e255a01c59ed1770f8fda5901163003e0c8f21636baefc2cb662c868，不能用新构建SHA改写旧执行记录。

DRAM配置固定unified_v6/configs/dramsys/ddr4_2ch_2rank_NoPowerDown_core_limits.json，SHA ddbdd1aee7f20d5e3eaf12d73b7e300894ad3ab5cc50ae2a8aa5fd121b2fa419，实际16GiB。旧bridge provenance中的8GiB是早期配置，不能代替本轮配置与完成结果。

功耗仅core-current模型；VDDQ=0明确表示I/O/PHY未标定，不是I/O免费。已知负ACT增量保留在结果中，未当成物理负能量、未截零，且不反馈时序。控制器/PHY/互连PPA另计，不能将这里的J值叫整芯片能耗。
