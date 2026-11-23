"""Audit sealed small screen results without model loading or GPU work."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import statistics
import tarfile

ARCHIVE_SHA='e010003550efce82b26b6918c79c44e512df4fda76ca13177f163293a9d83175'


def audit(archive):
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==ARCHIVE_SHA
    with tarfile.open(archive) as bundle:
        files={m.name:bundle.extractfile(m).read() for m in bundle.getmembers() if m.isfile()}
    raw_audit=json.loads(files['AUDIT.json'])
    summaries=[n for n in files if n.startswith('SCREEN_SUMMARY') and n.endswith('.json')]
    assert len(summaries)==1
    summary_bytes=files[summaries[0]]
    assert hashlib.sha256(summary_bytes).hexdigest()==raw_audit['summary_sha256']
    summary=json.loads(summary_bytes)
    full_name=next(n for n in files if n.startswith('FULL_SUBMISSION') and n.endswith('.json'))
    assert hashlib.sha256(files[full_name]).hexdigest()==raw_audit['full_submission_sha256']
    full=json.loads(files[full_name]);assert full['jobs']==[] and full['selected_cases']==[]
    by_case={};common=None;positions=None;cases=set()
    for entry in raw_audit['index']:
        name=entry['relative_result_path'];payload=files[name]
        sha=hashlib.sha256(payload).hexdigest()
        assert sha==entry['sha256']==files[name[:-5]+'.sha256'].decode().split()[0]
        d=json.loads(payload);r=d['result'];a=r['addresses']
        key=(d['case']['id'],d['seed']);assert key not in cases;cases.add(key)
        assert key==(entry['case'],entry['seed'])
        assert d['status']=='completed' and d['phase']=='screen' and not d['full_corpus']
        assert r['windows']==8 and r['targets']==9215
        assert math.isclose(r['ppl'],math.exp(r['nll']/r['targets']),rel_tol=1e-12)
        identity=(d['identity'],d['inputs'],d['protocol'],d['gate_sha256'])
        if common is None:common=identity
        assert identity==common
        p=[{k:w[k] for k in ['window_index','start','end','first_target','targets','target_token_sha256']}
           for w in r['window_ledger']]
        if positions is None:positions=p
        assert p==positions and sum(w['targets'] for w in p)==9215
        assert set(a['per_layer'])=={str(i) for i in range(36)}
        for layer in a['per_layer'].values():
            assert layer['calls']==8 and layer['tokens']==16384
        for x in [a]+list(a['per_layer'].values()):
            assert x['selected_weight_bytes']==x['unique_addresses']*19456
            assert x['full_weight_bytes']==x['possible_addresses']*19456
        assert math.isclose(a['unique_address_ratio'],a['unique_addresses']/a['possible_addresses'],rel_tol=1e-12)
        by_case.setdefault(key[0],[]).append((key[1],r))
    assert len(cases)==27 and len(by_case)==9
    for row in summary['rows']:
        values=by_case[row['case']];assert {seed for seed,_ in values}=={101,202,303}
        ppl=[r['ppl'] for _,r in values]
        assert math.isclose(row['ppl_mean'],statistics.mean(ppl),rel_tol=1e-12)
        assert math.isclose(row['ppl_sd'],statistics.stdev(ppl),rel_tol=1e-12)
        assert math.isclose(row['unique_address_ratio'],statistics.mean(r['addresses']['unique_address_ratio'] for _,r in values),rel_tol=1e-12)
    assert summary['selected_full_cases']==[]
    return {'status':'passed','scope':'8_window_3_seed_screen_not_full_WT2','unique_results':27,
            'configs':9,'seeds':[101,202,303],'targets_per_result':9215,'layers':36,
            'archive_sha256':ARCHIVE_SHA,'summary_sha256':raw_audit['summary_sha256'],
            'full_submission_sha256':raw_audit['full_submission_sha256'],
            'source_commit':common[1]['source']['git_commit'],
            'export_manifest_sha256':common[0]['export_manifest_sha256'],
            'text_sha256':common[2]['text_sha256'],'token_sha256':common[2]['token_sha256'],
            'qualified_full_candidates':0,'full_WT2_jobs':[]}


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('archive',type=Path);ap.add_argument('--output',type=Path)
    args=ap.parse_args();result=audit(args.archive)
    text=json.dumps(result,indent=2)+'\n'
    if args.output:args.output.write_bytes(text.encode('utf-8'))
    print(text)
