"""Use SHA-verified official parquet snapshots without server Hub connectivity."""
from pathlib import Path
import hashlib,json

def install(root):
    import datasets
    root=Path(root);data=root/'data/parquet'
    manifest=json.loads((data/'dataset_manifest.json').read_text())['datasets']
    original=datasets.load_dataset
    checked=set()
    def load(path,*args,**kwargs):
        if path=='parquet':return original(path,*args,**kwargs)
        name=args[0] if args else kwargs.get('name')
        key=path+'::'+str(name);assert key in manifest,key
        record=manifest[key];files={}
        for r in record['files']:
            p=data/r['file'];assert p.resolve().is_relative_to(data.resolve())
            if str(p) not in checked:
                assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'],str(p)
                checked.add(str(p))
            files.setdefault(r['split'],[]).append(str(p))
        result=original('parquet',data_files=files,cache_dir=str(root/'cache/datasets-local'))
        split=kwargs.get('split')
        return result[split] if split else result
    datasets.load_dataset=load
    return manifest
