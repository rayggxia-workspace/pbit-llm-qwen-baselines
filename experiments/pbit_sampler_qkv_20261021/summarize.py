"""Validate paired rows and report observed MSE-equivalent update budgets."""
import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics

SEEDS={0,1,2}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def avg(x):return statistics.mean(x) if x else None
def quantile(x,p):
    if not x:return None
    a=sorted(x);k=(len(a)-1)*p;i=int(k)
    return a[i]+(a[min(i+1,len(a)-1)]-a[i])*(k-i)


def gather(records,expected_repeats=8):
    """All seeds/replicates required at each curve point; no partial-seed means."""
    groups={}
    for result in records:
        for curve in result['curves']:
            key=(result['method'],curve['burn'],curve['samples'])
            seed=result['seed']
            if seed in groups.setdefault(key,{}):raise ValueError('duplicate seed/point')
            errors=curve['normalized_error_per_repeat']
            if len(errors)!=expected_repeats or any(not math.isfinite(e) or e<0 for e in errors):raise ValueError('replicate errors')
            groups[key][seed]=curve
    curves={}
    for (method,burn,samples),parts in groups.items():
        if set(parts)!=SEEDS:raise ValueError('missing full seed group')
        errors=[e for seed in sorted(SEEDS) for e in parts[seed]['normalized_error_per_repeat']]
        mean=avg(errors);se=statistics.stdev(errors)/math.sqrt(len(errors)) if len(errors)>1 else 0.
        curve=dict(method=method,burn=burn,samples=samples,n=len(errors),normalized_mse=mean,
            mc_normal_95_low=max(0.,mean-1.96*se),mc_normal_95_high=mean+1.96*se,
            seed_means={str(s):avg(parts[s]['normalized_error_per_repeat']) for s in sorted(SEEDS)})
        for key in ('logical_updates_per_repeat','pbit_draws_per_repeat','extra_fair_bits_per_repeat','rank_calls_per_repeat'):
            values=[v for seed in sorted(SEEDS) for v in (parts[seed].get(key) or [])]
            curve[key.replace('_per_repeat','_mean')]=avg(values)
            curve[key.replace('_per_repeat','_p90')]=quantile(values,.9)
        if method=='legacy_ctmc':curve['legacy_process_horizon']=parts[0]['legacy_process_horizon']
        curves.setdefault(method,[]).append(curve)
    return curves


def crossing(curves,method,target,burn=32,upper=False):
    if method in ('iid','rejection'):
        # Their ideal independence gives analytic MSE = variance/S. Do not turn
        # finite-MC luck into a claimed 64-sample equivalent of IID128.
        return next((dict(c,criterion='analytic_independent_reference') for c in curves if c['burn']==0 and c['samples']==target),None)
    if method=='legacy_ctmc':burn=0
    eligible=[c for c in curves if c['burn']==burn and c['mc_normal_95_high' if upper else 'normalized_mse']<=1/target]
    if not eligible:return None
    return dict(min(eligible,key=lambda c:c['logical_updates_mean'] if c['logical_updates_mean'] is not None else c['legacy_process_horizon']),
                criterion='observed_mean_grid' if not upper else 'individual_approximate_MC95_upper_grid')


