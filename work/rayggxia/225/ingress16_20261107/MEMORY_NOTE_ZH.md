## 2026-11-07 Issue225：用户选定100MHz DMA16KiB

当前100MHz默认6核/GU16-Wd32/共享QK/1216KiB，返回数据保持24→16KiB；CURRENT_100MHZ.json指向ffn6_100mhz_20261107.ingress16.make_model。原24KiB model/PROFILE/RESULTS与250MHz不改。全冷单层（36层地址分配、含embedding无head）解析136.4606GB/s/30ns、seed17：1.19425→1.19475ms，+0.04187%/50拍；算术/采样/外存字节和地址sum/xor一致、队列排空。非原生LPDDR整token；历史0.26%是旧DDR4完整单层增幅。覆盖面积33.692039→33.295774mm²，保持1.188795→0.792530mm²，沿原bank校准缩容量，无新PT，不按容量缩捕获动态能量。32KiB DMA SRAM预留保留，控制器/PHY/路由未知成本不置零。报告architecture_tlm/ffn6_100mhz_20261107/INGRESS16_ZH.md，原件/SEAL位于work/rayggxia/225/ingress16_20261107/replay。

修改/单层校验本地完成；远端状态见同任务PUBLICATION.json，PR248待审不合并。无新GPU/EDA作业或电路台账run；Projects待维护者同步。

---
