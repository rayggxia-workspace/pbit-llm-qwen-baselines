"""Prepare a pinned manifest after server path discovery; performs no inference.

Only small config bytes are read here. Full model/data hashing runs in Slurm.
Unknown extra tokenizer/model files are rejected by verify_inputs.py later.
"""
from pathlib import Path
import argparse
import hashlib
import json
import run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True)
    parser.add_argument('--text',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--personal-root',default='/home/Weican_Chen')
    args=parser.parse_args()
    personal_root=Path(args.personal_root).resolve(strict=True)
    model=run.inside(args.model,personal_root)
    text=run.inside(args.text,personal_root)
    output=run.inside(args.output,personal_root,exists=False)
    if output.exists():
        raise FileExistsError('Preserve existing input manifest; choose a new name')
    identities=json.loads((Path(__file__).parent/'expected_identity.json').read_text(encoding='utf-8'))
    config_sha=hashlib.sha256((model/'config.json').read_bytes()).hexdigest()
    variant=next((v for v in identities['config_variants'] if v['sha256']==config_sha),None)
    if variant is None:
        raise ValueError('Unrecognized config variant; inspect semantics and provenance first')
    files=[]
    for name,entry in identities['files'].items():
        if variant['label']=='upstream_original_recorded_sources_json':
            entry=identities.get('upstream_original_files',{}).get(name,entry)
        if name.startswith('model/'):
            relative=name.split('/',1)[1]
            path=run.inside(model/relative,personal_root)
            role='tokenizer' if any(v in relative for v in ['tokenizer','vocab','merges']) else 'model'
            identity=variant if relative=='config.json' else entry
        elif name=='data/wiki.test.raw':
            path=text;role='testtext';identity=entry
        else:
            continue  # No training/calibration corpus is used by this E0/E1 task.
        files.append({'role':role,'path':str(path),'sha256':identity['sha256'],'bytes':identity['bytes']})
    manifest={
        'schema':'attention-e01-input-manifest-v1',
        'model_id':'Qwen/Qwen2.5-0.5B',
        'model_revision':identities['model_revision'],
        'provenance':{'reference':identities['source'],'config_variant':variant['label'],
                      'identity_file_sha256':run.digest(Path(__file__).parent/'expected_identity.json'),
                      'train_data':'not used; historical SHA retained in identity metadata only'},
        'files':files,
    }
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(manifest,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps({'output':str(output),'sha256':run.digest(output),'config_variant':variant['label'],
                      'large_input_hashing':'pending Slurm verify_inputs.py'},ensure_ascii=False))


if __name__=='__main__':
    main()
