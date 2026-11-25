## 2026-11-25用户追加：21bit与本地PRNG默认

同Issue225/PR266，source3aa44ac8005337892ed0910b50a4e4500ffbeb22，17文件树与本地一致、4关键文件回读；ready/open未合并。复用tmp/cim-bank32-tlm-issue225-20261124，交接work/rayggxia/225/cim_count21_localrng_20261125/HANDOFF.md。

TLM计数、结果槽、结果线改21bit，K64/W8幅值127支持T128的数值容量；默认仍GU16/Wd32服务。冻结19bit校准RTL不覆盖，功能原型AW21已有；新21bit PPA未测，预算保留19bit参考并将新FFN及相关合计留空。五核净计数/FIFO状态增480B，不按位数直接推功耗面积。

用户澄清主要是本地PRNG向各输入供数。默认改为local_persistent，各核初始化后持续，采样消费才推进，等待不推进，不逐tile播种；中央固定步长/任意跳步并非硬件要求。GU共享64路、Wd三路保留原映射/联合分层；不要求不同调度逐位复现，旧jump软件只作可选参考。后续重播种沿随机服务原接口，未增加每tile熵源成本。

10unit、六组新trace、六类错误轨迹拒绝通过，五核小FFN2.664us未变；无新整机/PPL/RTL/STA/PT。原件归档project_archives/cim_count21_localrng225_20261125/RAW_AND_SOURCE.zip，1454537B，SHA e0f62912cff03437f412fcb4cb4f414267f043a34be153bfdec0ff9ce47b9ad5。正式记录COUNTER21_LOCAL_RNG_RESULTS_20261125.json。尺度封装与描述符满握手仍待落实，不因本次改位宽而宣称完成。
