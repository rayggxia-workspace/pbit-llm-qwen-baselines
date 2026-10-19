"""Validate registered Issue48 results before writing matched NLL/PPL reports.

Only sweep/suffix and full_confirm/full are publishable. Pilot self-checks do
not create a report or print pilot quality numbers.
"""
from pathlib import Path
import argparse,copy,csv,hashlib,json,math,re,statistics,struct

GEOMETRY=('segment_id','begin','end','first_target','last_target_exclusive','prefill_tokens','scored_tokens')
INVARIANTS=('context','decode','examples','batch','burn','spacing','budget_blocks','target_fraction','protocol','stride')
METRICS=('query_rows','query_token_rows','possible_candidates','selected_candidates','padded_qk_candidates','selected_blocks','raw_selected_blocks','quota_added','quota_removed','GQA_union_candidates','GQA_possible_candidates','sample_events','adjacent_repeats','adjacent_pairs')
SAMPLED={'screen_iid','screen_ising','ising_only'}
MODES=SAMPLED|{'sdpa','digital_sdpa','digital_exact','screen_exact'}

def require(condition,message):
    if not condition:raise ValueError(message)

def digest(value,name,length=64):
    require(isinstance(value,str) and re.fullmatch('[0-9a-f]{%d}'%length,value),name+' must be a nonempty hexadecimal digest')
    return value

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def ids_sha(values):
    result=hashlib.sha256()
    for value in values:result.update(struct.pack('<q',value))
    return result.hexdigest()

def finite(value,name):
    require(isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value),name+' must be finite')
    return value

def near(actual,expected,name,absolute=1e-9):
    require(math.isclose(finite(actual,name),finite(expected,name),rel_tol=1e-12,abs_tol=absolute),name+' does not reconcile')

def expected_plan(case,count):
    """Reconstruct positions without trusting saved plan/target digests."""
    for key in ('context','decode','examples','batch','stride'):
        require(type(case[key]) is int and case[key]>0,key+' must be a positive integer')
    require(type(count) is int and count>=2 and case['context']>=3,'invalid corpus/context length')
    context=case['context'];rows=[]
    if case['protocol']=='suffix':
        last=count-context-case['decode'];require(last>=0,'suffix exceeds source length')
        n=case['examples'];starts=[0] if n==1 else [round(last*i/(n-1)) for i in range(n)]
        require(len(set(starts))==n,'duplicate suffix starts')
        for begin in starts:
            first=begin+context;end=first+case['decode']
            rows.append(dict(segment_id=len(rows),begin=begin,end=end,first_target=first,last_target_exclusive=end,prefill_tokens=context-1,scored_tokens=case['decode']))
    elif case['protocol']=='full':
        require(case['stride']<=context,'full stride exceeds context');previous=0
        for begin in range(0,count,case['stride']):
            end=min(begin+context,count);first=max(previous,begin+1)
            if first<end:rows.append(dict(segment_id=len(rows),begin=begin,end=end,first_target=first,last_target_exclusive=end,prefill_tokens=first-begin-1,scored_tokens=end-first))
            previous=end
            if end==count:break
    else:raise ValueError('unknown protocol')
    positions=[p for row in rows for p in range(row['first_target'],row['last_target_exclusive'])]
    require(len(set(positions))==len(positions),'overlapping targets')
    if case['protocol']=='full':require(positions==list(range(1,count)),'full corpus targets omitted/duplicated')
    return rows,positions

def expected_calls(plan,batch):
    groups=[];pending=[];signature=None
    for row in plan:
        current=(row['end']-row['begin'],row['prefill_tokens'],row['scored_tokens'])
        if pending and (current!=signature or len(pending)==batch):groups.append(pending);pending=[]
        signature=current;pending.append(row)
    if pending:groups.append(pending)
    return sum(g[0]['scored_tokens'] for g in groups),sum(g[0]['prefill_tokens']>0 for g in groups)

