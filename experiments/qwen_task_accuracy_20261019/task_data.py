"""Pinned lm-eval 0.4.8 tasks and tokenizer boundaries; no custom task metric."""
import hashlib
import importlib.metadata
import inspect
import json
from pathlib import Path
from types import MethodType, SimpleNamespace

TASKS = {
    'piqa': ('validation', 1838, '40e1677bba609c8801deacc171d76f3e24c083f365c95a1cbda7520c923dfea2'),
    'arc_easy': ('test', 2376, '4160597d618ae851c7eb04e281574f3f654776216ac6b6641588d64527b47177'),
    'hellaswag': ('validation', 10042, '899813071e1e95efafec90f856e1987d2150fa4d020fc005df6962c259f660cd'),
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def load_tasks(data_root):
    if importlib.metadata.version('lm_eval') != '0.4.8':
        raise RuntimeError('This experiment pins installed lm_eval==0.4.8')
    from lm_eval.tasks import TaskManager
    manager = TaskManager()
    tasks, identity = {}, {}
    for name, (split, count, checksum) in TASKS.items():
        path = Path(data_root).resolve(strict=True) / name / '0000.parquet'
        if sha(path) != checksum:
            raise ValueError('Dataset bytes changed: ' + name)
        # Preserve registered task prompt, process_docs and metric functions.
        # Only the loader changes, to the already cached identical full split.
        override = dict(task=name, dataset_path='parquet', dataset_name=None,
                        training_split=None, validation_split=split if split == 'validation' else None,
                        test_split=split if split == 'test' else None,
                        num_fewshot=0, fewshot_split=split,
                        dataset_kwargs={'data_files': {split: str(path)}})
        task = manager.load_task_or_group([override])[name]
        if len(task.eval_docs) != count:
            raise ValueError('Unexpected full task size: ' + name)
        tasks[name] = task
        yaml_path = Path(manager.task_index[name]['yaml_path'])
        identity[name] = dict(split=split, documents=count, dataset_sha256=checksum,
                              dataset_bytes=path.stat().st_size, dataset_path=str(path),
                              task_yaml_sha256=sha(yaml_path), task_yaml=str(yaml_path))
    return tasks, identity


def token_documents(task, name, tokenizer):
    from lm_eval.models.huggingface import HFLM
    encoder = SimpleNamespace(tokenizer=tokenizer, backend='causal', add_bos_token=False)
    encoder.tok_encode = MethodType(HFLM.tok_encode, encoder)
    result = []
    for index, doc in task.doc_iterator():
        context = task.fewshot_context(doc, num_fewshot=0)
        requests = task.construct_requests(doc, context, metadata=(name, index, 1))
        contexts, choices = [], []
        for request in requests:
            if request.request_type != 'loglikelihood':
                raise ValueError('Only official multiple-choice likelihood requests supported')
            ctx, continuation = request.args
            if not ctx:
                raise ValueError('Selected task unexpectedly has empty context')
            c, a = HFLM._encode_pair(encoder, ctx, continuation)
            if not a or len(c) < 3 or len(c) + len(a) > 2049:
                raise ValueError('Unsupported context/continuation length; no silent truncation')
            contexts.append(c)
            choices.append(a)
        if any(c != contexts[0] for c in contexts):
            raise ValueError('Choices do not share identical tokenized context')
        result.append(dict(id=f'{name}:{index}', task=name, doc_id=index,
                           context_ids=contexts[0], choices_ids=choices))
    return result


def harness_sources():
    import lm_eval.api.task
    import lm_eval.models.huggingface
    import lm_eval.tasks.hellaswag.utils
    from lm_eval.models.huggingface import HFLM
    paths = {Path(x.__file__) for x in (lm_eval.api.task, lm_eval.models.huggingface,
                                       lm_eval.tasks.hellaswag.utils)}
    paths.add(Path(inspect.getfile(HFLM._encode_pair)))
    return {str(p): sha(p) for p in sorted(paths)}


def metrics_for(tasks, row):
    task = tasks[row['task']]
    doc = task.eval_docs[row['doc_id']]
    scores = [(float(x['logprob']), bool(x['is_greedy'])) for x in row['choices']]
    values = task.process_results(doc, scores)
    if set(values) != {'acc', 'acc_norm'} or any(float(v) not in (0., 1.) for v in values.values()):
        raise ValueError('Unexpected official task metrics')
    return {k: float(v) for k, v in values.items()}
