"""Render the verified pilot only; never infer missing seeds or hardware PPA."""
from pathlib import Path
import argparse,csv,hashlib,json
from summarize import summarize


def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();v=summarize(a.root)
    assert v['status']=='completed' and v['results']==40 and v['completed_tasks']==6
    a.output.mkdir(parents=True,exist_ok=True)
    index={(x['context'],x['case']):x for x in v['summary']}
    lines=['# 长上下文Attention采样预算初筛（Issue237 / PR238）','',
           '本轮是Qwen3-4B后训练模型的128目标短后缀PPL初筛，原FFN与投影BF16、准确prefill，全部36层计分decode Attention替换；不是完整WT2或长文检索验收。', '',
           '两长度使用完全相同的四组目标位置，每组32目标；各随机方案三部署seed。±为部署PPL样本标准差，不是多文本或多训练seed置信区间。', '',
           '|配置|8K：主K256|32K：主K512|','|---|---:|---:|']
    for label,tag in [('原BF16','BF16'),('筛选后准确Softmax/PV','exact')]+[(f'赢家保持 S{s}',f'S{s}') for s in (32,64,128,256)]:
        cells=[]
        for n,k in ((8192,256),(32768,512)):
            case='BF16' if tag=='BF16' else f'K{k}_exact' if tag=='exact' else f'K{k}_WH_{tag}'
            row=index[(n,case)];sd=row['deployment_sd']
            cells.append(f"{row['mean_ppl']:.4f}"+(f" ± {sd:.4f}" if sd else ''))
        lines.append('|'+label+'|'+'|'.join(cells)+'|')
    lines+=['','同K准确PV对照用于分离额外采样损失：','','|S|8K相对准确PV|32K相对准确PV|','|---:|---:|---:|']
    for s in (32,64,128,256):
        values=[]
        for n,k in ((8192,256),(32768,512)):
            reference=index[(n,f'K{k}_exact')]['mean_ppl'];ppl=index[(n,f'K{k}_WH_S{s}')]['mean_ppl']
            values.append(f'{(ppl/reference-1)*100:+.2f}%')
        lines.append(f'|{s}|'+'|'.join(values)+'|')
    lines+=['','K仅加倍一次，固定S128：','','|上下文|主K准确PV|加倍K准确PV|主K/S128|加倍K/S128|','|---|---:|---:|---:|---:|']
    for n,k in ((8192,256),(32768,512)):
        values=[]
        for case in (f'K{k}_exact',f'K{k*2}_exact',f'K{k}_WH_S128',f'K{k*2}_WH_S128'):
            x=index[(n,case)];values.append(f"{x['mean_ppl']:.4f}"+(f" ± {x['deployment_sd']:.4f}" if x['deployment_sd'] else ''))
        lines.append(f'|{n}|'+'|'.join(values)+'|')
    lines+=['','初筛建议：8K先保留K256/S128，32K先保留K512/S128。S64可留作更低预算候选；S32在本批未训练推理中退化较明显。K加倍没有显示明确收益，暂不扩大候选。S256未显示稳定优于S128，不能反过来声称S128在总体上更准确；32K S128的部署seed波动较大，需要更多文本确认。',
      '', '这里的S扫描评估采样机制的质量—预算权衡；S参数本身不是新的采样算法。PV逻辑地址减少不能直接换算整机时间或能量。',
      '', '数值与范围：', '',
      '- r32、recent32包含在K内，四Q头共享每KV组候选；S是每Q头有效地址数，保持和重复也计入。',
      '- 当前RNE signed12/F4分数→整数max差值→饱和U8/F4地址→原floor-P8 LUT；slot0/burn0，独立Philox，不是旧round-P8/burn32，也不是物理/GF64共享源位真。',
      '- FP32是原QK/SparQ的行为参考；采样前端实际执行定点量化和离散P8。没有把理想sigmoid或准确Softmax地址伪装成赢家采样。',
      '- 三seed的BF16结果各长度逐值一致；只从六份COMPLETE及40份封存JSON确认完成，独立重算NLL/PPL、共同目标SHA、36×128覆盖、每层S×4096提议/地址且零回退。',
      '- 仅128目标，随机配置并非共享整模型随机前缀；小差异和非单调性不能解释为显著优劣。筛选PPL低于BF16不代表所有任务能力更高。',
      '- 本轮未加入随机FFN，没有训练、长上下文TLM、硬件周期/能耗/面积结论。正式预算仍需更大计分集合及长文任务确认。', '',
      '公开交付为本报告、RESULTS.csv、AGGREGATE.json与两个分析脚本。完整逐结果SUMMARY.json、源/模型/数据SHA及ARTIFACT_INDEX.json仅保留在本地授权归档；本次不公开权重哈希、个人服务器路径或完整执行元数据。大权重和语料不入库。', '']
    (a.output/'REPORT_ZH.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    (a.output/'SUMMARY.json').write_text(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    aggregate={k:v[k] for k in ('status','results','expected','completed_tasks','expected_tasks','summary','scope')}
    (a.output/'AGGREGATE.json').write_text(json.dumps(aggregate,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    with (a.output/'RESULTS.csv').open('w',encoding='utf-8',newline='') as f:
        fields=['context','case','seeds','mean_ppl','deployment_sd'];w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(v['summary'])
    print(json.dumps(dict(results=v['results'],summary=v['summary']),ensure_ascii=False))


if __name__=='__main__':main()