def verify_result(stage,entry,registered,data):
    case=data['args'];require(registered['case_id']==entry['case_id']==case['case_id'],'case identity mismatch')
    for key,value in registered.items():require(key in case and case[key]==value,'registered/result argument mismatch: '+key)
    for key in ('mode','samples','seed','selection','protocol'):require(entry[key]==case[key],'stage/result label mismatch: '+key)
    require(case['mode'] in MODES and case['selection'] in ('fixed','variable'),'unknown mode/selection')
    require(type(case['samples']) is int and case['samples']>0 and type(case['seed']) is int and case['seed']>=0,'invalid samples/seed')
    require(data['execution_source_commit']==case['source_commit']==stage['source_commit'],'execution source mismatch')
    require(data['full_model_state_before_sha256']==stage['model_state_before_sha256'],'case model state differs from stage')
    digest(data['input_manifest_sha256'],'input manifest hash');digest(case['model_revision'],'model revision',40)
    token=digest(data['token_ids_sha256_le_int64'],'token hash')
    require(token==stage['token_sha256']==case['token_sha256'],'token identity mismatch')
    require(data['source_tokens']==stage['source_tokens'] and data['protocol']==case['protocol'],'source count/protocol mismatch')
    plan,positions=expected_plan(case,data['source_tokens']);examples=data['examples'];meta=data['scoring_plan']
    require(len(examples)==len(plan)==len(meta['segments']),'segment count mismatch')
    for example,declared,expected in zip(examples,meta['segments'],plan):
        require(all(example[k]==expected[k]==declared[k] for k in GEOMETRY),'segment geometry differs from protocol')
        require(example['start_token']==expected['begin'] and example['first_target_token']==expected['first_target'] and example['last_target_token']==expected['last_target_exclusive']-1,'segment target labels mismatch')
        require(example['target_positions_sha256_le_int64']==ids_sha(range(example['first_target'],example['last_target_exclusive'])),'segment target SHA mismatch')
        digest(example['token_ids_sha256_le_int64'],'segment token hash');require(finite(example['nll_sum'],'segment NLL')>=0,'negative segment NLL')
    target=ids_sha(positions)
    require(meta['target_positions_sha256_le_int64']==target,'global target SHA differs from reconstructed positions')
    require(meta['segment_starts']==[row['begin'] for row in plan],'start offsets mismatch')
    require(meta['protocol']==case['protocol'] and meta['source_tokens']==data['source_tokens'] and meta['every_full_corpus_target_once'] is (case['protocol']=='full'),'scoring-plan labels mismatch')
    n=sum(row['scored_tokens'] for row in examples);nll=math.fsum(row['nll_sum'] for row in examples)
    require(n==len(positions)==data['scored_tokens']==meta['scored_tokens']==entry['scored_tokens'],'scored count mismatch')
    near(data['nll_sum'],nll,'NLL sum');near(data['mean_nll'],nll/n,'token-weighted mean NLL',1e-12)
    near(data['perplexity'],math.exp(nll/n),'PPL',1e-10);near(entry['perplexity'],data['perplexity'],'stage PPL',1e-10)
    require(data['attention_layers']==24 and data['ffn'].startswith('original Qwen2MLP'),'model boundary mismatch')
    dc,pc=expected_calls(plan,case['batch']);audit=data['execution_audit']
    require(audit['every_scored_target_executed_all_24_layers'] is True and audit['scored_query_tokens']==n and audit['decode_calls_per_layer']==[dc]*24 and audit['prefill_calls_per_layer']==[pc]*24,'all-layer decode/prefill audit mismatch')
    sampling=data['sampling_stats']
    if case['mode']=='sdpa':require(sampling is None,'raw SDPA unexpectedly has replacement statistics')
    else:
        require(sampling['installed_layers']==24 and set(sampling['layers'])=={str(i) for i in range(24)},'replacement not on exactly all 24 layers')
        for key in ('mode','samples','burn','spacing','seed','selection','budget_blocks','target_fraction'):require(sampling[key]==case[key],'sampler argument mismatch: '+key)
        layers=sampling['layers'];totals=sampling['totals']
        for state in layers.values():
            require(state['query_rows']==n*14 and state['query_token_rows']==n and state['decode_calls']==dc and state['prefill_calls']==pc,'controller missed targets/heads/calls')
            for key in METRICS:require(finite(state[key],key)>=0,'negative cumulative metric')
            require(0<state['candidate_min']<=state['candidate_max'],'invalid candidate extrema')
            last=state.get('last_sampler_stats')
            if last and case['mode'] in ('screen_ising','ising_only'):
                require(last['samples']==case['samples'] and last['burn']==case['burn'] and last['spacing']==case['spacing'],'last CTMC config mismatch')
                require(last.get('event_cap_reached') is False and last.get('iid_fallback') is False and last.get('dropped_rows')==0 and last.get('dropped_events')==0,'last CTMC reports truncation/fallback')
        for key in METRICS:near(totals[key],math.fsum(s[key] for s in layers.values()),'cumulative '+key)
        for field,num,den in (('selected_fraction','selected_candidates','possible_candidates'),('GQA_union_fraction','GQA_union_candidates','GQA_possible_candidates'),('adjacent_repeat_fraction','adjacent_repeats','adjacent_pairs')):
            ratio=totals[num]/totals[den] if totals[den] else 0.;near(totals[field],ratio,field,1e-12);require(0<=ratio<=1,'invalid '+field)
        if case['mode'] in SAMPLED:
            near(totals['sample_events'],n*14*24*case['samples'],'all-call recorded samples')
            near(totals['adjacent_pairs'],n*14*24*(case['samples']-1),'all-call adjacent pairs')
    return dict(case_id=case['case_id'],args=case,result=data,sha256=entry.get('sha256'))

