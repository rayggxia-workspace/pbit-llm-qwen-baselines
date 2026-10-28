"""Address-set arithmetic and replay of archived synthetic transactions.

This is not a timing simulator, cache simulator, model run, or RTL experiment.
Unique burst sets are an ideal coalescing lower bound, not observed DRAM reads.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import math
import re
import subprocess
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def span_bursts(address, size, burst):
    return range(address // burst, (address + size - 1) // burst + 1)


def bursts(ids, n, d, layout='row_nhd', heads=1, head=0, page=16, burst=64):
    """BF16, byte-aligned bases; K and V are separate allocations.

    vllm_k uses x=8 elements (16 bytes), vllm_v has [page,H,D,T].
    The layouts are pinned ABI examples, not every modern vLLM backend.
    """
    if min(n, d, heads, page, burst) < 1 or not 0 <= head < heads:
        raise ValueError('invalid shape')
    ids = set(ids)
    if any(type(i) is not int or not 0 <= i < n for i in ids):
        raise ValueError('invalid token')
    out = set()
    for i in ids:
        if layout == 'row_nhd':
            out.update(span_bursts((i * heads + head) * d * 2, d * 2, burst))
        elif layout == 'row_hnd':
            out.update(span_bursts((head * n + i) * d * 2, d * 2, burst))
        elif layout == 'vllm_k':
            if d % 8:
                raise ValueError('head dimension must divide x=8')
            p, t = divmod(i, page)
            for c in range(d // 8):
                address = (((p * heads + head) * (d // 8) + c) * page + t) * 16
                out.update(span_bursts(address, 16, burst))
        elif layout == 'vllm_v':
            p, t = divmod(i, page)
            for c in range(d):
                address = (((p * heads + head) * d + c) * page + t) * 2
                out.update(span_bursts(address, 2, burst))
        else:
            raise ValueError(layout)
    return out


def occupancy_check():
    """Independent nested-loop physical serialization checks the index formulas."""
    checks = 0
    n, d, heads, page = 19, 16, 2, 8
    layouts = {}
    layouts['row_nhd'] = [(t, h, c) for t in range(n) for h in range(heads) for c in range(d)]
    layouts['row_hnd'] = [(t, h, c) for h in range(heads) for t in range(n) for c in range(d)]
    layouts['vllm_k'] = [(p * page + t, h, c * 8 + x)
                         for p in range(math.ceil(n / page)) for h in range(heads)
                         for c in range(d // 8) for t in range(page) for x in range(8)]
    layouts['vllm_v'] = [(p * page + t, h, c)
                         for p in range(math.ceil(n / page)) for h in range(heads)
                         for c in range(d) for t in range(page)]
    for name, serial in layouts.items():
        for ids in [[], [0], [0, 1, 7, 8, 18], list(range(n))]:
            for head in range(heads):
                for b in [16, 32, 64]:
                    oracle = {address // b for pos, (t, h, _) in enumerate(serial)
                              if t in ids and h == head for address in [2 * pos, 2 * pos + 1]}
                    assert bursts(ids, n, d, name, heads, head, page, b) == oracle
                    checks += 1
    assert len(bursts([0], 2048, 128)) * 64 == 256
    assert len(bursts([0], 2048, 128, 'vllm_k')) * 64 == 1024
    assert len(bursts([0], 2048, 128, 'vllm_v')) * 64 == 4096
    assert bursts([2, 2, 2], n, d) == bursts([2], n, d)
    return checks + 4


def analytic_cases(model):
    s = model['shape']
    hq, hkv, d, layers = [s[k] for k in ['num_attention_heads', 'num_key_value_heads', 'head_dim', 'num_hidden_layers']]
    shapes = []
    for n in [512, 2048, 8192]:
        data = 2 * n * hkv * d * 2
        mac = 2 * n * hq * d
        shapes.append(dict(n=n,read_bytes_per_layer=data,read_mib_per_layer=data / 2**20,
                           read_mib_all_layers=data * layers / 2**20,
                           mac_per_layer=mac,mac_all_layers=mac * layers,
                           append_write_bytes_per_layer=2 * hkv * d * 2,
                           ideal_group_fusion_flops_per_byte=2 * (hq // hkv) / 2,
                           conditional_all_layer_memory_ms_at_29_851GBs=data * layers / 29.851e9 * 1000,
                           conditional_all_layer_memory_ms_at_256GBs=data * layers / 256e9 * 1000,
                           conditional_all_layer_mac_ms_at_512x100MHz=mac * layers / (512 * 100e6) * 1000))
    # Full K scan, independent uniform IID sampling, shared group of four Q heads.
    # A transposed V page in the specified toy layout touches every burst when any token is selected.
    uniform = []
    for samples in [128, 512]:
        n, group, page = 2048, 4, 16
        v_row = -math.expm1(group * samples * math.log1p(-1 / n))
        v_page = -math.expm1(group * samples * math.log1p(-page / n))
        uniform.append(dict(n=n,group=group,samples_per_head=samples,
                            assumption='independent uniform IID draws; full K; not winner/systematic/real QKV',
                            expected_unique_V_row_fraction=v_row,
                            expected_touched_V_page_fraction=v_page,
                            expected_total_KV_fraction_row_layout=(1 + v_row) / 2,
                            expected_total_KV_fraction_transposed_page_toy=(1 + v_page) / 2))
    return shapes, uniform


def replay(index):
    """Reuse 18 old single-head S128 cases; do not invent a multi-head trace."""
    index = json.loads(Path(index).read_text(encoding='utf-8'))
    data = Path(index['path']).read_bytes()
    assert len(data) == index['bytes'] and sha(data) == index['sha256']
    records, inputs = [], []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = sorted(n for n in z.namelist() if re.fullmatch(r'results/sweep_final/L2048_d128_s(17|503|1009)_(D0|P[0-4])\.json', n))
        assert len(names) == 18
        for name in names:
            b = z.read(name)
            assert sha(b) == index['members'][name]['sha256']
            row = json.loads(b)
            assert row['status'] == 'completed' or row['status'] == 'ok'
            keys = set(row['candidates'])
            values = set(map(int, row['counts']))
            inputs.append(dict(member=name,sha256=sha(b),input_qkv_sha256=row['input_sha256']))
            k0 = len(bursts(keys, 2048, 128)) * 64
            v0 = len(bursts(values, 2048, 128)) * 64
            assert k0 == row['K_physical_bytes'] and v0 == row['V_physical_bytes']
            records.append(dict(mode=row['mode'],seed=row['seed'],n=2048,d=128,samples=row['samples'],
                                unique_k=len(keys),unique_v=len(values),
                                row_K_B=k0,row_V_B=v0,
                                legacy_page16_K_B=len(bursts(keys,2048,128,'vllm_k')) * 64,
                                legacy_page16_V_B=len(bursts(values,2048,128,'vllm_v')) * 64,
                                scope='old synthetic single head S128; lower-bound burst union, not same-quality GQA traffic'))
    return records, dict(path=index['path'],sha256=index['sha256'],members=inputs)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--archive-index', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    checks = occupancy_check()
    model_path = 'architecture_tlm/unified_v6/configs/model_qwen3_4b.json'
    model_bytes = subprocess.check_output(['git', 'show', 'HEAD:' + model_path])
    shapes, uniform = analytic_cases(json.loads(model_bytes))
    rows, original = replay(args.archive_index)
    result = dict(kind='derived_address_arithmetic_not_new_simulation',date='2026-10-28',
                  input_repo_head=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),
                  source_sha256=sha(Path(__file__).read_bytes()),model_shape_path=model_path,
                  model_shape_sha256=sha(model_bytes),model_shape=json.loads(model_bytes),
                  geometry_checks=checks,shapes=shapes,uniform_examples=uniform,
                  original_archive=original,replayed_single_head_cases=rows,
                  layout_toy=dict(element_bytes=2,burst_bytes=64,page_tokens=16,head_dim=128,
                                  single_token_row_bytes=256,single_token_legacy_K_bytes=1024,single_token_legacy_V_bytes=4096),
                  limitations=['no DRAMSys/cache/latency/energy prediction',
                               'burst union assumes ideal coalescing; finite cache/queue may re-fetch',
                               'no observed multi-head QKV or model/PPL; old traces all S128',
                               'ABI example is not universal modern vLLM or measured GPU traffic',
                               'no new RNG draws/RTL/EDA/server job or digital simulation run'])
    args.output.mkdir(parents=True)
    (args.output/'KV_READ_AUDIT.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())
    text = io.StringIO(newline='')
    writer = csv.DictWriter(text,fieldnames=list(rows[0]),lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
    (args.output/'SINGLE_HEAD_LAYOUT_REPLAY.csv').write_bytes(text.getvalue().encode())
    print(json.dumps(dict(geometry_checks=checks,archived_cases=len(rows),shapes=shapes,
                         uniform_examples=uniform),ensure_ascii=False))


if __name__ == '__main__':
    main()
