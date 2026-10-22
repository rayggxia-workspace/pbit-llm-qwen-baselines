"""Capture document-isolated QK-gate training targets from unchanged BF16 Qwen.

The forward hook only observes post-RoPE Q/K and the real V supplied to SDPA.
The explicit FP32 teacher is a separate numerical reference.  The reported
BF16 next-token loss is on the selected TRAIN articles, never WT2 test PPL.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import re
import sys
import time

import numpy as np

TRAIN_SHA256 = "6707892fa3788b5ab9ed78ab5ff37d9fe825f6011a2ad4fcd6a6d467f0e7da57"
TOP_TITLE = re.compile(r"^[ \t]*=[ \t]+([^=\r\n].*?)[ \t]+=[ \t]*$")


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def parse_documents(text):
    """Split only at WikiText's top-level `` = Article = `` title lines.

    Content deduplication uses the body (excluding the article title), with
    whitespace collapsed.  Raw corpus bytes are independently SHA-verified.
    Section headings stay in their parent article; pre-title whitespace is not
    a document.  No filesystem access occurs in this helper.
    """
    documents, title, heading, lines = [], None, None, []

    def finish():
        if title is None:
            return
        body = "".join(lines)
        if not body.strip():
            return
        canonical_body = " ".join(body.split())
        article_text = heading + body
        documents.append(dict(
            source_document_index=len(documents), title=title,
            text=article_text,
            content_sha256=hashlib.sha256(canonical_body.encode("utf-8")).hexdigest(),
            article_text_sha256=hashlib.sha256(article_text.encode("utf-8")).hexdigest(),
        ))

    for line in text.splitlines(keepends=True):
        match = TOP_TITLE.fullmatch(line.rstrip("\r\n"))
        if match:
            finish()
            title, heading, lines = match.group(1).strip(), line, []
        elif title is not None:
            lines.append(line)
        elif line.strip():
            raise ValueError("non-whitespace content before first top-level article")
    finish()
    if not documents:
        raise ValueError("no WikiText top-level articles found")
    return documents


def sha256_set(values, label):
    """Validate exclusion lists instead of accidentally treating a string as one."""
    if not isinstance(values, (list, tuple)):
        raise ValueError(label + " must be a list of SHA-256 strings")
    if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value)
           for value in values):
        raise ValueError(label + " contains an invalid SHA-256")
    return {value.lower() for value in values}


def select_documents(documents, encode, *, context, train_docs, val_docs,
                     holdout_docs, seed, exclude_document_sha256=(),
                     exclude_truncated_token_sha256=()):
    """Shuffle unique articles and exclude previously observed text or inputs.

    Document exclusions match either normalized ``content_sha256`` or the exact
    ``article_text_sha256``.  Truncated exclusions match the saved little-endian
    int64 ``truncated_token_ids_sha256`` (context+1 IDs).  Exclusions are applied
    to the shuffled order, preserving the old ordering for an empty exclusion.
    """
    counts = (int(train_docs), int(val_docs), int(holdout_docs))
    if min(counts) < 1:
        raise ValueError("each document split must be nonempty")
    excluded_documents = sha256_set(exclude_document_sha256, "exclude_document_sha256")
    excluded_prefixes = sha256_set(exclude_truncated_token_sha256, "exclude_truncated_token_sha256")
    unique, seen = [], set()
    for document in documents:
        key = document["content_sha256"]
        if key not in seen:
            unique.append(document)
            seen.add(key)
    order = list(range(len(unique)))
    random.Random(int(seed)).shuffle(order)
    selected, scanned, prefix_duplicates = [], 0, 0
    excluded_document_count, excluded_prefix_count = 0, 0
    seen_prefixes = set()
    for index in order:
        scanned += 1
        document = unique[index]
        if ({document["content_sha256"], document.get("article_text_sha256")}
                & excluded_documents):
            excluded_document_count += 1
            continue
        ids = list(encode(document["text"]))
        if len(ids) < context + 1:
            continue
        split = 0 if len(selected) < counts[0] else (
            1 if len(selected) < counts[0] + counts[1] else 2)
        chosen = dict(document, document=len(selected), split=split,
                      original_token_count=len(ids), token_ids=ids[:context + 1])
        chosen["truncated_token_ids_sha256"] = hashlib.sha256(
            np.asarray(chosen["token_ids"], dtype="<i8").tobytes()).hexdigest()
        if chosen["truncated_token_ids_sha256"] in excluded_prefixes:
            excluded_prefix_count += 1
            continue
        if chosen["truncated_token_ids_sha256"] in seen_prefixes:
            prefix_duplicates += 1
            continue
        seen_prefixes.add(chosen["truncated_token_ids_sha256"])
        selected.append(chosen)
        if len(selected) == sum(counts):
            break
    if len(selected) != sum(counts):
        raise ValueError(f"only {len(selected)} eligible unique articles; need {sum(counts)}")
    if len({d["content_sha256"] for d in selected}) != len(selected):
        raise AssertionError("document isolation failed")
    return selected, dict(parsed_articles=len(documents), unique_articles=len(unique),
                          articles_scanned=scanned, selected_articles=len(selected),
                          duplicate_truncated_inputs_skipped=prefix_duplicates,
                          excluded_document_sha256_count=len(excluded_documents),
                          excluded_truncated_token_sha256_count=len(excluded_prefixes),
                          excluded_documents_skipped=excluded_document_count,
                          excluded_truncated_inputs_skipped=excluded_prefix_count)


def row_statistics(q, k, v, position, *, max_blocks=32, block_tokens=64,
                   sub_tokens=16):
    """FP32 causal teacher and four visible post-RoPE K means per block.

    Invalid blocks/sub-blocks are zero-filled.  Their validity is never inferred
    from the feature value.  ``block_v`` is already weighted by the full causal
    probability, so summing it gives the dense teacher output.
    """
    q, k, v = (np.asarray(t, dtype=np.float32) for t in (q, k, v))
    if q.ndim != 1 or k.ndim != 2 or k.shape != v.shape or k.shape[1] != q.size:
        raise ValueError("expected q[D], k[T,D], v[T,D]")
    if block_tokens != 4 * sub_tokens or not 0 <= position < k.shape[0]:
        raise ValueError("invalid sub-block contract or query position")
    visible = int(position) + 1
    if visible > max_blocks * block_tokens:
        raise ValueError("visible keys exceed capture block capacity")
    if not all(np.isfinite(t).all() for t in (q, k[:visible], v[:visible])):
        raise ValueError("nonfinite Q/K/V")
    scores = (k[:visible] @ q) / np.float32(math.sqrt(q.size))
    weights = np.exp(scores - scores.max()).astype(np.float32)
    weights /= weights.sum(dtype=np.float32)
    x = np.zeros((max_blocks, 4), dtype=np.float32)
    mass = np.zeros(max_blocks, dtype=np.float32)
    block_v = np.zeros((max_blocks, q.size), dtype=np.float32)
    counts = np.zeros(max_blocks, dtype=np.int16)
    for block in range((visible + block_tokens - 1) // block_tokens):
        start, stop = block * block_tokens, min((block + 1) * block_tokens, visible)
        counts[block] = stop - start
        mass[block] = weights[start:stop].sum(dtype=np.float32)
        block_v[block] = weights[start:stop] @ v[start:stop]
        for sub in range(4):
            sub_start = start + sub * sub_tokens
            sub_stop = min(sub_start + sub_tokens, stop)
            if sub_start < sub_stop:
                x[block, sub] = (k[sub_start:sub_stop].mean(axis=0, dtype=np.float32)
                                 @ q) / np.float32(math.sqrt(q.size))
    valid, forced = counts > 0, np.zeros(max_blocks, dtype=np.bool_)
    last_block = (visible - 1) // block_tokens
    forced[0] = True
    forced[max(0, last_block - 1):last_block + 1] = True
    return dict(x=x, mass=mass, block_v=block_v, valid=valid, forced=forced,
                counts=counts, teacher_output=block_v.sum(axis=0, dtype=np.float32))


@contextmanager
def observe(model, torch, *, context, layers, heads, positions, document, split,
            records, diagnostics):
    """Observe the original SDPA call; never replace its returned value."""
    functional = torch.nn.functional
    original = functional.scaled_dot_product_attention
    active, handles, calls = {"layer": None}, [], []

    def pre(index):
        def hook(module, args):
            if active["layer"] is not None:
                raise RuntimeError("nested attention module")
            active["layer"] = index
        return hook

    def post(module, args, result):
        active["layer"] = None

    def wrapped(q, k, v, *args, **kwargs):
        layer = active["layer"]
        calls.append(layer)
        expected = (1, 14, context, 64)
        if any(tuple(t.shape) != expected for t in (q, k, v)):
            raise RuntimeError("unexpected Qwen SDPA QKV shape")
        if (args or kwargs.get("attn_mask") is not None
                or not kwargs.get("is_causal", False)
                or kwargs.get("dropout_p", 0) != 0
                or kwargs.get("scale") is not None
                or kwargs.get("enable_gqa", False)):
            raise RuntimeError("unexpected SDPA arguments")
        if any(t.dtype != torch.bfloat16 for t in (q, k, v)):
            raise RuntimeError("BF16 QKV required")
        result = original(q, k, v, *args, **kwargs)
        if layer in layers:
            for head in heads:
                base = (head // 7) * 7
                if not torch.equal(k[:, base], k[:, head]) or not torch.equal(v[:, base], v[:, head]):
                    raise RuntimeError("Qwen GQA repeated-head mismatch")
                keys, values = k[0, head].float().cpu().numpy(), v[0, head].float().cpu().numpy()
                for position in positions:
                    row = row_statistics(q[0, head, position].float().cpu().numpy(), keys, values, position)
                    actual = result[0, head, position].float().cpu().numpy()
                    difference = actual - row["teacher_output"]
                    nmse = float(np.mean(difference.astype(np.float64) ** 2)
                                 / max(float(np.mean(row["teacher_output"].astype(np.float64) ** 2)), 1e-12))
                    diagnostics.append(dict(document=document, split=split, layer=layer,
                                            head=head, position=position,
                                            fp32_teacher_vs_bf16_sdpa_nmse=nmse,
                                            max_abs=float(np.abs(difference).max())))
                    records.append(dict(row, layer=layer, head=head, document=document,
                                        split=split, position=position))
        return result

    try:
        for index, layer in enumerate(model.model.layers):
            handles.extend((layer.self_attn.register_forward_pre_hook(pre(index)),
                            layer.self_attn.register_forward_hook(post)))
        functional.scaled_dot_product_attention = wrapped
        yield calls
    finally:
        functional.scaled_dot_product_attention = original
        for handle in handles:
            handle.remove()


def tensor_sha256(tensor, torch):
    return hashlib.sha256(tensor.detach().cpu().contiguous().view(-1).view(torch.uint8).numpy().tobytes()).hexdigest()


def model_manifest(root):
    root = Path(root).resolve(strict=True)
    names = {"config.json", "generation_config.json", "tokenizer.json", "tokenizer_config.json",
             "special_tokens_map.json", "vocab.json", "merges.txt"}
    files = [p for p in root.iterdir() if p.is_file()
             and (p.name in names or p.name.endswith(".safetensors")
                  or p.name.endswith(".safetensors.index.json"))]
    if not any(p.name.endswith(".safetensors") for p in files):
        raise ValueError("local safetensors weights required")
    if not (root / "config.json").is_file():
        raise ValueError("model config missing")
    return {p.name: dict(bytes=p.stat().st_size, sha256=digest(p)) for p in sorted(files)}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def write_dataset_artifacts(output, arrays, *, emit_blind_split=False):
    """Archive full rows and optionally physically isolate train/val from blind.

    Original row ordering, document IDs and array schema are preserved in each
    partition.  The full archive remains ``dataset.npz`` for provenance; callers
    training phase two must explicitly use ``training_dataset.npz``.  No loader
    is redirected to the full archive or the blind holdout.
    """
    if not isinstance(emit_blind_split, bool):
        raise ValueError("emit_blind_split must be a JSON boolean")
    if not arrays or "split" not in arrays or arrays["split"].ndim != 1:
        raise ValueError("dataset requires one-dimensional split labels")
    groups = len(arrays["split"])
    if any(array.dtype.hasobject or array.ndim == 0 or len(array) != groups
           for array in arrays.values()):
        raise ValueError("dataset arrays must share row count and forbid object dtype")
    if not groups or not np.isin(arrays["split"], [0, 1, 2]).all():
        raise ValueError("invalid or empty dataset split labels")
    partitions = {"dataset": arrays}
    if emit_blind_split:
        if set(arrays["split"].tolist()) != {0, 1, 2}:
            raise ValueError("blind partition requires nonempty train, val and holdout")
        partitions["training_dataset"] = {key: value[arrays["split"] != 2] for key, value in arrays.items()}
        partitions["blind_holdout"] = {key: value[arrays["split"] == 2] for key, value in arrays.items()}
        if "document" in arrays:
            train_docs = set(partitions["training_dataset"]["document"].tolist())
            blind_docs = set(partitions["blind_holdout"]["document"].tolist())
            if train_docs & blind_docs:
                raise ValueError("a document crosses train/val and blind partitions")
    output = Path(output)
    paths = {key: output / (key + ".npz") for key in partitions}
    for path in paths.values():
        if path.exists():
            raise FileExistsError(path)
    manifest = {}
    for name, partition in partitions.items():
        path = paths[name]
        with path.open("xb") as stream:
            np.savez_compressed(stream, **partition)
        with np.load(path, allow_pickle=False) as saved:
            if set(saved.files) != set(partition):
                raise RuntimeError("dataset schema readback mismatch: " + name)
            for key, array in partition.items():
                if not np.array_equal(saved[key], array):
                    raise RuntimeError("dataset readback mismatch: " + name + "/" + key)
        manifest[name] = dict(path=str(path), bytes=path.stat().st_size, sha256=digest(path),
                              groups=len(partition["split"]), split_values=sorted(set(partition["split"].tolist())),
                              arrays={key: dict(shape=list(array.shape), dtype=str(array.dtype))
                                      for key, array in partition.items()})
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    config_path = Path(args.config).resolve(strict=True)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    exclusions = dict(exclude_document_sha256=config.get("exclude_document_sha256", []),
                      exclude_truncated_token_sha256=config.get("exclude_truncated_token_sha256", []))
    for label, values in exclusions.items():
        sha256_set(values, label)
    emit_blind_split = config.get("emit_blind_split", False)
    if not isinstance(emit_blind_split, bool):
        raise ValueError("emit_blind_split must be a JSON boolean")
    text_path = Path(config["text"]).resolve(strict=True)
    # No test split is read or hashed, including during provenance collection.
    if text_path.name != "wiki.train.raw":
        raise ValueError("capture permits only wiki.train.raw")
    text_sha = digest(text_path)
    expected_sha = config.get("expected_text_sha256", config.get("text_sha256", TRAIN_SHA256))
    if text_sha != expected_sha or expected_sha != TRAIN_SHA256:
        raise ValueError("WikiText TRAIN SHA-256 mismatch")
    if not config.get("source_commit"):
        raise ValueError("source_commit is required")
    if config.get("device", "cuda") != "cuda" or not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("capture requires CUDA inside an allocated Slurm job")
    context = int(config.get("context", 2048))
    layers, heads, positions = (list(map(int, config.get(key, default))) for key, default in (
        ("layers", [0, 12, 23]), ("heads", [0, 6, 13]), ("positions", [1023, 1535, 2047])))
    if context != 2048 or any(not 0 <= p < context for p in positions):
        raise ValueError("pilot requires context 2048 and causal in-window positions")
    if (not layers or not heads or not positions or len(set(layers)) != len(layers)
            or len(set(heads)) != len(heads) or len(set(positions)) != len(positions)
            or any(not 0 <= l < 24 for l in layers) or any(not 0 <= h < 14 for h in heads)):
        raise ValueError("invalid layer/head/position selection")
    seed = int(config.get("capture_seed", 42))
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("allocated CUDA BF16 device required")
    torch.set_num_threads(int(config.get("threads", 4)))
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    random.seed(seed)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = time.time()
    report = dict(status="running", source_commit=config["source_commit"], config=config,
                  config_sha256=digest(config_path), source_sha256=digest(__file__),
                  text=dict(path=str(text_path), sha256=text_sha, split="WikiText-2 raw TRAIN"),
                  scope="document-isolated local gate teacher; original BF16 TRAIN-article control, not WT2 test PPL",
                  policy=dict(original_attention=True, original_ffn=True, post_rope_keys=True,
                              teacher="explicit full-causal FP32 Softmax", block_tokens=64, sub_tokens=16,
                              raw_text_saved=False, no_test_access=True,
                              document_content_dedup="body whitespace collapsed, title excluded",
                              blind_split_emitted=emit_blind_split,
                              training_input="training_dataset.npz" if emit_blind_split else "dataset.npz",
                              blind_input="blind_holdout.npz" if emit_blind_split else None),
                  environment=dict(python=sys.version, platform=platform.platform(), numpy=np.__version__,
                                   torch=torch.__version__, transformers=transformers.__version__,
                                   cuda=torch.version.cuda, device=torch.cuda.get_device_name(),
                                   slurm_job_id=os.environ["SLURM_JOB_ID"],
                                   cuda_visible_devices=os.environ.get("CUDA_VISIBLE_DEVICES"),
                                   threads=torch.get_num_threads()))
    report_path = output / "capture.json"
    write_json(report_path, report)
    try:
        model_root = Path(config["model"]).resolve(strict=True)
        report["model"] = dict(path=str(model_root), files=model_manifest(model_root))
        tokenizer = AutoTokenizer.from_pretrained(model_root, local_files_only=True, trust_remote_code=False)
        documents = parse_documents(text_path.read_text(encoding="utf-8"))
        selected, selection = select_documents(
            documents, lambda text: tokenizer.encode(text, add_special_tokens=False), context=context,
            train_docs=config.get("train_docs", 32), val_docs=config.get("val_docs", 8),
            holdout_docs=config.get("holdout_docs", 8), seed=seed, **exclusions)
        report["selection"] = dict(selection, seed=seed, context=context,
                                   split_names={0: "train", 1: "val", 2: "holdout"},
                                   layers=layers, heads=heads, positions=positions,
                                   tokenization="add_special_tokens=False; first context+1 tokens per article")
        report["documents"] = [{k: v for k, v in d.items() if k not in ("text", "token_ids", "title")}
                               for d in selected]
        model = AutoModelForCausalLM.from_pretrained(model_root, torch_dtype=torch.bfloat16,
                    attn_implementation="sdpa", local_files_only=True, trust_remote_code=False).to("cuda").eval()
        cfg = model.config
        if (cfg.model_type != "qwen2" or cfg.num_hidden_layers != 24
                or cfg.num_attention_heads != 14 or cfg.num_key_value_heads != 2
                or cfg.hidden_size // cfg.num_attention_heads != 64):
            raise ValueError("expected Qwen2.5-0.5B Base QKV schema")
        report["tokenizer"] = dict(class_name=type(tokenizer).__name__, name_or_path=tokenizer.name_or_path,
                                    vocab_size=len(tokenizer), padding_side=tokenizer.padding_side)
        records, diagnostics, guards, controls = [], [], [], []
        guarded_splits = set()
        with torch.inference_mode():
            for document in selected:
                doc_id, split = document["document"], document["split"]
                ids = torch.tensor(document["token_ids"], dtype=torch.long, device="cuda")[None]
                window = ids[:, :context]
                guard = split in (0, 1) and split not in guarded_splits
                if guard:
                    reference = model.model(input_ids=window, use_cache=False, return_dict=True).last_hidden_state
                    reference_last = model.lm_head(reference[:, -1:]).float()
                with observe(model, torch, context=context, layers=set(layers), heads=heads,
                             positions=positions, document=doc_id, split=split,
                             records=records, diagnostics=diagnostics) as calls:
                    hidden = model.model(input_ids=window, use_cache=False, return_dict=True).last_hidden_state
                if calls != list(range(24)):
                    raise RuntimeError(f"capture layer coverage failed: {calls}")
                if guard:
                    last = model.lm_head(hidden[:, -1:]).float()
                    item = dict(document=doc_id, split=split,
                                backbone_bitwise_equal=bool(torch.equal(reference, hidden)),
                                last_logits_bitwise_equal=bool(torch.equal(reference_last, last)),
                                backbone_max_abs=float((reference.float() - hidden.float()).abs().max()),
                                last_logits_max_abs=float((reference_last - last).abs().max()),
                                backbone_sha256=tensor_sha256(reference, torch),
                                last_logits_sha256=tensor_sha256(reference_last, torch))
                    guards.append(item)
                    report["forward_guards"] = guards
                    if not item["backbone_bitwise_equal"] or not item["last_logits_bitwise_equal"]:
                        raise RuntimeError("unchanged BF16 capture bitwise guard failed")
                    guarded_splits.add(split)
                    del reference, reference_last, last
                nll = 0.0
                # Score all context targets, including the held-out next token.
                # Chunked lm_head avoids materializing [2048, vocab] at once.
                for start in range(0, context, 128):
                    end = min(start + 128, context)
                    logits = model.lm_head(hidden[:, start:end]).float()
                    nll += float(torch.nn.functional.cross_entropy(
                        logits.reshape(-1, logits.shape[-1]), ids[:, start + 1:end + 1].reshape(-1),
                        reduction="sum"))
                    del logits
                controls.append(dict(document=doc_id, split=split, scored_targets=context, nll_sum=nll))
                del ids, window, hidden
                print(json.dumps(dict(stage="captured", document=doc_id, split=split,
                                      groups=len(records), seconds=time.time() - started)), flush=True)
        report["forward_guards"] = guards
        report["numerical_diagnostics"] = dict(
            comparison="explicit FP32 teacher versus unchanged BF16 SDPA output; not bitwise identity",
            sanity_nmse_limit=1e-3, max_nmse=max(d["fp32_teacher_vs_bf16_sdpa_nmse"] for d in diagnostics),
            max_abs=max(d["max_abs"] for d in diagnostics), rows=diagnostics)
        if report["numerical_diagnostics"]["max_nmse"] > 1e-3:
            raise RuntimeError("FP32 teacher/BF16 SDPA NMSE sanity failed (limit 1e-3)")
        expected_groups = len(selected) * len(layers) * len(heads) * len(positions)
        if len(records) != expected_groups or guarded_splits != {0, 1}:
            raise RuntimeError("capture group coverage or split guards incomplete")
        arrays = {}
        for key in ("x", "mass", "block_v", "valid", "forced", "counts", "teacher_output"):
            arrays[key] = np.stack([row[key] for row in records])
        for key in ("layer", "head", "document", "position"):
            arrays[key] = np.asarray([row[key] for row in records], dtype=np.int64)
        arrays["split"] = np.asarray([row["split"] for row in records], dtype=np.int8)
        datasets = write_dataset_artifacts(output, arrays, emit_blind_split=emit_blind_split)
        totals = {str(split): dict(nll_sum=sum(c["nll_sum"] for c in controls if c["split"] == split),
                                  scored_targets=sum(c["scored_targets"] for c in controls if c["split"] == split))
                  for split in (0, 1, 2)}
        for total in totals.values():
            total["mean_nll"] = total["nll_sum"] / total["scored_targets"]
            total["ppl"] = math.exp(total["mean_nll"])
        report.update(status="completed", groups=len(records),
                      bf16_control=dict(scope="selected WikiText TRAIN articles, not complete WT2 test",
                                        documents=controls, splits=totals),
                      dataset=datasets["dataset"], datasets=datasets,
                      elapsed_seconds=time.time() - started)
        write_json(report_path, report)
        print(json.dumps(dict(status="completed", groups=len(records),
                              dataset_sha256=datasets["dataset"]["sha256"])), flush=True)
    except BaseException as exc:
        report.update(status="failed", error=dict(type=type(exc).__name__, message=str(exc)),
                      elapsed_seconds=time.time() - started)
        write_json(report_path, report)
        raise


if __name__ == "__main__":
    main()