def verify_stage_data(stage,registered,payloads,*,allow_preflight=False):
    require(stage['passed'] is True,'failed stage cannot be reported complete')
    protocols={'sweep':'suffix','full_confirm':'full'}
    if allow_preflight:protocols['gpu_preflight']='suffix'
    require(stage['stage'] in protocols,'only sweep/full_confirm may publish quality reports')
    digest(stage['source_commit'],'source commit',40)
    before=digest(stage.get('model_state_before_sha256'),'before model hash');after=digest(stage.get('model_state_after_sha256'),'after model hash')
    require(before==after,'model state changed');digest(stage['token_sha256'],'stage token hash')
    require(len(stage['cases'])==len(registered)==stage['registered_case_count']>0,'incomplete registered case list')
    ids=[c['case_id'] for c in registered];require(len(set(ids))==len(ids) and set(payloads)==set(ids),'duplicate/missing case IDs')
    records=[];identity=None
    for entry,case in zip(stage['cases'],registered):
        row=verify_result(stage,entry,case,payloads[case['case_id']]);c=row['args'];data=row['result']
        require(c['protocol']==protocols[stage['stage']],'stage/protocol mismatch')
        current=(tuple(c[k] for k in INVARIANTS),data['input_manifest_sha256'],c['model_revision'],data['scoring_plan']['target_positions_sha256_le_int64'],tuple((r['begin'],r['end'],r['token_ids_sha256_le_int64']) for r in data['examples']))
        if identity is None:identity=current
        require(current==identity,'cases differ in scoring/RNG order, inputs, or targets');records.append(row)
    require(any(r['args']['mode']=='sdpa' for r in records),'matched cached SDPA is required')
    return records

def child_path(source,relative):
    path=(source/relative).resolve();require(path.is_relative_to(source.resolve()) and path!=source.resolve(),'artifact path escapes source');return path

def load_verified(source,*,allow_preflight=False):
    source=Path(source);stage=json.loads((source/'stage_summary.json').read_text(encoding='utf-8'))
    manifest=json.loads((source/'artifacts.json').read_text(encoding='utf-8'));require(manifest['source_commit']==stage['source_commit'],'artifact/source commit mismatch');indexed={}
    for row in manifest['files']:
        require(row['path'] not in indexed,'duplicate artifact manifest path');path=child_path(source,row['path'])
        require(path.is_file() and path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],'artifact SHA/bytes mismatch: '+row['path']);indexed[row['path']]=row
    require('stage_summary.json' in indexed and 'registered_cases.json' in indexed,'stage/registration not manifest-indexed')
    registered=json.loads((source/'registered_cases.json').read_text(encoding='utf-8'));payloads={}
    for entry in stage['cases']:
        require(entry['file'] in indexed and entry['sha256']==indexed[entry['file']]['sha256'],'case/artifact hash mismatch')
        payloads[entry['case_id']]=json.loads(child_path(source,entry['file']).read_text(encoding='utf-8'))
    require('inputs_verified.json' in indexed,'input report not manifest-indexed');inputs=json.loads((source/'inputs_verified.json').read_text(encoding='utf-8'));require(inputs['passed'] is True,'inputs not verified')
    records=verify_stage_data(stage,registered,payloads,allow_preflight=allow_preflight)
    require(all(r['result']['input_manifest_sha256']==inputs['expected_manifest_sha256'] and r['args']['model_revision']==inputs['model_revision'] for r in records),'result differs from verified input provenance')
    return stage,registered,payloads,records

