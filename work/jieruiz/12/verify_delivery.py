"""Verify exact published bytes, immutable execution inputs and complete results."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AUX = Path(__file__).resolve().parent
BASE = '9608c0d06cf8b421cbbd348aca4fc84c5990aae7'


def record(path):
    raw = path.read_bytes()
    return dict(path=path.relative_to(ROOT).as_posix(), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def verify(record_manifest=False, staged=False):
    model = ROOT/'architecture_tlm/llama7b'
    frozen = json.loads((model/'EXECUTION_MANIFEST.json').read_text())
    for row in frozen['files']:
        raw = (model/row['path']).read_bytes()
        assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'], row['path']
    results = json.loads((model/'results/current/ARTIFACT_INDEX.json').read_text())
    assert results['results']==82 and not results['missing_cases']
    assert results['completeness_by_backend']=={'link_Staggered':60,'dramsys_Staggered':18,'dramsys_NoPowerDown':4}
    cases = json.loads((model/'results/current/cases.json').read_text())
    assert len(cases)==82
    for case in cases:
        assert abs(sum(case['energy_mJ_per_token'].values())-case['mJ_per_token'])<1e-7
        assert case['source_commit']==frozen['code_commit']
    for path in model.rglob('*.md'):
        if 'link_initial' in path.parts:
            continue
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8-sig')):
            if '://' in target or target.startswith('#'):
                continue
            assert (path.parent/target.split('#',1)[0]).exists(), (path,target)
    changed = subprocess.check_output(['git','diff','--name-only',BASE],cwd=ROOT,text=True).splitlines()
    allowed = ['AGENTS.md','architecture_tlm/README.md','architecture_tlm/llama7b/',
               'progress/jieruiz/','work/jieruiz/12/']
    assert all(any(rel==prefix or rel.startswith(prefix) for prefix in allowed) for rel in changed)
    artifacts = [record(ROOT/rel) for rel in changed if rel!='work/jieruiz/12/manifest.json']
    manifest_path = AUX/'manifest.json'
    if record_manifest:
        manifest = dict(repository='rayggxia-workspace/pbit-llm-qwen-baselines', owner='jieruiz', issue=12, pr=13,
            branch='task/12-llama7b-tlm',base_commit=BASE, execution_source_commit=frozen['code_commit'],
            capture_source_commit='e09b5e0c1319dee3ad3f212c51ff0495687b1043',
            postprocessing_report_commit=subprocess.check_output(['git','rev-parse','7c29927'],cwd=ROOT,text=True).strip(), postprocessing_report_sha256=record(model/'report.py')['sha256'],
            software_environment=json.loads((AUX/'capture_validation/manifest.json').read_text())['provenance']['versions'],
            model_data_identity='Model/tokenizer/WT2 hashes reverified by capture1877; see capture_validation/manifest.json. Upstream HF revision unknown, immutable shard hashes used.',
            protocol='Single public WT2 BF16 decode query/context512/1024/2048; TLM full32 layers; no new PPL/joint-SC numeric validation.',
            experiment_count=82, backend_counts=results['completeness_by_backend'],
            job_ids={'capture':1877,'link':1878,'dramsys_staggered':1879,'dramsys_nopd':1896},
            large_artifacts='Authorized SSH project in results/current/ARTIFACT_INDEX.json; weights/PDK/long traces not in Git.',
            limitations='Calibrated SRAM and source-backed DDR4 core scenario; digital/SC/RNG/Ising proxies and IO/PHY/CTS remain unmeasured.',
            artifacts=artifacts)
        manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        for row in manifest['artifacts']:
            raw = (ROOT/row['path']).read_bytes()
            assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'], row['path']
            if staged:
                blob = subprocess.check_output(['git','show',':'+row['path']],cwd=ROOT)
                assert blob==raw, 'staged byte mismatch: '+row['path']
    print(json.dumps({'immutable_inputs':len(frozen['files']),'complete_scenarios':len(cases),
                     'release_artifacts':len(artifacts),'staged_bytes_checked':staged}))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--record',action='store_true')
    p.add_argument('--staged',action='store_true')
    a=p.parse_args()
    verify(a.record,a.staged)