def summarize_rows(rows,require_sampling=False):
    groups={}
    for row in rows:
        meta=row['row'];group=(meta['context'],meta['pool'])
        groups.setdefault(group,[]).append(row)
    summary=[]
    for (context,pool),data in sorted(groups.items()):
        methods=sorted(data[0]['curves'])
        for target in (128,512):
            selected=[r for r in data if not require_sampling or r.get('profile',{}).get('map_normalized_mse',math.inf)>1/target]
            for method in methods:
                hits=[crossing(r['curves'][method],method,target) for r in selected]
                upper=[crossing(r['curves'][method],method,target,upper=True) for r in selected]
                okay=[c for c in hits if c is not None]
                clocks=[c['logical_updates_mean'] for c in okay if c['logical_updates_mean'] is not None]
                draws=[c['pbit_draws_mean'] for c in okay if c['pbit_draws_mean'] is not None]
                summary.append(dict(context=context,pool=pool,target_iid_samples=target,method=method,
                    rows=len(selected),excluded_map_already_sufficient=len(data)-len(selected),mean_gate_reached=len(okay),mc95_gate_reached=sum(c is not None for c in upper),
                    median_observed_updates=quantile(clocks,.5),p90_observed_updates=quantile(clocks,.9),
                    median_pbit_draws=quantile(draws,.5),
                    # P=64 is a service-wave lower bound; control, rank, score
                    # load, pipeline latency, and physical response are extra.
                    median_64pbit_service_wave_lower_bound=quantile([
                        c['logical_updates_mean']*math.ceil((r['candidates'] if method.startswith('winner') else r['candidates']-1 if method=='rejection' else 2 if method=='two_bits' else 1)/64)
                        for r,c in zip(selected,hits) if c is not None and c['logical_updates_mean'] is not None and method!='iid'],.5),
                    censor_note='updates summarize reached rows only; unreached rows excluded, never interpreted as zero cost'))
    return summary


def fixed_budget_checks(rows):
    """Quality at an actual fixed configuration, without threshold monotonicity assumptions."""
    checks=[]
    scopes=[('all',rows)]
    scopes += [(str(c)+'/'+pool,[r for r in rows if r['row']['context']==c and r['row']['pool']==pool])
               for c,pool in sorted({(r['row']['context'],r['row']['pool']) for r in rows})]
    for scope,data in scopes:
        for method in ('winner0','winner0_q8'):
            for burn in (0,32,128):
                for samples in (128,256,512,1024,2048,4096):
                    curves=[next(c for c in r['curves'][method] if c['burn']==burn and c['samples']==samples) for r in data]
                    checks.append(dict(scope=scope,method=method,burn=burn,samples=samples,updates=burn+samples,rows=len(data),
                        normalized_mse_mean=avg([c['normalized_mse'] for c in curves]),
                        target128_reached=sum(c['normalized_mse']<=1/128 for c in curves),
                        target128_mc95_reached=sum(c['mc_normal_95_high']<=1/128 for c in curves),
                        target512_reached=sum(c['normalized_mse']<=1/512 for c in curves),
                        target512_mc95_reached=sum(c['mc_normal_95_high']<=1/512 for c in curves)))
    return checks


