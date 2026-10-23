"""Prepare compact, auditable matrix artifacts; no weights or private fixtures."""
import argparse
import gzip
import json
from pathlib import Path
import shutil
from .run import canonical,digest,json_write


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--extracted',type=Path,required=True)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    real=a.extracted/'matrix-real-v5';smoke=a.extracted/'matrix-smoke-v5'
    totals={}
    for name,folder,expected in [('real',real,68),('smoke',smoke,8)]:
        totals[name]=json.loads((folder/'SUMMARY.json').read_text(encoding='utf-8'))
        assert (totals[name]['passed'],totals[name]['failed'])==(expected,0)
        for item in json.loads((folder/'ARTIFACT_MANIFEST.json').read_text(encoding='utf-8'))['artifacts']:
            data=(folder/item['path']).read_bytes()
            assert len(data)==item['bytes'] and digest(data)==item['sha256'],item['path']
    a.output.mkdir(parents=True,exist_ok=False)
    for src,dst in [(real/'SUMMARY.json','SUMMARY.json'),(smoke/'SUMMARY.json','SMOKE_SUMMARY.json'),
                    (real/'CASES.json','CASES.json'),(real/'ARTIFACT_MANIFEST.json','REAL_ARTIFACT_MANIFEST.json'),
                    (smoke/'ARTIFACT_MANIFEST.json','SMOKE_ARTIFACT_MANIFEST.json'),
                    (a.extracted/'matrix-v5-execution.json','EXECUTION.json')]:
        shutil.copyfile(src,a.output/dst)
    summaries={}
    for kind,folder in [('real',real),('smoke',smoke)]:
        for case in totals[kind]['cases']:
            summaries[kind+'/'+case['name']]=json.loads((folder/case['name']/'summary.json').read_text(encoding='utf-8'))
    blob=gzip.compress(canonical(summaries),mtime=0)
    (a.output/'CASE_SUMMARIES.json.gz').write_bytes(blob)
    chosen=['qwen_layer12_ffn_B4T32K32_seed0','qwen_layer12_exact_N128_S32_seed0',
            'qwen_layer12_winner_N512_S512_seed0','qwen_layer12_rejection_N512_S512_seed0']
    for index,name in enumerate(chosen):
        dest=a.output/name;dest.mkdir()
        names=['summary.json','contracts.json','trace.json.gz']
        if index<2:names.append('timeline.html')
        for file in names: shutil.copyfile(real/name/file,dest/file)
    archive_sha=digest(a.archive.read_bytes())
    assert archive_sha=='82319f0d95054149e7d3dbeba5248648d461fe91539107aaa85e83fd44429ee5'
    json_write(a.output/'ARCHIVE_INDEX.json',{
        'job_id':2776,'state':'COMPLETED','exit_code':'0:0','gpu_requested':False,
        'archive':{'local_path':str(a.archive.resolve()),'sha256':archive_sha,'bytes':a.archive.stat().st_size,
            'remote_host':'10.129.164.156:21570','remote_owner':'Weican_Chen',
            'remote_path':'/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/matrix-v5-results.tar.gz'},
        'source_archive':{'remote_path':'/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/cycle-source-v5.tar.gz',
                          'sha256':'f6c596f3d772dee19bea1d85badb25fe0088aefaaae70ab959555b68daf96cbf'},
        'full_summaries':{'path':'CASE_SUMMARIES.json.gz','cases':len(summaries),'sha256':digest(blob)},
        'publication_policy':'all76 full summary objects compressed; raw artifact manifests plus selected traces/timelines; complete raw results retained in hashed personal archive',
        'boundary':'real cropped FFN and query inputs; not full Qwen inference/PPL or physical PPA'})
    artifacts=[{'path':f.relative_to(a.output).as_posix(),'sha256':digest(f.read_bytes()),'bytes':f.stat().st_size}
               for f in sorted(a.output.rglob('*')) if f.is_file()]
    json_write(a.output/'PUBLISHED_MANIFEST.json',{'artifacts':artifacts})
    print(json.dumps({'cases':len(summaries),'files':len(artifacts),'published_bytes':sum(x['bytes'] for x in artifacts)}))


if __name__=='__main__':main()
