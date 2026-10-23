"""Offline document/provenance validation; this does not execute model or PPA tests."""
from pathlib import Path
import argparse, hashlib, json, math, posixpath, re
from urllib.parse import unquote, urlparse

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=Path('.'))
    p.add_argument('--tree-paths',type=Path)
    args=p.parse_args()
    root=args.root.resolve()
    known=set(json.loads(args.tree_paths.read_text(encoding='utf-8'))) if args.tree_paths else set()
    rel='architecture_tlm/benchmark_protocol_20261022/'
    work='work/amlink1219/98/prefill/'
    report=(root/(rel+'PREFILL_ANALYSIS_ZH.md')).read_text(encoding='utf-8')
    ev=json.loads((root/(rel+'PREFILL_EVIDENCE.json')).read_text(encoding='utf-8'))
    manifest=json.loads((root/(work+'MANIFEST.json')).read_text(encoding='utf-8'))
    checks=[]
    def check(name,value):
        checks.append({'name':name,'passed':bool(value)})
        if not value:raise AssertionError(name)
    expected=['opal','monde','unicaim','mba','kelle','attacc','neupims','cent','anda','llmcompass','splitwise','dscim','artemis','scarlet','hsa','santa']
    check('original_16_ids_and_order',[x['id'] for x in ev['papers']]==expected)
    check('report_and_evidence_matrix_ids',re.findall(r'^\| `([a-z]+)` —',report,re.M)==expected)
    check('three_additional_library_papers',[x['id'] for x in ev['additional_library_papers']]==['santapp','pdswap','tokenpicker'])
    check('each_paper_has_original_source_and_locator',all(x['source_url'].startswith('https://') and x['source_version'] and x['prefill_handling_and_locator'] for x in ev['papers']))
    check('library_attachments_hashed_not_redistributed',len(ev['local_library_attachments'])==10 and all(re.fullmatch('[0-9a-f]{64}',x['sha256']) and not x['redistributed'] for x in ev['local_library_attachments']))
    check('santa_versions_explicit','v1' in ev['version_caveats'][0] and 'v2' in ev['version_caveats'][0])
    s=ev['santa_v2_table3']
    check('santa_decode_arithmetic',math.isclose(s['decode_speedup'],s['baseline_decode_s']/s['candidate_decode_s'],rel_tol=1e-14) and round(s['decode_speedup'],4)==1.2501)
    check('santa_request_arithmetic',math.isclose(s['prefill_plus_decode_speedup'],(s['baseline_prefill_s']+s['baseline_decode_s'])/(s['candidate_prefill_s']+s['candidate_decode_s']),rel_tol=1e-14) and round(s['prefill_plus_decode_speedup'],4)==1.1478)
    check('santa_batch_output_denominator',math.isclose(s['baseline_ms_per_batch_normalized_output'],s['baseline_decode_s']/(s['batch']*s['new_tokens_per_request'])*1000,rel_tol=1e-14))
    r=ev['project_recommendation']
    check('proposal_not_approved_or_measured',r['approved_default_change'] is False and r['new_quality_budget_approved'] is False and all(r[k] is None for k in ['prefill_latency_s','prefill_energy_J','complete_physical_area_mm2']))
    check('frozen_repository_boundary_source',ev['base_commit']=='eb317e4f6fb1b0d8844887401f3275f128ef8a83' and 'architecture_tlm/unified_v6/README_ZH.md' in ev['repository_sources'])
    links=[]
    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)',report):
        u=urlparse(target)
        if u.scheme or target.startswith('#'):continue
        path=posixpath.normpath(posixpath.join(rel,unquote(u.path)))
        check('relative_link:'+path,not path.startswith('../') and ((root/path).is_file() or path in known))
        links.append(path)
    check('internal_links_present',len(links)>=5)
    for item in manifest['files']:
        raw=(root/item['path']).read_bytes()
        raw.decode('utf-8')
        check('utf8_lf:'+item['path'],b'\r' not in raw and raw.endswith(b'\n'))
        check('sha256:'+item['path'],len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256'])
    check('manifest_scope',set(x['path'] for x in manifest['files'])=={rel+'PREFILL_ANALYSIS_ZH.md',rel+'PREFILL_EVIDENCE.json',work+'verify.py'})
    print(json.dumps({'validation_kind':'documentation_and_arithmetic_not_model_or_hardware','checks_passed':len(checks),'checks_failed':0,'relative_links_checked':len(links),'checks':checks},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
