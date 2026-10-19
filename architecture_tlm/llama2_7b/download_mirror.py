"""Download a user-authorized public mirror without credentials; verify upstream hashes."""
import argparse
import concurrent.futures
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8*2**20),b''):h.update(chunk)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--manifest-output',type=Path,required=True)
    a=p.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Use Slurm for this server task')
    if a.output.exists() or a.manifest_output.exists():raise FileExistsError('Use a new model/manifest destination')
    import requests
    source=json.loads(Path(__file__).with_name('configs').joinpath('MIRROR_SOURCE.json').read_text(encoding='utf-8'))
    endpoint=source['mirror_endpoint'];mirror=source['mirror_repository'];revision=source['mirror_revision']
    def session():
        s=requests.Session();s.trust_env=False
        s.headers.update({'User-Agent':'pbit-llama2-public-mirror-download'})
        return s
    s=session()
    metadata=s.get(endpoint+'/api/v1/models/'+mirror+'/repo/files',
        params={'Revision':revision,'Recursive':'true'},timeout=(10,30))
    metadata.raise_for_status();listing=metadata.json()
    assert listing['Success']
    files={x['Path']:x for x in listing['Data']['Files']}
    for name,expected in source['files'].items():
        actual=files[name]
        assert actual['Size']==expected['size'],('size',name)
        if expected.get('lfs'):assert actual['Sha256']==expected['lfs']['sha256'],('upstream SHA',name)
    a.output.mkdir(parents=True,exist_ok=False)
    def download(name):
        meta=files[name];destination=a.output/name;temporary=a.output/(name+'.part')
        local=session();url=endpoint+'/api/v1/models/'+mirror+'/repo?'+urlencode({'Revision':revision,'FilePath':name})
        for attempt in range(3):
            begin=temporary.stat().st_size if temporary.exists() else 0
            headers={'Range':f'bytes={begin}-'} if begin else {}
            try:
                with local.get(url,headers=headers,stream=True,timeout=(15,60)) as response:
                    response.raise_for_status()
                    if begin and response.status_code!=206:
                        begin=0
                    if begin:
                        assert response.headers.get('Content-Range','').startswith(f'bytes {begin}-')
                    with temporary.open('ab' if begin else 'wb') as handle:
                        done=begin;next_report=done+512*2**20
                        for chunk in response.iter_content(2**20):
                            if not chunk:continue
                            handle.write(chunk);done+=len(chunk)
                            if done>meta['Size']:raise RuntimeError('Mirror sent too many bytes')
                            if done>=next_report:
                                print(json.dumps({'file':name,'downloaded_bytes':done,'total_bytes':meta['Size']}),flush=True)
                                next_report+=512*2**20
                assert temporary.stat().st_size==meta['Size'],('download size',name)
                digest=sha(temporary)
                assert digest==meta['Sha256'],('mirror SHA mismatch',name)
                expected=source['files'][name]
                if expected.get('lfs'):assert digest==expected['lfs']['sha256']
                blob=None
                if not expected.get('lfs'):
                    raw=temporary.read_bytes()
                    blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
                temporary.rename(destination)
                row={'bytes':meta['Size'],'sha256':digest,'mirror_revision':meta['Revision'],
                     'official_lfs_match':digest==expected.get('lfs',{}).get('sha256') if expected.get('lfs') else None,
                     'official_git_blob_match':blob==expected.get('blobId') if blob else None}
                print(json.dumps({'verified_file':name,**row}),flush=True)
                return name,row
            except Exception as e:
                if attempt==2:raise
                print(json.dumps({'retry_file':name,'error_type':type(e).__name__,'attempt':attempt+1}),flush=True)
                time.sleep(2)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        records=dict(pool.map(download,source['files']))
    config=json.loads((a.output/'config.json').read_text())
    expected={'model_type':'llama','hidden_size':4096,'intermediate_size':11008,'num_hidden_layers':32,
        'num_attention_heads':32,'num_key_value_heads':32,'max_position_embeddings':4096,'vocab_size':32000,
        'rms_norm_eps':1e-5,'rope_theta':10000.0,'tie_word_embeddings':False,'hidden_act':'silu','attention_bias':False}
    normalized=dict(config)
    normalized.setdefault('attention_bias',False);normalized.setdefault('rope_theta',10000.0)
    assert all(normalized.get(k)==v for k,v in expected.items()),'Unexpected mirror architecture'
    manifest={'repository':source['official_repository'],'revision':source['official_revision'],
        'mirror_repository':mirror,'mirror_revision':revision,'endpoint':endpoint,'files':records,
        'model_shape':expected,'source_commit':os.environ.get('SOURCE_COMMIT'),
        'source_sha256':sha(Path(__file__)),'source_metadata_sha256':sha(Path(__file__).with_name('configs')/'MIRROR_SOURCE.json'),
        'authentication':'none; Session.trust_env=False; no token/cookies loaded or sent',
        'verification':'All downloaded files match frozen mirror SHA; LFS weights and tokenizer.model additionally match official upstream SHA. Small JSON Git-blob matches recorded separately.',
        'slurm_job_id':os.environ['SLURM_JOB_ID']}
    a.manifest_output.parent.mkdir(parents=True,exist_ok=True)
    with a.manifest_output.open('x',encoding='utf-8',newline='\n') as f:json.dump(manifest,f,indent=2);f.write('\n')
    print(json.dumps({'status':'complete','manifest':str(a.manifest_output),'manifest_sha256':sha(a.manifest_output)}),flush=True)


if __name__=='__main__':main()
