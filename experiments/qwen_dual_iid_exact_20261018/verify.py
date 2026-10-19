"""Read-only identity gate; no downloads or reconstruction of historical inputs."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
MODEL_REVISION = '060db6499f32faf8b98477b0a26969ef7d8b9987'
TEST_IDS_SHA256 = '8d41d21825bb0e103dc63337727daf4b51c631cacec5937f014b119ae209081e'
CALIBRATION_IDS_SHA256 = '52765211c4e14b32bb7fe44f5790c77370764454de7dc6c735f759538e5cd472'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    temporary.replace(path)


def source_manifest():
    return {str(p.relative_to(ROOT)).replace('\\', '/'): {
                'bytes': p.stat().st_size, 'sha256': digest(p)}
            for p in sorted(ROOT.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts
            and p.suffix in ('.py', '.json', '.sbatch', '.md')}


def verify(model, data, output):
    """Hash model, tokenizer and both raw corpora before any model inference."""
    import torch
    from transformers import AutoTokenizer
    model, data = Path(model).resolve(), Path(data).resolve()
    expected = json.loads((ROOT / 'expected_identity.json').read_text(encoding='utf-8'))
    checked = {}
    for name, entry in expected['files'].items():
        area, rel = name.split('/', 1)
        path = (model if area == 'model' else data) / rel
        actual = {'bytes': path.stat().st_size, 'sha256': digest(path)}
        if actual != entry:
            raise ValueError(f'Identity mismatch: {name}: {actual} != {entry}')
        checked[name] = dict(actual, path=str(path))
    frozen = json.loads((ROOT / 'frozen_manifest.json').read_text(encoding='utf-8'))
    for rel, entry in frozen['files'].items():
        path = ROOT / rel
        actual = {'bytes': path.stat().st_size, 'sha256': digest(path)}
        if actual != entry:
            raise ValueError(f'Frozen implementation/calibration changed: {rel}')
    tokenizer = AutoTokenizer.from_pretrained(str(model), local_files_only=True)
    token_info = {}
    for split in ('train', 'test'):
        text = (data / f'wiki.{split}.raw').read_text(encoding='utf-8')
        ids = tokenizer(text, add_special_tokens=False, return_tensors='pt').input_ids
        checksum = hashlib.sha256(ids.numpy().tobytes()).hexdigest()
        token_info[split] = {'tokens': ids.shape[-1], 'ids_sha256': checksum,
                             'dtype': str(ids.dtype), 'shape': list(ids.shape)}
        if split == 'test' and (ids.shape[-1] != 299078 or checksum != TEST_IDS_SHA256):
            raise ValueError(f'Full Qwen WT2 token identity mismatch: {token_info[split]}')
        if split == 'train':
            selected = hashlib.sha256(ids[:, :8192].numpy().tobytes()).hexdigest()
            if selected != CALIBRATION_IDS_SHA256:
                raise ValueError(f'Calibration prefix token identity mismatch: {selected}')
            token_info[split]['first8192_ids_sha256'] = selected
    identity = {'status': 'verified', 'model_repository': 'Qwen/Qwen2.5-0.5B',
        'model_revision': MODEL_REVISION,
        'revision_evidence': 'Recorded original upstream revision plus immutable file hashes; no network download',
        'files': checked, 'tokens': token_info, 'source_sha256': source_manifest(),
        'frozen_manifest_sha256': digest(ROOT / 'frozen_manifest.json'),
        'physical_rng_replay': False,
        'randomness': 'Ideal IID software distribution, no tuned seed or predefined sequence'}
    write_json(output, identity)
    return identity


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--data', required=True)
    parser.add_argument('--output', required=True)
    a = parser.parse_args()
    verify(a.model, a.data, a.output)
    print('PASS: model/tokenizer/train/test/frozen code/calibration/token identities')
