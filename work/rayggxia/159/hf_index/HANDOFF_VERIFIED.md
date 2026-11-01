# Issue159：HF登录核对补充交接

续PR229/task/159-hf-model-index；原匿名失败与PUBLICATION保留历史。现在用户登录的内置浏览器可读；repo确为private，不需要改公开或导出cookie/token。读取实际提交fa0a9e4a7ad394ffb60e8175cb0d1e34dff93caf的Hub API可视JSON，共276文件/37,494,721,776字节；七组目录、每组38文件/36FFN、non_ffn LFS oid和export Git blob均录入正式INDEX。实际读到本批HANDOFF和code_reference；manifest/transfer_checks只确认元数据与位置，未打开内容，不写成已逐文件验证。未下载大权重/未加载/未PPL/无GPU/EDA。

正式入口qwen3/model_artifacts/HF_SEVEN_FFN_MODELS_ZH_20261101.md；配套代码dataset固定版本/目录、原模型、加载规则及新helper未做完整4B运行的限制均明确。下一步如需推理，先按固定dataset获取对应加载器和metadata/tokenizer，核对manifest，再只下载需要case，同组non_ffn和全部36FFN不可混配。用户任务仅位置备注，不自动运行37.49GB下载或大评测，不将交付submitted改成accepted。

浏览器稳定用法：先getState(emit:false)，再agent.browsers.get('2')和tabs.get('2')；单独goto到确定URL（约12–22秒），下一工具调用read-only evaluate document.body.innerText。把goto/DOM合并且timeout20秒曾触发重置；异步WebCrypto evaluate亦超时，未产生可用checksum，不冒称SHA已验证。不要提取cookie/凭据。原模型库匿名HTTP401仍可能正常，不撤销已登录页面证据。

本地仍同一精简工作树；git sparse-checkout reapply已修复未检出文件显示D的索引标记，无原件删除。正式API远端历史与本地归档历史不同，禁止直接force-push。上传只列本次窄范围文件，回读SHA；Issue159/STATUS/备忘录增量及根阅读镜像同步，PR待审未合并，Projects待维护者同步。
