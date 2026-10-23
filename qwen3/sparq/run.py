"""Issue157: pinned post-trained Qwen3-4B, resumable paired evaluation.

Launch only through the supplied Slurm entry point. Every result has an input
identity; completed chunks are immutable and reused only after hash validation.
"""
import argparse
from dataclasses import asdict, replace
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import sys
import time

import torch
import torch.nn.functional as F

from .core import SparQConfig
from .scoring import evaluate_ppl, evaluate_tasks
from .task_data import load_tasks, token_documents, harness_sources, sha
from ..stochastic.vendor.scoring import full_window_plan, ids_sha256, summarize_records


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class Artifacts:
    def __init__(self, root, identity):
        self.root, self.identity = Path(root), identity
        self.key = fingerprint(identity)
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / 'IDENTITY.json'
        if path.exists():
            if json.loads(path.read_text()) != identity:
                raise ValueError('output belongs to a different experiment')
        else:
            save(path, identity)

    def existing(self, name):
        path = self.root / (name + '.json')
        if not path.exists():
            return None
        value = json.loads(path.read_text())
        if (value.get('experiment') != self.key
                or value.get('result_sha256') != fingerprint(value.get('result'))):
            raise ValueError('completed artifact integrity failure: ' + name)
        return value['result']

    def put(self, name, result):
        if self.existing(name) is not None:
            raise ValueError('refusing overwrite of completed result: ' + name)
        path = self.root / (name + '.json')
        # Result and integrity marker commit in a single atomic rename. A crash
        # before that rename leaves only a .tmp file, never a half-committed pair.
        save(path, dict(experiment=self.key, result=result, result_sha256=fingerprint(result),
                        job=os.environ['SLURM_JOB_ID']))

    def progress(self, phase):
        def emit(event):
            event = dict(event, phase=phase, wall_time=time.time(), job=os.environ['SLURM_JOB_ID'])
            with (self.root / 'progress.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(event, allow_nan=False) + '\n')
            if event['kind'] == 'ppl_window' or event['completed'] % 10 == 0:
                print(json.dumps({k: v for k, v in event.items() if k != 'record'}), flush=True)
        return emit


def verify_prepared(root):
    ready = json.loads((root / 'prepared/READY.json').read_text())
    if ready['model'] != 'Qwen/Qwen3-4B' or ready['revision'] != '1cfa9a7208912126459214e8b04321603b3df60c':
        raise ValueError('only the explicitly selected post-trained model is allowed')
    for row in ready['files']:
        path = root / 'model' / row['name']
        if path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('checkpoint differs from staged public revision')
    for row in ready['data']:
        if sha(row['path']) != row['sha256']:
            raise ValueError('prepared data changed')
    return ready


def source_identity():
    tree = Path(__file__).resolve().parents[2]
    manifest = json.loads((tree / 'EXECUTION.json').read_text())
    required={'qwen3/sparq/'+name for name in ('run.py','core.py','adapter.py','scoring.py',
        'task_data.py','benchmark.py','SOURCES.json','model_identity.json')}
    required.add('qwen3/stochastic/vendor/scoring.py')
    if not required.issubset(manifest['files']):
        raise ValueError('execution manifest omits required dependencies')
    for path, checksum in manifest['files'].items():
        target=(tree/path).resolve(strict=True)
        if not target.is_relative_to(tree) or sha(target) != checksum:
            raise ValueError('execution source differs: ' + path)
    return manifest


def sum_counter(stats, suffix):
    return sum(row['diagnostics'].get('logical_counts.' + suffix, 0)
               for row in stats['execution_audit']['replacement']['layers'].values())


def preflight(model, ids, documents, tasks, config):
    # Same q_len=1/cache/batch execution must be bitwise identical when delegated.
    options = dict(context=32, stride=16, batch=2, capture_logits_hash=True)
    native = evaluate_ppl(model, ids[:80], mode='native', **options)
    dense = evaluate_ppl(model, ids[:80], mode='dense', **options)
    if native['scored_logits_sha256'] != dense['scored_logits_sha256'] or native['nll_sum'] != dense['nll_sum']:
        raise RuntimeError('real-model dense wrapper changed native logits')
    strict = replace(config, validate_finite=True)
    options = dict(protocol='suffix', context=256, suffix_decode=32, suffix_examples=2,
                   batch=2, capture_logits_hash=True)
    checked = evaluate_ppl(model, ids[:1024], mode='sparq', config=strict, **options)
    fast = evaluate_ppl(model, ids[:1024], mode='sparq', config=config, **options)
    if checked['scored_logits_sha256'] != fast['scored_logits_sha256'] or sum_counter(fast, 'sparse_groups') <= 0:
        raise RuntimeError('finite-check toggle changed arithmetic or sparse path was bypassed')
    task_smoke = {}
    for name, rows in documents.items():
        a = evaluate_tasks(model, rows, mode='native', doc_limit=2, tasks=tasks)
        b = evaluate_tasks(model, rows, mode='dense', doc_limit=2, tasks=tasks)
        if a['documents'] != b['documents']:
            raise RuntimeError('official native/wrapped choice scoring mismatch')
        c = evaluate_tasks(model, rows, mode='sparq', config=config, doc_limit=2, tasks=tasks)
        task_smoke[name] = dict(native=a, dense=b, sparq=c)
    return dict(passed=True, native=native, dense=dense, strict_sparq=checked,
                production_sparq=fast, tasks=task_smoke, complete_quality_evaluation=False)


def vectorized_anchor(model, ids, out):
    name = 'ppl_vectorized_bf16'
    existing = out.existing(name)
    if existing is not None:
        return existing
    rows, started = [], time.perf_counter()
    with torch.inference_mode():
        for row in full_window_plan(len(ids)):
            part_name = 'anchor/window_' + str(row['segment_id']).zfill(4)
            record = out.existing(part_name)
            if record is None:
                tokens = ids[row['begin']:row['end']].to(model.device)[None]
                hidden = model.model(input_ids=tokens, use_cache=False).last_hidden_state
                first, end = row['first_target'] - row['begin'], tokens.shape[1]
                losses = []
                # Chunk the output projection to avoid materializing 2048*vocab logits.
                for start in range(first, end, 128):
                    stop = min(start + 128, end)
                    logits = model.lm_head(hidden[:, start - 1:stop - 1]).float()
                    losses.append(F.cross_entropy(logits.flatten(0, 1), tokens[:, start:stop].flatten(),
                                                  reduction='none').double().sum().item())
                record = dict(row, nll_sum=math.fsum(losses))
                out.put(part_name, record)
                del hidden, logits, tokens
            rows.append(record)
            out.progress(name)(dict(kind='ppl_window', completed=len(rows), total=len(full_window_plan(len(ids))), record=record))
    result = dict(**summarize_records(rows), records=rows, complete=True, scored_tokens_expected=len(ids)-1,
                  protocol='vectorized native SDPA; original FFN; 2048/1024; head projection chunks128',
                  elapsed_this_invocation_s=time.perf_counter()-started,
                  warning='anchor has different BF16 execution shapes from paired cached scorer')
    out.put(name, result)
    return result


def paired_ppl(model, ids, config, out, batch, chunk):
    plan = full_window_plan(len(ids))
    results = {}
    # Chunk-major scheduling publishes paired evidence before the whole corpus finishes.
    for start in range(0, len(plan), chunk):
        for mode in ('dense', 'sparq'):
            name = f'ppl_parts/{mode}_{start:04d}'
            if out.existing(name) is None:
                result = evaluate_ppl(model, ids, mode=mode, config=config, batch=batch,
                    segment_start=start, segment_count=min(chunk, len(plan)-start), progress=out.progress(name))
                out.put(name, result)
    for mode in ('dense', 'sparq'):
        name = 'ppl_' + mode
        results[mode] = out.existing(name)
        if results[mode] is not None:
            continue
        parts = [out.existing(f'ppl_parts/{mode}_{start:04d}') for start in range(0, len(plan), chunk)]
        records = [r for part in parts for r in part['records']]
        if len(records) != len(plan) or any(any(r[k] != expected[k] for k in expected) for r, expected in zip(records, plan)):
            raise RuntimeError('full corpus records are missing, duplicated or misaligned')
        if sum(r['scored_tokens'] for r in records) != len(ids)-1:
            raise RuntimeError('incorrect full PPL denominator')
        results[mode] = dict(**summarize_records(records), mode=mode, records=records, complete=True,
            source_tokens=len(ids), token_ids_sha256=ids_sha256(ids.tolist()),
            part_names=[f'ppl_parts/{mode}_{s:04d}' for s in range(0,len(plan),chunk)],
            total_scoring_seconds=sum(p['elapsed_seconds'] for p in parts),
            all_scored_predictors_single_query_all_layers=True,
            original_ffn=True, attention_config=asdict(config) if mode=='sparq' else None)
        out.put(name, results[mode])
    return results


def paired_tasks(model, documents, tasks, config, out, chunk):
    summary = {}
    for task_name, docs in documents.items():
        for start in range(0, len(docs), chunk):
            for mode in ('dense', 'sparq'):
                name = f'task_parts/{task_name}_{mode}_{start:05d}'
                if out.existing(name) is None:
                    result = evaluate_tasks(model, docs[start:start+chunk], mode=mode, config=config,
                                            tasks=tasks, choice_batch=4, progress=out.progress(name))
                    result['shard_complete'] = result['complete']
                    result['complete'] = False
                    result['scope'] = 'contiguous_task_shard; only final task summary can claim full completion'
                    result['full_task_documents'] = len(docs)
                    result['shard_start'] = start
                    out.put(name, result)
        summary[task_name] = {}
        for mode in ('dense', 'sparq'):
            name = f'task_{task_name}_{mode}'
            result = out.existing(name)
            if result is None:
                names = [f'task_parts/{task_name}_{mode}_{s:05d}' for s in range(0, len(docs), chunk)]
                parts = [out.existing(n) for n in names]
                rows = [r for p in parts for r in p['documents']]
                if [r['id'] for r in rows] != [d['id'] for d in docs]:
                    raise RuntimeError('missing/duplicate/misordered official task scores')
                metrics = {k: math.fsum(float(r['metrics'][k]) for r in rows)/len(rows) for k in ('acc','acc_norm')}
                for row in rows:
                    if set(row['metrics']) != {'acc','acc_norm'} or any(float(v) not in (0.,1.) for v in row['metrics'].values()):
                        raise RuntimeError('unexpected official metrics')
                result = dict(task=task_name, mode=mode, documents=len(rows), complete=True, metrics=metrics,
                    binomial_standard_error={k: math.sqrt(v*(1-v)/len(rows)) for k,v in metrics.items()},
                    source_parts=names, total_scoring_seconds=sum(p['elapsed_seconds'] for p in parts),
                    original_ffn=True, protocol='official lm_eval 0.4.8 0-shot likelihood, no chat template')
                out.put(name, result)
            summary[task_name][mode] = result
    return summary


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',required=True)
    parser.add_argument('--phase',choices=('preflight','full'),default='preflight')
    parser.add_argument('--batch',type=int,default=8)
    parser.add_argument('--ppl-chunk',type=int,default=16)
    parser.add_argument('--task-chunk',type=int,default=50)
    args=parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or not os.environ.get('CUDA_VISIBLE_DEVICES'):
        raise RuntimeError('an explicit GPU Slurm allocation is required')
    root=Path(args.root).resolve(strict=True)
    if not root.is_relative_to(Path('/home/Weican_Chen')) or root.stat().st_uid != os.getuid():
        raise ValueError('task root outside verified personal storage')
    ready=verify_prepared(root)
    execution=source_identity()
    if importlib.metadata.version('transformers')!='4.51.3' or torch.cuda.device_count()!=1 or not torch.cuda.is_bf16_supported():
        raise RuntimeError('pinned runtime and exactly one allocated BF16 GPU required')
    from transformers import AutoTokenizer,AutoModelForCausalLM
    torch.manual_seed(0)
    torch.cuda.manual_seed(0)
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    torch.set_num_threads(4)
    config=SparQConfig(validate_finite=False)
    tokenizer=AutoTokenizer.from_pretrained(root/'model',local_files_only=True,trust_remote_code=False)
    ids=tokenizer((root/'data/wikitext-2/wiki.test.raw').read_bytes().decode('utf-8'),return_tensors='pt',add_special_tokens=False).input_ids[0]
    tasks,task_identity=load_tasks(root/'data')
    documents={name:token_documents(task,name,tokenizer) for name,task in tasks.items()}
    identity=dict(model=ready['model'],revision=ready['revision'],ready_sha256=sha(root/'prepared/READY.json'),
        execution=execution,config=asdict(config),seed=0,ppl=dict(context=2048,stride=1024,batch=args.batch,chunk=args.ppl_chunk),
        tasks=task_identity,task_chunk=args.task_chunk,task_tokenization_sha256=fingerprint(documents),
        harness=harness_sources(),tokens_sha256=ids_sha256(ids.tolist()),original_ffn=True,
        environment={n:importlib.metadata.version(n) for n in ('torch','transformers','tokenizers','lm_eval','datasets')})
    out=Artifacts(root/'results'/execution['commit'][:12],identity)
    save(out.root/('INVOCATION_'+os.environ['SLURM_JOB_ID']+'.json'),dict(argv=sys.argv,host=platform.node(),
        gpu=torch.cuda.get_device_name(0),gpu_uuid=str(torch.cuda.get_device_properties(0).uuid),
        visible_devices=os.environ['CUDA_VISIBLE_DEVICES'],phase=args.phase))
    try:
        model=AutoModelForCausalLM.from_pretrained(root/'model',local_files_only=True,trust_remote_code=False,
            torch_dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda:0').eval()
        if any(getattr(model.config,k)!=v for k,v in ready['shape'].items()):
            raise ValueError('native Qwen3 shape changed')
        if out.existing('preflight') is None:
            out.put('preflight',preflight(model,ids,documents,tasks,config))
        print('PREFLIGHT_PASSED',flush=True)
        if args.phase=='preflight':
            return
        from .benchmark import run_benchmark
        if out.existing('benchmark') is None:
            out.put('benchmark',run_benchmark(model,ids,config=config,power_gpu_uuid=str(torch.cuda.get_device_properties(0).uuid)))
        anchor=vectorized_anchor(model,ids,out)
        ppl=paired_ppl(model,ids,config,out,args.batch,args.ppl_chunk)
        task_results=paired_tasks(model,documents,tasks,config,out,args.task_chunk)
        if out.existing('SUMMARY') is None:
            out.put('SUMMARY',dict(complete=True,model=ready['model'],revision=ready['revision'],
                anchor=anchor['perplexity'],ppl={m:r['perplexity'] for m,r in ppl.items()},tasks=task_results,
                physical_asic_ppa=None,scope='pure SparQ, original full FFN; Python reference GPU timing'))
        print('ALL_REQUESTED_QUALITY_COMPLETE',flush=True)
    except BaseException as error:
        save(out.root/('FAILED_'+os.environ['SLURM_JOB_ID']+'.json'),dict(error=repr(error),phase=args.phase,complete=False))
        raise


if __name__=='__main__':
    main()
