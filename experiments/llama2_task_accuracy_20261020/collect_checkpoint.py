"""Read-only Issue73 checkpoint; never starts/restarts model jobs.

This checks sealing, hashes, scoring coverage and stored metric aggregation.
It does not independently replay official task.process_results; final quality
delivery must add that separate check against the pinned original datasets.
"""
import argparse,datetime,hashlib,json,math,statistics,subprocess
from pathlib import Path

OLD='022db6828c0caba96ae3d620f80b27c1ae3774b9'
PACKED='309ca9c1629c364142ffdce474d5f6138da929c1'
OLD_INDICES={0,4,5,6,13,17,18,19}
COUNTS={'piqa':1838,'arc_easy':2376}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def unique(pairs):
    d={}
    for k,v in pairs:
        if k in d:raise ValueError('duplicate JSON key '+k)
        d[k]=v
    return d


def loads(text):return json.loads(text,object_pairs_hook=unique)


def require(condition,message):
    if not condition:raise ValueError(message)


def checked_result(path,task,cfg,commit,metadata,requests):
    x=loads(path.read_text())
    require(x['status']=='completed','not sealed')
    require(x['task']==task and x['configuration']==cfg and x['code_commit']==commit,'result identity')
    require(x['configuration_sha256']==hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),'configuration SHA')
    for k in ['task_data_sha256','identity_sha256']:
        require(x[k]==metadata[k],k)
    require(x['n_documents']==COUNTS[task],'document count')
    artifact=x['document_artifact'];p=path.with_suffix('.documents.jsonl')
    require(str(p)==artifact['path'] and p.stat().st_size==artifact['bytes'] and sha(p)==artifact['sha256'],'documents seal')
    b=p.read_bytes();require(b.endswith(b'\n') and b'\r' not in b,'archived LF bytes')
    docs=[loads(line) for line in b.decode('utf-8').splitlines()]
    require(len(docs)==COUNTS[task] and {d['doc_id'] for d in docs}==set(range(COUNTS[task])),'missing/duplicate documents')
    by_id={d['id']:d for d in requests};tokens=0;metrics={'acc':[],'acc_norm':[]}
    for d in docs:
        require(d['id']==task+':'+str(d['doc_id']) and d['task']==task,'document task/id')
        req=by_id[d['id']];require(len(d['choices'])==len(req['choices_ids']),'missing choice')
        for c,answer in zip(d['choices'],req['choices_ids']):
            require(type(c['tokens']) is int and c['tokens']==len(answer)>0,'choice tokens')
            require(type(c['is_greedy']) is bool and math.isfinite(c['logprob']) and c['logprob']<=1e-5,'choice likelihood')
            tokens+=c['tokens']
        for k in metrics:
            require(d['metrics'][k] in (0.,1.),'nonbinary metric');metrics[k].append(d['metrics'][k])
    for k,values in metrics.items():
        require(abs(sum(values)/len(values)-x['metrics'][k])<1e-12,'metric aggregation '+k)
    a=x['execution_audit'];decode=a['actual_decode_calls'];prefill=a['actual_prefill_calls']
    require(a['every_scored_target_used_32_decode_layers'] is True,'scored 32-layer guard')
    for prefix,n in [('attention_decode',decode),('ffn_decode',decode),('attention_prefill',prefill),('ffn_prefill',prefill)]:
        require(a[prefix+'_calls_per_layer']==[n]*32,'layer calls '+prefix)
    require(a['actual_decode_query_rows']==a['shared_first_query_rows']+a['branch_query_rows']+a['dummy_query_rows'],'dummy query accounting')
    require(a['original_tokenized_requests']==a['scored_choice_tokens']==tokens,'scored target coverage')
    require(a['completed_documents']==COUNTS[task] and a['shared_first_query_rows']==COUNTS[task],'complete scored documents')
    if cfg['mode']!='sdpa':
        s=x['sampling_stats'];active=x['active_sampling_stats']
        require(set(s['layers'])==set(map(str,range(32))),'32 attention layers')
        for layer in s['layers'].values():
            require(layer['decode_calls']==decode and layer['prefill_calls']==prefill,'attention audit')
        require(s['totals']['query_token_rows']==a['actual_decode_query_rows']*32,'attention total query audit')
        require(active['query_token_rows']==(a['shared_first_query_rows']+a['branch_query_rows'])*32,'active vs dummy audit')
    if cfg['ffn']!='none':
        require(set(x['ffn_stats'])==set(map(str,range(32))),'32 FFN layers')
        require(all(v['calls']==decode+prefill for v in x['ffn_stats'].values()),'FFN calls')
    return dict(path=str(path),sha256=sha(path),bytes=path.stat().st_size,documents=artifact,
        metrics=x['metrics'],elapsed_seconds=x['elapsed_seconds'],configuration_sha256=x['configuration_sha256'],
        code_commit=commit,slurm_job_id=x['slurm_job_id'],scored_tokens=tokens,decode_calls=decode,
        metadata_and_32_layers_verified=True,stored_metrics_reaggregated=True,official_metric_oracle_recomputed=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    project=Path(args.project).resolve(strict=True)
    require(str(project)=='/home/Hongjie_Zeng/projects/pbit-llama2-task-accuracy-20261020-issue73','personal project')
    metadata={};request_sets={};provenance={};suites={}
    for commit in [OLD,PACKED]:
        out=project/'outputs'/commit;snap=project/'snapshots'/commit
        ready=loads((out/'READY.json').read_text());meta=loads((out/'TASK_DATA.json').read_text());identity=loads((out/'identity.json').read_text())
        require(ready['code_commit']==meta['code_commit']==commit,'execution commit')
        require(ready['baseline_gate_passed'] and ready['bf16_task_bridge_passed'],'GPU gates')
        for name,key in [('TASK_DATA.json','task_data_sha256'),('identity.json','identity_sha256'),('suite.json','suite_sha256')]:
            require(sha(out/name)==ready[key],name+' SHA')
        require(meta['source_sha256']==ready['source_sha256'],'source metadata mismatch')
        for name,h in ready['source_sha256'].items():require(sha(snap/name)==h,'source byte SHA '+name)
        require(identity['revision']=='01c7f73d771dfac7d292323805ebc428287df4f9' and identity['model_shape']['num_hidden_layers']==32,'model revision/shape')
        requests={}
        for task in COUNTS:
            entry=meta['tokenized'][task];path=Path(entry['path']);require(sha(path)==entry['sha256'],'tokenized input SHA')
            requests[task]=[loads(line) for line in path.read_text().splitlines()]
            task_entry=meta['tasks'][task];require(sha(task_entry['dataset_path'])==task_entry['dataset_sha256'],'dataset SHA')
            require(sha(task_entry['task_yaml'])==task_entry['task_yaml_sha256'],'task YAML SHA')
        for path,h in meta['harness_sources'].items():require(sha(path)==h,'Harness source SHA')
        metadata[commit]=ready;request_sets[commit]=requests;suites[commit]=loads((out/'suite.json').read_text())
        provenance[commit]=dict(READY=dict(sha256=sha(out/'READY.json'),path=str(out/'READY.json')),
            task_data_sha256=ready['task_data_sha256'],identity_sha256=ready['identity_sha256'],suite_sha256=ready['suite_sha256'],
            source_files_verified=len(ready['source_sha256']),model_identity=identity,
            model_weight_files_rehashed=False,model_identity_scope='pinned manifest and preflight binding; no repeat hash of 14GB checkpoint',
            input_files={k:meta['tokenized'][k] for k in COUNTS})
    require(suites[OLD]==suites[PACKED],'suite changed after storage repair')
    for task in COUNTS:require(request_sets[OLD][task]==request_sets[PACKED][task],'requests changed')
    suite=suites[OLD];require(len(suite['configurations'])==13 and suite['tasks']==list(COUNTS),'26-case frozen plan')
    queue=subprocess.run(['/opt/slurm/21.08.8/bin/squeue','-r','-h','-u','Hongjie_Zeng','-o','%i|%T|%M|%S|%R'],capture_output=True,text=True,check=True).stdout
    queued={}
    for line in queue.splitlines():
        parts=line.split('|');job=parts[0]
        if job.startswith('2585_'):
            queued[int(job.split('_')[1])]=dict(job=job,state=parts[1],runtime=parts[2],start=parts[3],reason=parts[4])
    rows=[]
    for index in range(26):
        task=suite['tasks'][index//13];cfg=suite['configurations'][index%13];commit=OLD if index in OLD_INDICES else PACKED
        path=project/'outputs'/commit/'full'/(task+'_'+cfg['name']+'.json')
        item=dict(index=index,task=task,configuration=cfg,expected_commit=commit)
        if path.exists():
            try:item.update(status='completed',**checked_result(path,task,cfg,commit,metadata[commit],request_sets[commit][task]))
            except (ValueError,KeyError,OSError) as e:item.update(status='invalid_result',error=str(e),path=str(path))
        else:
            q=queued.get(index);item['status']=q['state'].lower() if q else 'missing';item['queue']=q
            progress=path.with_suffix('.progress.jsonl')
            item['progress_documents_unsealed']=sum(1 for _ in progress.open()) if progress.exists() else 0
        rows.append(item)
    counts={s:sum(r['status']==s for r in rows) for s in sorted({r['status'] for r in rows})}
    groups=[]
    for task in COUNTS:
        baseline=next((r for r in rows if r['task']==task and r['configuration']['name']=='bf16' and r['status']=='completed'),None)
        for group in ['ffn_only','attention_S128','joint_S128','joint_S512']:
            members=[r for r in rows if r['task']==task and r['configuration']['name'].startswith(group+'_s')]
            got=[r for r in members if r['status']=='completed']
            g=dict(task=task,group=group,completed_seeds=len(got),expected_seeds=3,metrics=None,delta_from_matched_bf16_pp=None)
            if len(got)==3 and baseline:
                g['metrics']={k:dict(mean=statistics.mean(r['metrics'][k] for r in got),population_sd=statistics.pstdev(r['metrics'][k] for r in got)) for k in ['acc','acc_norm']}
                g['delta_from_matched_bf16_pp']={k:100*(g['metrics'][k]['mean']-baseline['metrics'][k]) for k in ['acc','acc_norm']}
            groups.append(g)
    result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),issue=73,expected_unique_cases=26,counts=counts,
        complete=counts.get('completed',0)==26,scope='sealed results/checksums/32-layer coverage/stored metric aggregation; official metric oracle pending final collection',
        source_sha256=sha(__file__),provenance=provenance,results=rows,three_seed_groups=groups,queue_text=queue,
        prior_PR75_merged='3fe790ecc2d4849662b60216922fd45dc4300848',no_inference_or_scheduler_mutations=True)
    dest=Path(args.output);require(project in dest.resolve().parents,'output project boundary');dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(output=str(dest),sha256=sha(dest),counts=counts,utc=result['utc'])))


if __name__=='__main__':main()
