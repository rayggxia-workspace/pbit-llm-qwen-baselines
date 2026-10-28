from report_fixed import *
stage='''## 2026-10-28 Issue198：定点QK与有限LUT数值/短流验证完成

rayggxia继续task/198-attention-compare / draft PR199，main为PR base；独立目录tmp/attention-compare-issue198-20261027，执行父49880d16+不可变源SHA。用户要求BF16之后测试INT8或更高定点、方便输入LUT。CPU3301/GPU3302首次全零阈值断言失败，原件保留；CPU3303/GPU3304完成46配置并暴露±32饱和；CPU3305/GPU3306完成扩大范围的62配置、10种S128/burn32×3seed局部审计及14个短流PPL case。本人本轮全部作业已结束，未动其他健康作业。

原Qwen3-4B后训练revision1cfa9a7、模型/tokenizer/WT2原字节/token SHA核验，4 train query标定、8 test query×全36层×32头=9216行，固定FP32 SparQ128候选。12/12有无诊断原生logits逐位相同；v2/v3输入与13248共用结果逐项一致。实际scaled score[-17.4184,37.5958]，±32即使高小数位仍最大TV约72%，不能只看平均。范围±64：INT8 step1/2平均TV4.3517%、输出RMS6.5730%；I11 step1/16为0.5435%/0.8329%；I12 step1/32为0.2724%/0.4115%；BF16对照0.5082%/0.8433%。均为局部指标。

推荐作为待验接口的分离位宽：11位分数（或12位增加范围余量）、4小数、整数max与差值、8位LUT地址（gap step1/16、cap255）、12/16位阈值。P12平均稳态TV0.6655%/输出RMS0.8576%，P16为0.5479%/0.8330%；P8平均丢掉约1.702%目标质量。先BF16再I11/P16为TV0.6380%/RMS0.9628%，直接从累加器转换避免额外BF16舍入。单表256×P12/P16=384/512byte仅逻辑容量，不是128并行读物理面积。

固定参考train max+2在P8/P12/P16出现1414/344/74个全零头行，P16有限采样输出RMS约80.25%对理想19.59%；不能仅凭softmax平移不变性省去在线参考控制。invalid头行明确排除稳态均值并单报，不加uniform/一LSB隐含fallback；不是全部离线标定不可行证明。

短流256目标（4等间距窗、prefill2047、每窗64步、context2048增长2111），全36层每目标实际替换，原FFN保持。原生/包装8目标门禁逐字节、512 LUT项独立公式通过；各量化case 37748736 score、0饱和。PPL BF16 17.70427，纯SparQ16.50503，理想winner16.94690±0.41999，INT8step1/2 17.32488±0.63733，I11+U8+P12 17.42265±0.49642，P16 17.34924±0.21394。三seed均值约高理想2%–3%、波动明显，未证明无损/显著优劣；不是旧完整WT2，可用小样本筛查而非验收。范围选择参考test局部观察，属探索性选型。

正式experiments/attention_fixedpoint_20261028/REPORT_ZH.md、SUMMARY、PPL_SUMMARY、CALIBRATION、RAW_INDEX、provenance、COMPLETE、REPEAT_CHECK；源码audit/quantize/quality，辅助report_fixed/write_fixed_report/deploy_fixed_v3。原始11.8MB结果与逐case PPL在project_archives/attention_compare_issue198_20261027/fixedpoint_20261028_v3及个人服务器fixed3-6539a4ea8baf，27文件SHA校验；v1/v2归档不改。执行来源FIXED{,2,3}_SOURCE/CPU/SUBMISSION/COLLECTION；失败FIXED_FAILURE。实际推送/回读见FIXED_PUBLICATION.json。STATUS/HANDOFF/长期记忆增量同步，PR待审不合并、Issue不关闭，Projects沿权限限制待维护者同步。

无新RTL/EDA/PPA、无全WT2、未量化Q/K乘法，不新增数字电路台账run、不替换当前默认。下一步匹配完整PPL与11/12位分数转换/整数max/ROM/比较器/随机供给联合PPA，现有控制0.923nJ不包含这些成本。

---

'''
def main():
    for p in [R/'progress/rayggxia/STATUS.md',W/'HANDOFF.md']:
        b=p.read_bytes();assert not b.startswith(stage.encode());p.write_bytes(stage.encode()+b)
    backup=A/'reading_preimages';backup.mkdir(exist_ok=False);mem=[]
    for i,p in enumerate([WS/'PROJECT_MEMORY_ZH.md',WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md']):
        b=p.read_bytes();(backup/f'memory{i}.bin').write_bytes(b);assert p.read_bytes()==b;p.write_bytes(stage.encode()+b)
        mem.append(dict(path=str(p),pre_sha256=hashlib.sha256(b).hexdigest(),new_sha256=sha(p)))
    save(W/'FIXED_MEMORY_SYNC.json',dict(memories=mem,preimages=str(backup),old_bytes_preserved=True,mirrors_equal=mem[0]['new_sha256']==mem[1]['new_sha256']))
    print('STATUS_HANDOFF_MEMORY_UPDATED')
if __name__=='__main__':main()
