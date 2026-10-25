# 原生ONNXim机制探针

固定公开源码8599bee46b311fb267ac34b0677ad7db3d8a8ccd，主许可证MIT见UPSTREAM_LICENSE.txt。`build_and_run.py`下载固定版本和依赖、记录每个文件SHA，构建并运行；下载缓存可放相邻download_cache，INDEX必须含URL/原字节SHA。正式依赖版本与构建命令在结果SOURCE.json/COMMAND.json。

```sh
python3 build_and_run.py /absolute/new/empty-output-directory
```

需要GCC支持C++20及网络；构建结果目录必须不存在。4个原实现Core.cc、SystolicWS.cc、Sram.cc、SystolicOS.cc保持原字节；OS只为链接编译，其实现未完成，没有拿它做基准。头适配明确记录ADAPTER.patch：移除无关ONNX图头、Core的Dram依赖替成Common、向量延迟方法设virtual、必要MAX/MIN兼容。SC只在新子类的COMP指令返回显式宏忙时，未修改原Core调度。

25情景：原WS＋SC忙时8/32/64/128，分别双tile、单tile、受限外部服务、交错bank、冲突bank。每项4tile，1024B读取、512B写出，核对请求ID、依赖、所有返回和回压。受限外部服务同时把window8改1、latency3改11，因此不能把全部差值归因window。官方无数据payload的WS夹具39/47拍也通过。

这些是接口/机制检查，不是数值FFN，不是完整Qwen，不是BF16/W8混合精度性能对照，也没有在这个probe内接DRAMSys。全模型TLM另外调用真实DRAMSys。上游Sram主要记录容量/valid，不代表完整SRAM bank仲裁；SimpleNoC/内部队列也并非全部有物理深度。探针的外部bank服务是我们显式的合成有限服务。

实际执行：native_v1/2983下载超时失败，native_v2/2985因fmt链接失败，native_v3/2986加-DFMT_HEADER_ONLY后完成25项。失败目录保留。GCC13.3的-O2构建有17项来自fmt内联路径的stringop-overflow告警，没有抹去；随后相同代码用-O1 -fsanitize=address,undefined重建2994，25项结果原字节SHA一致，stderr为0。这个sanitizer检查只覆盖实际运行路径，不能证明上游所有输入无内存错误。

结果：../../results/scheduling_20261025/native/；sanitizer/保存复核索引。大二进制和依赖留远端本人pbit-scheduling-issue186-20261025/native_v3及native_sanitize，不复制进Git。