def main():
    p=argparse.ArgumentParser();p.add_argument('--rows',required=True);p.add_argument('--capture-report',required=True)
    p.add_argument('--execution-commit',required=True);p.add_argument('--plan-sha256',required=True);p.add_argument('--output',required=True)
    p.add_argument('--allow-partial',action='store_true');a=p.parse_args()
    capture=json.loads(Path(a.capture_report).read_text());capture_sha=digest(a.capture_report)
    data=[];missing=[];files=[]
    import numpy as np
    if digest(capture['trace']['path'])!=capture['trace']['sha256']:raise ValueError('private trace SHA')
    trace=np.load(capture['trace']['path'],allow_pickle=False)
    for index,meta in enumerate(capture['rows']):
        path=Path(a.rows)/f'row_{index}.json'
        if not path.exists():missing.append(index);continue
        record=json.loads(path.read_text())
        if record.get('status')!='completed' or record['row']!=meta:raise ValueError('row identity/status '+str(index))
        if record['source_commit']!=a.execution_commit or record['capture_sha256']!=capture['trace']['sha256'] or record['capture_report_sha256']!=capture_sha or record['plan_sha256']!=a.plan_sha256:raise ValueError('source/input/config binding '+str(index))
        curves=gather(record['results'])
        expected={'iid','rejection','winner0','winner2','winner4','winner0_q8','two_bits','barker','barker_q8','xor','legacy_ctmc'}
        if set(curves)!=expected:raise ValueError('missing method '+str(index))
        profile=record['profile'].copy()
        z=trace[meta['row_id']+'_logits'].astype(np.float64);v=trace[meta['row_id']+'_values'].astype(np.float64)
        mu=np.array(profile['reference_output']);variance=profile['iid_single_sample_variance']
        profile['map_normalized_mse']=float(np.square(v[z.argmax()]-mu).sum()/variance) if variance>0 else 0.
        a8=-np.minimum(np.rint(np.abs(z-z.max())/.125),255)*.125
        w8=np.exp(a8-a8.max());mu8=(w8/w8.sum())@v
        profile['winner0_q8_stationary_bias_normalized']=float(np.square(mu8-mu).sum()/variance) if variance>0 else 0.
        data.append(dict(index=index,row=meta,candidates=record['candidates'],profile=profile,
            screening_omission_bias=record['screening_omission_bias'],curves=curves))
        files.append(dict(index=index,path=str(path),bytes=path.stat().st_size,sha256=digest(path)))
    if missing and not a.allow_partial:raise RuntimeError('incomplete rows '+repr(missing))
    if not data:raise RuntimeError('no completed rows')
    aggregate=summarize_rows(data)
    # Calibrate a fixed common-offset choice on first window only; check its
    # migration on the disjoint second window. Per-row oracle is not deployed.
    choices=[]
    for context,pool in sorted({(r['row']['context'],r['row']['pool']) for r in data}):
        cal=[r for r in data if r['row']['context']==context and r['row']['pool']==pool and r['row']['start_token']==0]
        test=[r for r in data if r['row']['context']==context and r['row']['pool']==pool and r['row']['start_token']==65536]
        if not cal or not test:continue
        values={m:avg([next(c['normalized_mse'] for c in r['curves'][m] if c['burn']==32 and c['samples']==128) for r in cal]) for m in ('winner0','winner2','winner4')}
        selected=min(values,key=values.get)
        choices.append(dict(context=context,pool=pool,calibration_rows=len(cal),test_rows=len(test),
            calibration_mse=values,selected=selected,test_mse=avg([next(c['normalized_mse'] for c in r['curves'][selected] if c['burn']==32 and c['samples']==128) for r in test]),
            limitation='small held-out window diagnostic, not trained controller or independent quality benchmark'))
    result=dict(status='completed' if not missing else 'partial',expected_rows=len(capture['rows']),completed_rows=len(data),missing_rows=missing,
        execution_commit=a.execution_commit,plan_sha256=a.plan_sha256,capture_report_sha256=capture_sha,
        capture_trace_sha256=capture['trace']['sha256'],summary_generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        primary_burn=32,targets=[128,512],groups=aggregate,groups_map_insufficient=summarize_rows(data,require_sampling=True),offset_transfer=choices,
        fixed_budget_checks=fixed_budget_checks(data),
        burn_thresholds=[dict(method=method,target=t,burn=b,rows=len(data),
            reached=sum(c is not None for c in hits),
            median_observed_updates=quantile([c['logical_updates_mean'] for c in hits if c is not None],.5),
            maximum_observed_updates=max([c['logical_updates_mean'] for c in hits if c is not None],default=None))
            for method in ('winner0','winner0_q8','winner2','winner4','two_bits','barker','barker_q8','xor')
            for b in (0,32,128) for t in (128,512)
            for hits in [[crossing(r['curves'][method],method,t,burn=b) for r in data]]],
        profiles=[dict(index=r['index'],**r['row'],candidates=r['candidates'],**{k:v for k,v in r['profile'].items() if k!='reference_output'},screening_omission_bias=r['screening_omission_bias']) for r in data],
        per_input_thresholds=[dict(index=r['index'],**r['row'],candidates=r['candidates'],thresholds={m:{str(t):crossing(cs,m,t) for t in (128,512)} for m,cs in r['curves'].items()}) for r in data],
        raw_artifact_index=files,
        limits=['Real fixed-row output MSE, not model PPL or task accuracy.','Ideal fresh independent p-bits, not physical device data.',
            'Grid crossing uses finite Monte Carlo; no exact minimum or simultaneous-confidence claim.',
            'Primary chain burn32; the raw curves retain burn0/32/128.',
            'Update counts and pbit-service waves are not measured clock cycles; control/feedback, score load, conversion, warmup and rank-tree pipeline are extra.',
            'Failed and missing rows are not replaced by IID; tables of reached rows are censored as labeled.'])
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    (out/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    def fmt(x):return '—' if x is None else f'{x:,.1f}'
    text=['# 真实QK/V采样器比较：更新预算与输出误差','',
        f"状态：{result['status']}；{len(data)}/{len(capture['rows'])}行；执行源`{a.execution_commit}`。",'',
        '主表固定链预热32；直接IID/拒绝法不需要链预热。每行三seed×八重复，真实64维V；误差对同候选准确输出。表中的轮数是算法更新/拒绝提议，不是芯片时钟。', '',
        '达标按观测均值MSE不大于解析IID目标判断；有限重复会使首次网格交叉波动。括号中的MC95达标是单点近似区间上界检查，不是全表同时置信保证。未达标输入不能当零成本。', '',
        '|上下文/候选池|目标IID次数|方法|均值达标行/总行（MC95）|达标行更新中位数|P90|p-bit服务中位数|',
        '|---|---:|---|---:|---:|---:|---:|']
    for g in aggregate:
        text.append(f"|{g['context']}/{g['pool']}|{g['target_iid_samples']}|{g['method']}|{g['mean_gate_reached']}/{g['rows']}（{g['mc95_gate_reached']}）|{fmt(g['median_observed_updates'])}|{fmt(g['p90_observed_updates'])}|{fmt(g['median_pbit_draws'])}|")
    text+=['','## 解读边界','',
           '- 直接校正拒绝法在理想响应下提供独立样本，表内其目标128/512固定为相应接受数，成本取实际重试；没有利用MC偶然小误差宣称更少样本。',
           '- 赢家保持/T32或CTMC的输出数、链更新数、提议数和有效样本量彼此不同；旧CTMC只保留质量参考，过程时间不能换算到时钟。',
           '- 对并行阵列，若只有64个物理p-bit，一帧至少ceil(N/64)个采样波；还需仲裁、分数驱动和反馈。单p-bit则需挑战者分数读取/差分/稳定，每更新未必一拍。',
           '- 并行固定偏置可以提前流水候选，但数字赢家更新的反馈关键路径、在途B帧和rank树仍须RTL/PT。Barker单链的分数依赖不能直接套同一流水II。',
           '- 主输入是原BF16轨迹，初始化argmax；不代表随机初始化、旧query赢家、随机FFN引起的新分布或完整模型结果。',
           '- 筛选遗漏误差在SUMMARY单列；采样器对候选的误差不会自动补回遗漏块。',
           '- q8指sigmoid驱动输入而非8位概率阈值，Barker量化差分不预设仍有准确原Softmax平稳分布。',
        '- 增加确定性argmax-V对照：部分极尖峰输入不采样也能满足此MSE目标。SUMMARY单列MAP不足的输入，避免把这些容易输入误算为采样器优势。8位赢家保持的无限样本偏差也由同一真实输入解析计算。',
        '- 完整逐seed/预算/预热曲线留在个人服务器原件，Git仅保留摘要、代码、来源及SHA。','']
    (out/'RESULTS_ZH.md').write_text('\n'.join(text),encoding='utf-8',newline='\n')
    print(json.dumps(dict(status=result['status'],completed=len(data),missing=missing,summary=str(out/'SUMMARY.json'))))


if __name__=='__main__':main()