def build_summary(stage,records,*,allow_preflight=False):
    baselines={};groups={}
    for row in records:
        c=row['args'];groups.setdefault((c['mode'],c['selection'],c['samples']),[]).append(row)
        if c['mode'] in ('sdpa','digital_sdpa','digital_exact'):
            if c['mode'] in baselines:require(allow_preflight and baselines[c['mode']]['args']['seed']==c['seed'] and baselines[c['mode']]['result']['nll_sum']==row['result']['nll_sum'],'ambiguous/repeated digital reference')
            else:baselines[c['mode']]=row
    groups_out=[]
    for (mode,selection,samples),original in sorted(groups.items()):
        rows=[];seen=set()
        for row in sorted(original,key=lambda r:r['args']['seed']):
            seed=row['args']['seed']
            if seed in seen:require(allow_preflight and mode=='sdpa','duplicate group seed');continue
            seen.add(seed);rows.append(row)
        values=[r['result']['perplexity'] for r in rows];count=sum(r['result']['scored_tokens'] for r in rows);nll=math.fsum(r['result']['nll_sum'] for r in rows)/count
        totals=[r['result']['sampling_stats']['totals'] if r['result']['sampling_stats'] else None for r in rows]
        layers=[s for r in rows if r['result']['sampling_stats'] for s in r['result']['sampling_stats']['layers'].values()];complete=all(t is not None for t in totals)
        item=dict(mode=mode,selection=selection,samples=samples,effective_samples=samples if mode in SAMPLED else None,role='bridge_diagnostic' if mode=='ising_only' or selection!='fixed' else 'primary',seeds=[r['args']['seed'] for r in rows],ppl_mean=statistics.mean(values),ppl_seed_population_sd=statistics.pstdev(values),mean_nll=nll,ppl_geometric_mean=math.exp(nll),scored_tokens_per_seed=rows[0]['result']['scored_tokens'],runs=len(original),independent_seed_count=len(rows),selected_fraction_mean=statistics.mean(t['selected_fraction'] for t in totals) if complete else None,GQA_union_fraction_mean=statistics.mean(t['GQA_union_fraction'] for t in totals) if complete else None,selected_candidates_min=min(s['candidate_min'] for s in layers) if layers else None,selected_candidates_max=max(s['candidate_max'] for s in layers) if layers else None,selected_candidates_mean=statistics.mean(t['selected_candidates']/t['query_rows'] for t in totals) if complete else None,adjacent_repeat_fraction_mean=statistics.mean(t['adjacent_repeat_fraction'] for t in totals) if complete and mode in SAMPLED else None,adjacent_repeat_fraction_pooled=math.fsum(t['adjacent_repeats'] for t in totals)/math.fsum(t['adjacent_pairs'] for t in totals) if complete and mode in SAMPLED and samples>1 else None,cumulative_metrics_by_seed=[dict(seed=r['args']['seed'],**t) for r,t in zip(rows,totals) if t is not None],ctmc_last_call_only=[dict(seed=r['args']['seed'],layer=int(layer),scope='last call of this layer only; not whole evaluation',stats=s['last_sampler_stats']) for r in rows if mode in ('screen_ising','ising_only') for layer,s in r['result']['sampling_stats']['layers'].items() if s.get('last_sampler_stats')])
        for ref,baseline in baselines.items():
            base=baseline['result'];delta=nll-base['mean_nll'];item['delta_mean_nll_vs_'+ref]=delta;item['ppl_increase_percent_vs_'+ref]=(item['ppl_mean']/base['perplexity']-1)*100;item['geometric_ppl_increase_percent_vs_'+ref]=math.expm1(delta)*100
        groups_out.append(item)
    first=records[0]['result'];case=records[0]['args'];protocol=case['protocol']
    return dict(source_commit=stage['source_commit'],stage=stage['stage'],job_id=stage['job_id'],protocol=protocol,protocol_parameters={k:case[k] for k in INVARIANTS},source_tokens=first['source_tokens'],scored_tokens_per_seed=first['scored_tokens'],token_sha256=first['token_ids_sha256_le_int64'],target_positions_sha256=first['scoring_plan']['target_positions_sha256_le_int64'],completed_cases=len(records),registered_cases=stage['registered_case_count'],groups=groups_out,full_model_layers=24,ffn='original',prefill='original multi-token SDPA',hardware_PPA_measured=False,physical_PPA=None,model_weights_unchanged=True,model_state_sha256=stage['model_state_before_sha256'],input_manifest_sha256=first['input_manifest_sha256'],model_revision=case['model_revision'],publishable=stage['stage'] in ('sweep','full_confirm'),scope='fixed WT2 suffix targets, not full WT2' if protocol=='suffix' else 'all WT2 targets exactly once; cached window scorer; matched cached SDPA comparison',statistics_scope='PPL arithmetic mean and population SD across recorded inference seeds; geometric PPL=exp(token-weighted mean NLL); seed SD is not corpus confidence',rng_scope='same inputs/targets/batch/step order; per-layer streams exclude S/backend; CTMC samples need not be independent',memory_scope='GQA union fraction is logical candidate-address union, not physical DRAM/energy saving',ctmc_scope='adjacent repeats/pairs/sample counts are cumulative; ctmc_last_call_only is final call per layer; no whole-run event/ESS/mixing estimate; CTMC time is not ns',case_files=[dict(case_id=r['case_id'],sha256=r['sha256']) for r in records])

