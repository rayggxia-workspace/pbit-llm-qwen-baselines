"""Rebuild the result tables from small sealed evidence, without model inference."""
from pathlib import Path
import csv
import hashlib
import json
import math
import statistics

HERE=Path(__file__).resolve().parent
E=HERE/'evidence'


def read(p):
    raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==p.with_suffix('.sha256').read_text().strip()
    return json.loads(raw)


def save(p,v):
    raw=(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    p.write_bytes(raw);p.with_suffix('.sha256').write_bytes((hashlib.sha256(raw).hexdigest()+'\n').encode())


def csv_file(name,rows):
    with (HERE/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)


def main():
    s4=read(E/'S4_COMPLETE.json');half=read(E/'S2_S4_PILOT.json')
    tasks=read(E/'TASK_SUMMARY.json');verified=read(E/'TASK_VERIFICATION.json')
    lane=read(E/'PREVIOUS_LANE_COMPLETE.json');lab=read(E/'LAB_VERIFICATION.json')
    assert s4['status']==half['status']==tasks['status']=='completed'
    assert verified['status']==lab['status']=='verified'
    assert verified['configuration_document_pairs']==27090
    assert (tasks['completed_parts'],tasks['completed_groups'])==(225,18)
    assert s4['identity']==half['identity']==tasks['T64_identity']
    assert lane['protocol_and_model']['export_manifest_sha256']==s4['identity']['export_manifest_sha256']
    assert lane['protocol_and_model']['test_text_sha256']==s4['protocol']['text_sha256']
    assert lane['protocol_and_model']['test_token_sha256']==s4['protocol']['token_sha256']
    assert len(s4['full'])==6 and len(half['rows'])==8 and len(tasks['groups'])==18
    labels={'lane':'原逐元素四档（同预算对照）','dynamic32':'x/g/u动态32共享单尺度',
            'gu_onebit64':'x原四档；g/u64共享基准＋1bit',
            'all64_onebit':'x动态64共享；g/u64共享基准＋1bit'}
    task_rows=[]
    grouped={(x['case']['id'],x['task']):x for x in tasks['groups']}
    for case_id in ['BF16']+[f'{p}_{tx}_{ta}' for tx,ta in [(16,32),(64,128)] for p in labels]:
        case=next(x['case'] for x in tasks['groups'] if x['case']['id']==case_id)
        row=dict(case=case_id,policy='原预训练BF16参考' if case_id=='BF16' else labels[case['policy']],
                 budget='—' if case_id=='BF16' else f'{case["T_x"]}/{case["T_and"]}')
        for name in ['piqa','arc_challenge']:
            g=grouped[(case_id,name)]
            assert g['documents']=={'piqa':1838,'arc_challenge':1172}[name]
            for key in ['acc','acc_norm']:
                row[name+'_'+key+'_pct']=100*g['metrics'][key+',none']
                if case_id!='BF16':
                    ref=grouped[(f'lane_{case["T_x"]}_{case["T_and"]}',name)]
                    row[name+'_'+key+'_delta_pp_vs_lane']=100*(g['metrics'][key+',none']-ref['metrics'][key+',none'])
                else:row[name+'_'+key+'_delta_pp_vs_lane']=None
        task_rows.append(row)
    csv_file('TASK_ACCURACY.csv',task_rows)
    pilot=[]
    for tx,ta in [(16,32),(64,128)]:
        for policy in ['gu_onebit64','all64_onebit']:
            rows={x['case']['step_bits']:x['result'] for x in half['rows'] if x['case']['T_x']==tx and x['case']['scale_policy']==policy}
            p4,p2=rows[2]['ppl'],rows[1]['ppl']
            row=dict(policy=policy,budget=f'{tx}/{ta}',S4_PPL=p4,S2_PPL=p2,S2_change_pct=100*(p2/p4-1))
            for bits,name in [(2,'S4'),(1,'S2')]:
                stats=rows[bits]['scale_statistics'];wd=stats['integer_backend']['Wd']
                row[name+'_within_group_product_span']=stats['group_scales']['within_group_product_exponent_span_max']
                row[name+'_backend_alignment_bits']=wd['max_alignment_bits']
                row[name+'_observed_symmetric_signed_bits']=wd['max_observed_symmetric_signed_bits']
                row[name+'_conservative_bound_signed_bits']=wd['max_conservative_bound_signed_bits']
            pilot.append(row)
    csv_file('S2_S4_PILOT_AND_WIDTH.csv',pilot)
    full=[]
    for tx,ta in [(16,32),(64,128)]:
        old=[x for x in lane['results'] if x['case']==f'lane{tx}_{ta}']
        policy='gu_onebit64' if tx==16 else 'all64_onebit'
        new=[x['result'] for x in s4['full'] if x['case']['id']==f'{policy}_{tx}_{ta}']
        assert {x['seed'] for x in old}=={x['seed'] for x in new}=={101,202,303}
        oldmean=statistics.mean(x['ppl'] for x in old)
        for label,rows in [('原逐元素四档',old),(labels[policy],new)]:
            vals=[x['ppl'] for x in sorted(rows,key=lambda x:x['seed'])]
            assert all(x['targets']==299077 and x['windows']==292 for x in rows)
            full.append(dict(policy=label,budget=f'{tx}/{ta}',seed101=vals[0],seed202=vals[1],seed303=vals[2],
                             mean_PPL=statistics.mean(vals),SD=statistics.stdev(vals),delta_pct_vs_lane=100*(statistics.mean(vals)/oldmean-1)))
    csv_file('COMPLETE_WT2.csv',full)
    combined=dict(status='verified_completed',model='Qwen/Qwen3-4B trained100M T64 W8/native non_ffn',
        attention='accurate SDPA throughout; no QKVO overlay or sampled Attention',
        full_WT2=full,S2_S4_subset=pilot,task_accuracy=task_rows,
        protocols=dict(full='292 windows;2048/1024;299077 targets;seeds101/202/303',
                       subset='8 dispersed windows;9215 targets;seed101',
                       tasks='PIQA1838+ARC-C1172;official lm-eval0.4.8;zero-shot;seed101;full prompt/answer FFN;no chat template/truncation'),
        identity=s4['identity'],code_commits=dict(S4=s4['source']['git_commit'],S2=half['source']['git_commit'],tasks=tasks['provenance']['source']['git_commit']),
        no_new_training=True,no_new_PPA_or_TLM_default=True,active_jobs=0,
        boundaries=['S2 has no complete WT2 or task results in this batch','task accuracy is one deployment seed, not multi-training-seed confidence',
                    'observed/backend bound widths are numerical diagnostics, not RTL minimum widths',
                    'BF16 is original pretrained reference; same-budget T64 lane isolates scale changes'])
    save(HERE/'SUMMARY.json',combined)
    text=['# T64共享尺度：三批任务最终结果','',
          '2026-11-26，Issue225／PR266。三批已提交任务全部完成；5090两批共6个新完整WT2结果及8个小测结果，学院准确率225/225分片、18/18完整配置。已核验原字节SHA、逐窗／逐题记录、模型／输入身份及36层覆盖。当前本批GPU队列为空。',
          '','## 结论','',
          'S/S2的四种8窗配置均优于同轮S/S4，Wd后端最大实际观测位宽也降低1～2bit。S2值得优先补完整质量验证；本批没有S2完整WT2或任务准确率。',
          '',
          'S/S4的64/128方案支持较简洁的共享尺度：x也动态64共享、g/u加1bit时，完整WT2为8.98949，相对原四档8.97555增加0.155%；两任务acc相对同预算原四档为PIQA +0.979个百分点、ARC-C −0.427个百分点。16/32仍有明显任务质量代价，纯动态32共享尤其不合适。',
          '','## 1. 两个完整任务：准确率','',
          'PIQA完整validation1838题、ARC-Challenge完整test1172题。表中为百分比。固定T64/W8及其原non_ffn、准确SDPA；单seed101。所有题干和答案位置均使用所选FFN，官方lm-eval0.4.8零样本，不套聊天模板、不截断。这里的1bit小档均为S/S4，不能继承为S2成绩。',
          '','|预算 GU/Wd|尺度规则|PIQA acc|PIQA acc_norm|ARC-C acc|ARC-C acc_norm|',
          '|---|---|---:|---:|---:|---:|']
    for z in task_rows:
        text.append(f'|{z["budget"]}|{z["policy"]}|{z["piqa_acc_pct"]:.2f}|{z["piqa_acc_norm_pct"]:.2f}|{z["arc_challenge_acc_pct"]:.2f}|{z["arc_challenge_acc_norm_pct"]:.2f}|')
    text += ['',
             '主尺度比较采用相同T64、相同采样预算的原四档对照。原预训练BF16只作参考；T64经过100M token继续训练，不能把相对原BF16的变化全归因于采样。单部署seed不提供跨seed置信结论。',
             '','## 2. S/S2与S/S4：8窗单seed PPL','',
             '同8个分散窗口、9215目标、seed101。每一项S4逐窗结果与原封存S4完全匹配；新S4包装器logits逐位一致，S2重复一致及新完整BF16参考通过。',
             '','|预算|x规则|S/S4 PPL|S/S2 PPL|变化|','|---|---|---:|---:|---:|']
    for z in pilot:
        text.append(f'|{z["budget"]}|'+('原四档' if z['policy']=='gu_onebit64' else '动态64共享')+f'|{z["S4_PPL"]:.6f}|{z["S2_PPL"]:.6f}|{z["S2_change_pct"]:+.3f}%|')
    text += ['','两条路径的g/u都采用64共享动态PoT基准＋逐元素1bit；本节只改变小档S/4→S/2及对应阈值，保持P8、真实幅度sigmoid、前级共享R8分层、联合AND计数直连Wd及W8整数恢复。小测结果不能直接当完整WT2。',
             '','## 3. 整数范围：/2究竟缩了多少','',
             '|预算|x规则|组内g×u指数跨度 S4→S2|Wd后端最大对齐位 S4→S2|Wd实际观测对称位宽 S4→S2|Wd保守界位宽 S4→S2|',
             '|---|---|---:|---:|---:|---:|']
    for z in pilot:
        cells=[f'{z["S4_"+k]}→{z["S2_"+k]}' for k in ['within_group_product_span','backend_alignment_bits','observed_symmetric_signed_bits','conservative_bound_signed_bits']]
        text.append('|'+z['budget']+'|'+('原四档' if z['policy']=='gu_onebit64' else '动态64共享')+'|'+'|'.join(cells)+'|')
    text += ['','组内档间对齐从0/2/4位收窄到0/1/2位；低预算实测34→32bit，高预算35/36→34bit。全投影软件后端的保守范围仍为53～56bit，因为还包含组间基准、权重指数、K和计数长度。这些是本次输入的数值范围及后端保守界，不是已经综合的RTL最小位宽；本轮不将64bit状态统一改为32bit。',
             '','## 4. S/S4完整WT2：三部署seed','',
             '每seed292窗、299077目标，window2048/stride1024，原文无模板，36层。±为三个部署seed的样本标准差；同预算原四档引用已封存完整结果，模型／语料身份与本轮新pilot逐字回放核对一致。',
             '','|预算|规则|完整PPL均值±SD|相对同预算原四档|','|---|---|---:|---:|']
    for z in full:text.append(f'|{z["budget"]}|{z["policy"]}|{z["mean_PPL"]:.6f} ± {z["SD"]:.6f}|{z["delta_pct_vs_lane"]:+.3f}%|')
    text += ['',
             f'本轮5090原BF16完整参考：{s4["baseline_full_WT2"]["ppl"]:.6f}；学院A6000同协议参考：{tasks["provenance"]["protocol"]["targets"]}目标、11.536429。硬件／软件环境分别保留，不将两环境分片拼成同一完整结果。',
             '','## 5. 完成与复核证据','',
             '- 原S4：数值源7283f04157ff6cdb3d526271766ed64eb5db4461，5090实际作业6361（显示6355_5），退出0，6个完整三seed结果均封存。',
             '- S2对照：数值源90b7742ac88beeb95203ab600c5a78adac809bf4，CPU6379十四项PASS、5090实际6387（6380_6），退出0，8个小测结果均封存。',
             '- 任务：数值源ea293caea14b8ec5b271a937919ae21693ccae9c，CPU62231／GPU Gate62228通过，四worker62229_0～3及汇总62230全部COMPLETED/0:0。各worker约129～130分钟，合计8.622 GPU小时，不含独立Gate。',
             '- 独立CPU62235用verify_tasks.py重新读取450份分片／官方逐题JSON，核对原文档SHA、输入ledger、模型／源码身份，重算27090个配置×题目计分；18组与原汇总完全一致。原始唯一题为3010道，配置×题目记录不是独立文本样本量。',
             '- LAB_VERIFICATION和TASK_VERIFICATION含原件SHA索引。大逐题文本和原执行快照留原共享存储；Git只存小型原字节汇总／索引。两个小归档在项目project_archives/scale_results225_20261126，确切恢复位置见个人HANDOFF。',
             '- 本轮无新训练、RTL／PPA或TLM默认修改；PR266保持未合并。没有S2任务准确率或完整WT2，未自动新增任务。',
             '',
             '重新生成：在本目录运行python build_report.py，仅从evidence读小型封存汇总，不运行大模型。重新核验逐题原件需原共享存储及python verify_tasks.py ROOT OUTPUT，通过CPU Slurm执行。']
    with (HERE/'REPORT_ZH.md').open('w',encoding='utf-8',newline='\n') as f:f.write('\n'.join(text)+'\n')
    print(json.dumps(dict(status='completed',full_rows=len(full),pilot_rows=len(pilot),task_rows=len(task_rows))))


if __name__=='__main__':main()
