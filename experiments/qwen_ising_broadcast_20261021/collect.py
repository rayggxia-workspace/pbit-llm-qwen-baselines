"""Summarize sealed Issue78 JSON; incomplete or failed services stay explicit."""
import argparse,hashlib,json,math,statistics
from pathlib import Path


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def collect(root):
    root=Path(root);reference=json.loads((root/'bf16_reference.json').read_text())
    suite=json.loads((root/'suite.json').read_text());entries=[];groups={};artifacts={}
    for c in suite['cases']:
        p=root/'ppl'/(c['name']+'.json')
        if not p.exists():entries.append(dict(configuration=c,status='pending'));continue
        r=json.loads(p.read_text());artifacts[str(p.relative_to(root))]=digest(p)
        if r['configuration']!=c:raise ValueError('configuration mismatch '+str(p))
        if r['status']=='completed':
            for k in ['scored_tokens','token_ids_sha256_le_int64']:
                if r[k]!=reference[k]:raise ValueError('scoring mismatch '+k)
            if r['bf16_reference_sha256']!=digest(root/'bf16_reference.json'):raise ValueError('baseline changed')
        st=r.get('network_call_stats',[])
        slots=sum(s['observation_slots'] for s in st)
        invalid=sum(s['invalid_observation_slots'] for s in st)
        e=dict(configuration=c,status=r['status'],perplexity=r.get('perplexity'),
            mean_nll=r.get('mean_nll'),seconds=r.get('elapsed_seconds'),
            invalid_readout_fraction=invalid/slots if slots else None,
            adjacent_repeat_fraction=statistics.mean(s['adjacent_repeat_fraction'] for s in st) if st else None,
            mean_service_sweeps=statistics.mean(s['executed_sweeps'] for s in st) if st else None,
            mean_service_update_phases=statistics.mean(s['update_phases'] for s in st) if st else None,
            failure=r.get('failure_stats'))
        entries.append(e);groups.setdefault(c['backend'],[]).append(e)
    grouped=[]
    for name,items in groups.items():
        good=[x for x in items if x['status']=='completed'];ppl=[x['perplexity'] for x in good]
        grouped.append(dict(method=name,completed_seeds=len(good),failed_seeds=len(items)-len(good),
            ppl_mean=statistics.mean(ppl) if ppl else None,
            ppl_sd=statistics.stdev(ppl) if len(ppl)>1 else None,
            exp_mean_nll=math.exp(statistics.mean(x['mean_nll'] for x in good)) if good else None))
    return dict(issue=78,scope='128-target CPU BF16 suffix pilot, not full WT2',
        baseline_ppl=reference['perplexity'],scored_tokens=reference['scored_tokens'],
        source_commit=suite['args']['commit'],pending=sum(x['status']=='pending' for x in entries),
        entries=entries,groups=grouped,artifact_sha256=artifacts,
        baseline_sha256=digest(root/'bf16_reference.json'),suite_sha256=digest(root/'suite.json'))


def render(s):
    lines=['# 全局广播与随机分块更新：CPU模型初筛','',
        f"原BF16 PPL：**{s['baseline_ppl']:.6f}**；{s['scored_tokens']}个固定后缀目标。",
        '原FFN、准确多token前缀；24层被计分decode Attention替换。筛选最多512候选、S64。',
        '**不是完整WT2，不能与历史完整PPL直接比较。CTMC是理想连续时间有限观测参考，不是64次独立准确Softmax。**','',
        '| 方法 | 完成seed | 失败seed | PPL均值 | seed标准差 |',
        '|---|---:|---:|---:|---:|']
    for g in s['groups']:
        p='—' if g['ppl_mean'] is None else f"{g['ppl_mean']:.6f}"
        sd='—' if g['ppl_sd'] is None else f"{g['ppl_sd']:.6f}"
        lines.append(f"| {g['method']} | {g['completed_seeds']}/3 | {g['failed_seeds']} | {p} | {sd} |")
    lines+=['',f"仍待完成：{s['pending']}项。失败不计入PPL均值，未齐3seed的均值只是部分结果。",
        '非法状态观测会等待，直到64个有效地址；cap失败保留null，不删行或用IID替代。',
        '新网络间隔随机1..7次扫描、均值4，用于排除固定步长混叠；与CTMC的时间单位不同。',
        '更新阶段/CPU耗时不是ASIC周期/功耗。未运行RTL/PT；无训练。',
        '',f"执行源码：`{s['source_commit']}`。原始文件SHA见SUMMARY.json；输入权重/语料与逐目标审计保存在原始JSON。"]
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    s=collect(a.input);o=Path(a.output);o.mkdir(parents=True,exist_ok=True)
    for name,data in [('SUMMARY.json',json.dumps(s,indent=2,ensure_ascii=False,allow_nan=False)+'\n'),('RESULTS_ZH.md',render(s))]:
        with (o/name).open('x',encoding='utf-8',newline='\n') as f:f.write(data)
    print(json.dumps(s['groups']),flush=True)

if __name__=='__main__':main()
