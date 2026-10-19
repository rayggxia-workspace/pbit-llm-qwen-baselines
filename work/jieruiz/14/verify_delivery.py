"""Verify immutable inputs, real model evidence, complete results and Git blob bytes."""
import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
AUX=Path(__file__).resolve().parent
BASE='07d03385a3b16b1f81a987c031f667c13876edf1'
MODEL=ROOT/'architecture_tlm/llama2_7b'
BASELINE=ROOT/'baselines/llama2_7b/results/bf16_wt2_20261017'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(record=False,staged=False,allow_pending=False):
    frozen=read(MODEL/'EXECUTION_MANIFEST.json')
    assert frozen['code_commit']=='b5964b165dfead06676580029235bf5e952b5dad'
    assert len(frozen['files'])==57
    for row in frozen['files']:
        p=ROOT/row['path']
        assert p.stat().st_size==row['bytes'] and digest(p)==row['sha256'],row['path']
    identity=read(MODEL/'configs/model_identity.json')
    assert identity['repository']=='meta-llama/Llama-2-7b-hf'
    assert identity['revision']=='01c7f73d771dfac7d292323805ebc428287df4f9'
    assert all(r.get('official_lfs_match') is True or r.get('official_git_blob_match') is True for r in identity['files'].values())
    capture=read(AUX/'capture_validation/manifest.json')
    assert capture['status']=='complete' and capture['provenance']['model_identity']==identity
    assert capture['provenance']['identity_manifest_sha256']==digest(MODEL/'configs/model_identity.json')
    assert capture['provenance']['data']['first_2048_ids_sha256']=='5c208664955a0c5e4d2fb19d1a018559bf02eccd36d6aafb2a77b0e5d8cabca8'
    assert {r['context'] for r in capture['artifacts']}=={512,1024,2048,4096}
    for row in capture['artifacts']:
        actual=read(AUX/f"capture_validation/c{row['context']}.validation.json")
        assert row==actual
        assert actual['rows']==1024 and all(v['bitwise_equal'] and v['max_abs_difference']==0 for v in actual['validation'])
    baseline=read(BASELINE/'ARTIFACT_MANIFEST.json')
    for name,row in baseline.items():
        p=BASELINE/name
        assert p.stat().st_size==row['bytes'] and digest(p)==row['sha256'],name
    summary=read(BASELINE/'summary.json')
    assert summary['status']=='completed' and summary['code_commit']=='9ee1ab47d0317430212364e75adb78abec9797fb'
    assert {r['window'] for r in summary['ppl']}=={2048,4096}
    assert all(r['scored_tokens']==335686 and r['corpus_tokens']==335687 for r in summary['ppl'])
    current=MODEL/'results/current'
    if not current.exists():
        assert allow_pending and not record,'Final 116-case report not yet available'
        print(json.dumps({'immutable_inputs':57,'baseline_artifacts_verified':len(baseline),'capture_contexts':4,'TLM_status':'pending'}))
        return
    index=read(current/'ARTIFACT_INDEX.json');cases=read(current/'cases.json')
    assert index['results']==116 and not index['missing_cases']
    assert index['completeness_by_backend']=={'link_Staggered':72,'dramsys_Staggered':36,'dramsys_NoPowerDown':8}
    assert len(cases)==116 and len({(r['backend'],r['context'],r['case'],r['engines'],r['seed']) for r in cases})==116
    assert all(r['source_commit']==frozen['code_commit'] and r['workload']['kind']=='REAL_LLAMA2_7B_POST_ROPE_QK_LOGITS' for r in cases)
    assert all(math.isclose(sum(r['energy_mJ_per_token'].values()),r['mJ_per_token'],rel_tol=1e-10) for r in cases)
    assert all(r['input_snapshot_sha256']==digest(MODEL/'EXECUTION_MANIFEST.json') for r in cases)
    external=read(current/'DRAM_ARTIFACT_INDEX.json')
    assert external['DRAM_cases']==44 and len(external['original_artifacts'])==88
    expected={(r['backend'],f"c{r['context']}_{r['case']}_e{r['engines']}_s{r['seed']}") for r in cases if r['backend'].startswith('dramsys_')}
    actual={}
    for row in external['original_artifacts']:
        assert row['bytes']>0 and re.fullmatch(r'[0-9a-f]{64}',row['sha256'])
        assert row['path'].startswith(external['project']+'/outputs/'+row['backend']+'/')
        actual.setdefault((row['backend'],row['case']),[]).append(row['path'])
    assert set(actual)==expected and all(len(v)==2 for v in actual.values())
    assert all(any(p.endswith('.bridge.log') for p in v) and any(p.endswith('.requests.jsonl.gz') for p in v) for v in actual.values())
    assert external['bridge']['sha256']=='900e8257e255a01c59ed1770f8fda5901163003e0c8f21636baefc2cb662c868'
    assert external['linked_libraries']['libdramsys.so']['sha256']=='67f608ec3b7938f032414d1798b674eb9519cd339807b12b582ca7c2714b23c3'
    assert external['linked_libraries']['libDRAMPower.so']['sha256']=='33cc1cc40c4969cd3582beb40a7443c49249ea653938efffdb27c2835263f456'
    for path in list(MODEL.rglob('*.md'))+list(BASELINE.glob('*.md')):
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8-sig')):
            if '://' in target or target.startswith('#'):continue
            assert (path.parent/target.split('#',1)[0]).exists(),(path,target)
    changed=subprocess.check_output(['git','diff','--name-only',BASE],cwd=ROOT,text=True).splitlines()
    allowed=('architecture_tlm/llama2_7b/','baselines/llama2_7b/','work/jieruiz/14/')
    assert all(p in ('progress/jieruiz/STATUS.md','architecture_tlm/README.md') or p.startswith(allowed) for p in changed)
    artifacts=[]
    for rel in changed:
        if rel=='work/jieruiz/14/manifest.json':continue
        p=ROOT/rel;raw=p.read_bytes()
        assert len(raw)<10*2**20,'Use indexed server storage for large file: '+rel
        artifacts.append({'path':rel,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    manifest_path=AUX/'manifest.json'
    if record:
        value={'repository':'rayggxia-workspace/pbit-llm-qwen-baselines','owner':'jieruiz','issue':14,'pr':15,
            'branch':'task/14-llama2-baseline-tlm','base_commit':BASE,
            'capture_and_TLM_commit':frozen['code_commit'],'baseline_commit':summary['code_commit'],
            'postprocessing':read(AUX/'report_job.json'), 'model_repository':identity['repository'],
            'model_revision':identity['revision'],'model_identity_sha256':digest(MODEL/'configs/model_identity.json'),
            'test_data_sha256':summary['data_sha256'],'train_data':'Not used; no new training or calibration',
            'precision':'BF16 SDPA baseline; W8/A8 share64 T4096 SC hardware scenario; BF16 residual interface',
            'seed_protocol':'BF16 seed0; TLM deterministic dense seed0, stochastic address paths seeds0/1/2',
            'environment':read(BASELINE/'environment.json'),'TLM_cases':116,
            'scope':'Complete WT2 baseline PPL independent of single-query/context real-BF16 routing TLM. No joint SC PPL or measured ASIC energy.',
            'large_artifacts':'Authorized SSH project indexed by results/current/ARTIFACT_INDEX.json; weights/corpus/long traces not in Git.',
            'artifacts':artifacts}
        manifest_path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    if manifest_path.exists():
        manifest=read(manifest_path)
        assert {r['path'] for r in manifest['artifacts']}=={r['path'] for r in artifacts},'Release artifact set changed; regenerate manifest'
        for row in manifest['artifacts']:
            raw=(ROOT/row['path']).read_bytes()
            assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],row['path']
            if staged:
                blob=subprocess.check_output(['git','show',':'+row['path']],cwd=ROOT)
                assert blob==raw,'Git staged byte mismatch: '+row['path']
    print(json.dumps({'immutable_inputs':57,'baseline_artifacts_verified':len(baseline),'capture_contexts':4,
        'TLM_cases':116,'original_DRAM_artifacts_indexed':88,'release_artifacts':len(artifacts),'staged_blobs_verified':staged}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--record',action='store_true');p.add_argument('--staged',action='store_true');p.add_argument('--allow-pending',action='store_true')
    a=p.parse_args();verify(a.record,a.staged,a.allow_pending)
