# 64×64冻结二次幂权重参考

本分支提供用户2026-10-27修订的权重格式，供七组训练交接使用，见../training/seven_case_ffn_20261027/REMOTE_AGENT_PLAN_ZH.md。训练任务尚未提交，旧PPL不继承。

权重w_hat=Q*2**k。每块64×64一个int8指数；S1和S3广播共享指数。支持总有符号位宽4/6/8/9/10，七组仅使用6/8/10。码范围分别由2**(b-1)-1确定；模拟int16容器不冒充真实bit-pack。

choose_exponents用frexp在离线加载权重后选cover-max PoT步长，零块k=-24。训练及推理复用冻结指数，不逐token/step重算max；scale_maps.py提供S1/S3和参考W8范围保持。W6/W10 k_b=k8+8-b。

校准、训练硬前向和推理入口共用同一量化规则。Wd恢复系数也为精确二次幂，不把65536饱和成65535；大于15级指数跨度需要扩展恢复契约，不能静默截断。校准/checkpoint有pot64-v2版本，旧权重只可显式warm-start并重新校准。

默认参考仍是PR178的输入64/joint32及FFN-only；本方案的全模型IID、T16/32/64两段采样需要对方Agent集成。GU恢复仍有FP32参考边界，需整数oracle核对，不能称整个FFN bittrue。

本次52项CPU测试48通过4CUDA跳过，详见validation_20261027/VALIDATION.json与TEST_LOG.txt。没有新PPL、H200/GPU/RTL/PT/TLM结果。Qwen3-4B tile64逻辑指数656640B约641.25KiB；这是元数据容量，不是面积/能耗比，也不是必须一次全放在片上。
