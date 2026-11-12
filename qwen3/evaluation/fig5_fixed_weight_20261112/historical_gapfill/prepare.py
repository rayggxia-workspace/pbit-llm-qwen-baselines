"""Download fixed HF weights; verify raw WT2 and exact tokenizer identity."""
from pathlib import Path
import argparse,hashlib,json
from plans import ids_sha256

HERE=Path(__file__).resolve().parent
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--work',required=True)
    p.add_argument('--raw',help='Existing wiki.test.raw. Omit to reconstruct pinned HF parquet.')
    p.add_argument('--dataset-revision',help='Optional Salesforce/wikitext commit; resolved and recorded when omitted.')
    a=p.parse_args();root=Path(a.work).resolve();root.mkdir(parents=True,exist_ok=True)
    from huggingface_hub import snapshot_download,hf_hub_download,HfApi
    from transformers import AutoTokenizer
    spec=json.loads((HERE/'ASSETS.json').read_text())
    model=snapshot_download(repo_id=spec['parent']['repo'],revision=spec['parent']['revision'],
        allow_patterns=['*.json','*.safetensors','*.txt','*.model','*.tiktoken'],cache_dir=str(root/'hf'))
    overlay=None
    dataset_revision=None
    if a.raw:raw=Path(a.raw).resolve()
    else:
        import pyarrow.parquet as pq
        dataset_revision=HfApi().dataset_info(spec['test']['repo'],revision=a.dataset_revision).sha
        parquet=hf_hub_download(repo_id=spec['test']['repo'],repo_type='dataset',revision=dataset_revision,
            filename='wikitext-2-raw-v1/test-00000-of-00001.parquet',cache_dir=str(root/'hf'))
        rows=pq.read_table(parquet,columns=['text'])['text'].to_pylist()
        raw=root/'wiki.test.raw'
        raw.write_bytes(''.join(' \n' if s=='' else s for s in rows).encode('utf-8'))
    assert sha(raw)==spec['test']['raw_sha256'],'WT2 raw bytes mismatch; do not normalize/join with extra newline'
    tokenizer=AutoTokenizer.from_pretrained(model,local_files_only=True)
    ids=tokenizer(raw.read_bytes().decode('utf-8'),add_special_tokens=False)['input_ids']
    assert len(ids)==spec['test']['tokens'] and ids_sha256(ids)==spec['test']['token_ids_sha256_le_int64'],'WT2 tokenizer protocol mismatch'
    # Every downloaded model/tokenizer byte is fingerprinted, not only the overlay.
    files={str(f.relative_to(model)):sha(f) for f in sorted(Path(model).rglob('*')) if f.is_file()}
    out=dict(model_dir=model,overlay=overlay,raw=str(raw),spec=spec,model_files_sha256=files,
             dataset_revision=dataset_revision,raw_source='user-supplied hash-verified raw' if a.raw else 'HF parquet reconstructed',
             token_count=len(ids),token_ids_sha256_le_int64=ids_sha256(ids))
    (root/'assets.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(root/'assets.json')
if __name__=='__main__':main()