def markdown(info):
    c=info['protocol_parameters']
    if info['protocol']=='suffix':protocol=f'每 seed 计分 {info["scored_tokens_per_seed"]} 个固定 WT2 后缀目标，{c["examples"]} 段×{c["decode"]} 目标，初始 context={c["context"]}，实际 KV 长度 {c["context"]}..{c["context"]+c["decode"]-1}；不是完整 WT2。'
    else:protocol=f'完整 WT2 共 {info["source_tokens"]} tokens，位置 1 至末尾共 {info["scored_tokens_per_seed"]} 个目标各计一次，context={c["context"]}/stride={c["stride"]}。这是 cached 窗口计分协议；比值只对匹配 cached SDPA，旧 vectorized BF16 anchor 不作为数值相同的对照。'
    lines=['# 联合概率 QK 筛选＋有限时间 Ising：采样数与 PPL','',f'执行源 `{info["source_commit"]}`；Slurm {info["job_id"]}；{info["completed_cases"]}/{info["registered_cases"]} 项完成。原始成果 SHA、每段几何、目标 SHA、加权 NLL 与模型前后 SHA 已核验。','原 FFN 与投影，全部 24 层 decode，原始 SDPA 多 token prefill。'+protocol,f'burn={c["burn"]} / spacing={c["spacing"]}；固定预算 {c["budget_blocks"]} 块，每块 64，最多 {c["budget_blocks"]*64} 候选，末尾块按实际长度计。','']
    for role,title in (('primary','主比较'),('bridge_diagnostic','桥接与诊断（无筛选 Ising / 变量预算）')):
        rows=[r for r in info['groups'] if r['role']==role]
        if not rows:continue
        lines += ['## '+title,'','| 模式 | 预算 | 有效 S | seed 数 | PPL 算术均值 ± seed SD | 相对匹配原 SDPA |','|---|---|---:|---:|---:|---:|']
        for r in rows:
            budget='无筛选' if r['mode']=='ising_only' else f'{c["target_fraction"]:.0%} variable' if r['selection']=='variable' else f'{c["budget_blocks"]} blocks' if r['mode'].startswith('screen_') else '全候选'
            lines.append(f'| {r["mode"]} | {budget} | {r["effective_samples"] if r["effective_samples"] is not None else "—"} | {len(r["seeds"])} | {r["ppl_mean"]:.6f} ± {r["ppl_seed_population_sd"]:.6f} | {r["ppl_increase_percent_vs_sdpa"]:+.3f}% |')
        lines+=['']
    lines+=['## 候选与采样统计','','| 模式 | 预算 | S | 每 query-head 候选 min / mean / max | 筛选比例 | GQA 逻辑并集比例 | 全程相邻重复率 |','|---|---|---:|---:|---:|---:|---:|']
    for r in info['groups']:
        if r['selected_candidates_mean'] is None:continue
        repeat=r['adjacent_repeat_fraction_pooled']
        lines.append(f'| {r["mode"]} | {r["selection"] if r["mode"]!="ising_only" else "无筛选"} | {r["effective_samples"] if r["effective_samples"] is not None else "—"} | {r["selected_candidates_min"]} / {r["selected_candidates_mean"]:.3f} / {r["selected_candidates_max"]} | {r["selected_fraction_mean"]:.3%} | {r["GQA_union_fraction_mean"]:.3%} | {format(repeat,".3%") if repeat is not None else "—"} |')
    lines+=['','候选均值来自全程 selected_candidates/query_rows，极值覆盖各层各 seed，比例由累计计数核验。GQA 并集仅是逻辑候选地址并集，不代表实际 DRAM 流量或能耗节省。','','误差为表中实际 seed 数的总体标准差，单 seed 的 0 SD 不表示无随机误差；seed SD 不是数据集置信区间。手写 FP32 与 BF16 fused SDPA 分列；未使用采样的对照显示 S=—，原 samples 配置仍保留。','','JSON 另列 exp(加权平均 NLL) 与基于 NLL 的几何 PPL 增幅，和表中 PPL 算术均值及增幅定义不同。所有对照的目标、上下文、批次顺序相同。','','全程 adjacent_repeats/adjacent_pairs 可核验；ctmc_last_call_only 仅为每层最后一次调用，不能当全场事件数、混合时间或 ESS。CTMC 过程时间不是物理 ns。','','桥接项单列；用户尚未指定接受阈值。不据测试集最佳点声称独立泛化优势，GPU 耗时不作 ASIC 延迟、功率或能量。','']
    return '\n'.join(lines)

