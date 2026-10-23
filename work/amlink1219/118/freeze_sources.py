"""Freeze reviewed Git bytes, never the changing working tree or credentials."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

BASE = '46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d'
REPO = 'rayggxia-workspace/pbit-llm-qwen-baselines'
PATHS = [
    'AGENTS.md', 'PROJECT_MEMORY_ZH.md',
    'architecture_tlm/unified_v6/config.py',
    'architecture_tlm/unified_v6/model.py',
    'architecture_tlm/unified_v6/RNG_INTEGRATION_RESULTS_ZH.md',
    'architecture_tlm/ffn_stratified_reference/reference.json',
    'architecture_tlm/digital_ppa_v1/LATEST_TLM_RTL_GAPS_ZH.md',
    'architecture_tlm/resource_budget_plan_20261022/PLAN_ZH.md',
    'architecture_tlm/llama7b/runtime/results/sram_calibration_v1_20261016/calibration.json',
]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-checkout', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    records = []
    for path in PATHS:
        data = subprocess.run(['git', '-C', args.source_checkout, 'show', BASE+':'+path],
                              check=True, capture_output=True).stdout
        oid = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        records.append(dict(path=path, git_blob=oid, bytes=len(data),
                            sha256=hashlib.sha256(data).hexdigest(),
                            url='https://github.com/'+REPO+'/blob/'+BASE+'/'+path))
    payload = dict(schema_version=1, repository=REPO, base_commit=BASE,
                   evidence_type='read_only_source_binding', files=records)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n',
                    encoding='utf-8', newline='\n')
    print(json.dumps({'source_files':len(records), 'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}))

if __name__ == '__main__': main()
