"""Read-only sealed screen audit; packages raw small results without weights."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import statistics
import tarfile


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def sealed(path):
    assert digest(path)==path.with_suffix('.sha256').read_text().strip(),str(path)
    d=json.loads(path.read_bytes());assert d['status']=='completed',str(path)
    return d


def collect(root,old_root,output):
    if output.exists():raise FileExistsError('audit output exists')
    output.mkdir()
    gatepath=root/'gate-c72597f5d439/RESULT.json';gate=sealed(gatepath)
    calibpath=gatepath.parent/'CALIBRATION.json';calib=sealed(calibpath)
    assert digest(calibpath)==gate['calibration_sha256'] and calib['no_test_set_fit']
    nativepath=gatepath.parent/'BF16_reference/RESULT.json';native=sealed(nativepath)
    assert digest(nativepath)==gate['BF16_reference_sha256']
    assert gate['full2048_no_prune_logits_bitwise'] and gate['dense_integer_layers']==36
    assert gate['GPU_checks']['tests']==8 and gate['GPU_checks']['status']=='PASS'
    planpath=root/'source-c72597f5d439/PLAN.json';plan=json.loads(planpath.read_bytes())
    members=[gatepath,gatepath.with_suffix('.sha256'),nativepath,nativepath.with_suffix('.sha256')]
    rows=[];index=[];positions=None
    for case in plan['cases']:
        values=[];references=[]
        for seed in plan['deployment_seeds']:
            p=root/'screen-c72597f5d439'/('seed'+str(seed))/case['id']/'RESULT.json'
            d=sealed(p);r=d['result'];addr=r['addresses'];values.append(r)
            assert d['case']==case and d['seed']==seed and d['phase']=='screen' and not d['full_corpus']
            assert d['inputs']==gate['inputs'] and d['identity']==gate['identity'] and d['protocol']==gate['protocol']
            assert d['calibration_sha256']==digest(calibpath) and d['gate_sha256']==digest(gatepath)
            assert r['windows']==8 and r['targets']==9215 and addr['original_wd_calls']==288
            assert math.isclose(r['ppl'],math.exp(r['nll']/9215),rel_tol=1e-12)
            ledger=[{k:w[k] for k in ['window_index','start','end','first_target','targets','target_token_sha256']} for w in r['window_ledger']]
            if positions is None:positions=ledger
            assert ledger==positions
            assert set(addr['per_layer'])=={str(i) for i in range(36)}
            for layer in addr['per_layer'].values():
                assert layer['calls']==8 and layer['tokens']==16384
                assert layer['selected_weight_bytes']==layer['unique_addresses']*19456
                assert layer['full_weight_bytes']==layer['possible_addresses']*19456
            old=sealed(old_root/('seed'+str(seed))/'original_strat64/RESULT.json')['result']
            references.append(old)
            if case['kind']=='original':
                assert r['nll']==old['nll'] and r['ppl']==old['ppl']
                assert addr['unique_address_ratio']==old['addresses']['unique_address_ratio']
            else:
                pr=addr['pruning']['total'];assert pr['possible']==addr['possible_addresses']
                assert pr['pruned']<=pr['possible']-addr['unique_addresses']
                assert pr['baseline_nonzero']-pr['removed_nonzero']==addr['unique_addresses']
                assert set(addr['pruning']['per_layer'])=={str(i) for i in range(36)}
                for layer,v in addr['pruning']['per_layer'].items():
                    assert v['baseline_nonzero']-v['removed_nonzero']==addr['per_layer'][layer]['unique_addresses']
                    assert v['pruned']<=v['possible']-addr['per_layer'][layer]['unique_addresses']
            index.append({'case':case['id'],'seed':seed,'sha256':digest(p),'relative_path':p.relative_to(root).as_posix()})
            members.extend([p,p.with_suffix('.sha256')])
        ratio=math.exp(statistics.mean(v['mean_nll']-ref['mean_nll'] for v,ref in zip(values,references)))
        row={'case':case['id'],'score':case['score'],'target_prune_percent':case['prune_percent'],
             'ppl_mean':statistics.mean(v['ppl'] for v in values),'ppl_sd':statistics.stdev(v['ppl'] for v in values),
             'ppl_geometric_ratio_vs_paired_original':ratio,
             'unique_address_fraction':statistics.mean(v['addresses']['unique_address_ratio'] for v in values),
             'relative_GU_payload_reduction':statistics.mean(1-v['addresses']['unique_address_ratio']/ref['addresses']['unique_address_ratio'] for v,ref in zip(values,references)),
             'seeds':[{'seed':seed,'ppl':v['ppl'],'mean_nll':v['mean_nll']} for seed,v in zip(plan['deployment_seeds'],values)]}
        if case['kind']!='original':
            row['actual_pruned_fraction']=statistics.mean(v['addresses']['pruning']['total']['actual_pruned_fraction'] for v in values)
            row['removed_input_mass_fraction']=statistics.mean(v['addresses']['pruning']['total']['removed_input_mass_fraction'] for v in values)
        else:row['actual_pruned_fraction']=None
        rows.append(row)
    assert len(index)==15 and len({(v['case'],v['seed']) for v in index})==15
    archive=output/'RESULTS.tar.gz'
    with tarfile.open(archive,'w:gz') as f:
        for p in members:f.add(p,arcname=p.relative_to(root).as_posix())
    summary={'status':'completed','scope':'GU_only_8window_3seed_not_full_WT2',
        'rows':rows,'unique_results':15,'targets_per_result':9215,'layers':36,
        'identity':gate['identity'],'inputs':gate['inputs'],'protocol':gate['protocol'],
        'gate_sha256':digest(gatepath),'calibration_sha256':digest(calibpath),
        'train_text_sha256':calib['train_text_sha256'],'train_token_sha256':calib['train_token_sha256'],
        'calibration_spans':calib['calibration_spans'],'sampled_tokens_per_layer':calib['sampled_tokens_per_layer'],
        'norm_encoding_statistics':{k:{n:v[n] for n in ['distinct_exponents','exponent_spread','norm_min','norm_max']} for k,v in calib['norm_encodings'].items()},
        'fresh_BF16_reference_ppl':native['result']['ppl'],'gate_checks':gate['GPU_checks'],
        'unpruned_same_seed_NLL_bitwise_matches_prior':True,'all_result_seals_identity_positions_layers_and_payload_checks_passed':True,
        'raw_archive':{'name':'RESULTS.tar.gz','sha256':digest(archive),'bytes':archive.stat().st_size,'members':len(members)},
        'raw_result_index':index,'full_WT2_submitted':False}
    p=output/'SUMMARY.json';p.write_bytes((json.dumps(summary,indent=2)+'\n').encode())
    p.with_suffix('.sha256').write_bytes((digest(p)+'\n').encode())
    print(json.dumps({'summary_sha256':digest(p),'raw_archive':summary['raw_archive'],'rows':rows}))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--old-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();collect(a.root,a.old_root,a.output)