def summarize(source,output):
    output=Path(output);require(not output.exists(),'refusing to overwrite existing report directory')
    stage,_,_,records=load_verified(source);info=build_summary(stage,records);report=markdown(info)
    output.mkdir(parents=True) # No output is created until all validation succeeds.
    (output/'summary.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    fields=list(dict.fromkeys(k for row in info['groups'] for k in row))
    with (output/'summary.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        writer.writerows({k:json.dumps(v,ensure_ascii=False,separators=(',',':')) if isinstance(v,(list,dict)) else v for k,v in row.items()} for row in info['groups'])
    (output/'RESULTS_ZH.md').write_text(report,encoding='utf-8',newline='\n');return info

def self_check(source):
    """Internal schema checks; no pilot quality output or files."""
    stage,registered,payloads,records=load_verified(source,allow_preflight=True)
    require(stage['stage']=='gpu_preflight','self-check expects saved GPU preflight')
    info=build_summary(stage,records,allow_preflight=True)
    require(not info['publishable'] and '不是完整 WT2' in markdown(info),'pilot/suffix label guard')
    rejected=[];first=registered[0]['case_id']
    def reject(name,mutate):
        s,r,p=copy.deepcopy((stage,registered,payloads));mutate(s,r,p)
        try:verify_stage_data(s,r,p,allow_preflight=True)
        except (ValueError,KeyError):rejected.append(name)
        else:raise ValueError('negative check unexpectedly accepted: '+name)
    reject('missing_model_hashes',lambda s,r,p:s.update(model_state_before_sha256=None,model_state_after_sha256=None))
    reject('incorrect_mean_nll',lambda s,r,p:p[first].update(mean_nll=p[first]['mean_nll']+.001))
    reject('incorrect_target_hash',lambda s,r,p:p[first]['scoring_plan'].update(target_positions_sha256_le_int64='0'*64))
    reject('changed_target_geometry',lambda s,r,p:p[first]['examples'][0].update(first_target=p[first]['examples'][0]['first_target']+1))
    reject('case_mode_mismatch',lambda s,r,p:p[first]['args'].update(mode='screen_iid'))
    reject('mislabeled_full_stage',lambda s,r,p:s.update(stage='full_confirm'))
    reject('missing_layer_audit',lambda s,r,p:p[first]['execution_audit'].update(decode_calls_per_layer=[0]*24))
    ising=next(r for r in info['groups'] if r['mode']=='screen_ising')
    require(len(ising['ctmc_last_call_only'])==24 and ising['selected_candidates_min']<=ising['selected_candidates_mean']<=ising['selected_candidates_max'],'candidate/last-call extraction')
    near(ising['adjacent_repeat_fraction_pooled'],ising['adjacent_repeat_fraction_mean'],'single-seed repeats',1e-12)
    # Synthetic full-confirm schema check, explicitly not experimental data.
    fs,fr,fp=copy.deepcopy((stage,registered[:1],{first:payloads[first]}));data=fp[first]
    fs.update(stage='full_confirm',cases=copy.deepcopy(stage['cases'][:1]),registered_case_count=1,source_tokens=17)
    for c in (fr[0],data['args']):c.update(protocol='full',context=8,stride=4,decode=4,examples=1,batch=2)
    data.update(protocol='full',source_tokens=17);plan,positions=expected_plan(data['args'],17)
    data['examples']=[dict(row,start_token=row['begin'],first_target_token=row['first_target'],last_target_token=row['last_target_exclusive']-1,nll_sum=float(row['scored_tokens']),token_ids_sha256_le_int64='1'*64,target_positions_sha256_le_int64=ids_sha(range(row['first_target'],row['last_target_exclusive']))) for row in plan]
    data['scoring_plan']=dict(protocol='full',source_tokens=17,scored_tokens=16,target_positions_sha256_le_int64=ids_sha(positions),every_full_corpus_target_once=True,segment_starts=[r['begin'] for r in plan],segments=plan)
    data.update(scored_tokens=16,nll_sum=16.,mean_nll=1.,perplexity=math.e);dc,pc=expected_calls(plan,2)
    data['execution_audit'].update(decode_calls_per_layer=[dc]*24,prefill_calls_per_layer=[pc]*24,scored_query_tokens=16)
    fs['cases'][0].update(protocol='full',scored_tokens=16,perplexity=math.e)
    full=build_summary(fs,verify_stage_data(fs,fr,fp));require(full['publishable'] and full['scored_tokens_per_seed']==16 and 'cached 窗口计分协议' in markdown(full),'full-confirm path/label')
    try:verify_stage_data(stage,registered,payloads)
    except ValueError:rejected.append('preflight_publication')
    else:raise ValueError('pilot unexpectedly publishable')
    return dict(passed=True,source_stage=stage['stage'],validated_cases=len(records),validated_groups=len(info['groups']),rejected_invalid_cases=rejected,synthetic_full_confirm_checked=True,output_files_written=0,scope='internal checks only; no pilot quality report')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source');parser.add_argument('--output');parser.add_argument('--self-check-source');args=parser.parse_args()
    if args.self_check_source:
        require(not args.source and not args.output,'self-check accepts no publication output');print(json.dumps(self_check(args.self_check_source),ensure_ascii=False))
    else:
        require(args.source and args.output,'--source and --output are required');result=summarize(args.source,args.output)
        compact={k:result[k] for k in ('job_id','completed_cases','scored_tokens_per_seed')}
        compact['groups']=[{k:g[k] for k in ('mode','selection','samples','seeds','ppl_mean','ppl_seed_population_sd','ppl_increase_percent_vs_sdpa')} for g in result['groups']]
        print(json.dumps(compact,ensure_ascii=False))
