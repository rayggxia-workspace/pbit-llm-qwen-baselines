"""Audit sealed software/model results; no inference, hardware run, or refit."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import struct
import tarfile

HERE=Path(__file__).resolve().parent
OLD=(18.20000779048508,17.89494970067286,17.669679075660085)
FAMILIES={'normalized_amplitude':('438d4eea432a',('shared9','shared8')),
          'raw_value':('4b81b34fa28d',('raw9','raw8'))}


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def dump(path,obj):
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')


def aggregate_diag(cases):
    rows=[]
    for layer in range(36):
        d=[c['diagnostics'][str(layer)] for c in cases]
        stats=[sum(x['codec']['raw_codec_stats'][j] for x in d) for j in range(14)]
        n=max(stats[0],1)
        rows.append(dict(layer=layer,probe_elements=int(stats[0]),
            gate_changed_fraction=stats[1]/n,gate_probability_mae=stats[2]/n,
            conditional_z_change_nmse=stats[5]/max(stats[6],1e-30),
            g_amplitude_changed_fraction=stats[7]/n,u_amplitude_changed_fraction=stats[8]/n,
            g_zero_fraction=stats[9]/n,u_zero_fraction=stats[10]/n,
            g_clipped_fraction=statistics.mean(x['amplitude']['g']['clip_fraction'] for x in d),
            u_clipped_fraction=statistics.mean(x['amplitude']['u']['clip_fraction'] for x in d),
            g_encoding_nmse=statistics.mean(x['amplitude']['g']['encoding_nmse'] for x in d),
            u_encoding_nmse=statistics.mean(x['amplitude']['u']['encoding_nmse'] for x in d)))
    return rows


def main():
    files={};results={};scores=[];target_sha=None;prepared_sha=None;dep_sha=None
    frozen_dir=HERE/'results'
    for family,(prefix,modes) in FAMILIES.items():
        root=frozen_dir/prefix
        for folder in ('gate','seed0','seed1','seed2'):
            path=root/folder;seal=json.loads((path/'complete.json').read_bytes())
            assert seal['status']=='completed'
            for name,h in seal['documents'].items():assert digest(path/name)==h,(path,name)
        for p in sorted(root.rglob('*')):
            if p.is_file():files[p.relative_to(HERE).as_posix()]=dict(bytes=p.stat().st_size,sha256=digest(p))
        case_data={}
        for seed in (0,1,2):
            path=root/('seed'+str(seed));prov=json.loads((path/'provenance.json').read_bytes())
            assert prov['source']['source_commit'].startswith(prefix)
            assert prov['dependency_source']['commit']=='5d49ea97502d2c11bf0745d50689b4c558c384d1'
            if prepared_sha is None:prepared_sha=prov['prepared_sha256'];dep_sha=prov['dependency_source']
            assert prepared_sha==prov['prepared_sha256'] and dep_sha==prov['dependency_source']
            assert prov['config']['data_sha256']=={
                'wiki.train.raw':'6707892fa3788b5ab9ed78ab5ff37d9fe825f6011a2ad4fcd6a6d467f0e7da57',
                'wiki.test.raw':'173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08'}
            for case in ('bf16',)+tuple('finite_'+m for m in ('independent9',)+modes):
                v=json.loads((path/(case+'.json')).read_bytes())
                assert v['provenance_sha256']==digest(path/'provenance.json')
                assert v['scored_tokens']==1024 and v['all_layer_calls']==[8]*36
                assert len(v['rows'])==8 and sum(r['scored_tokens'] for r in v['rows'])==1024
                assert all(r['first_target']-r['begin']==2048 and r['prefill_tokens']==2047 and r['scored_tokens']==128 for r in v['rows'])
                inputs=sum(r['end']-r['begin']-1 for r in v['rows'])
                assert inputs==17400 and v['all_layer_input_tokens']==[inputs]*36
                positions=[p for r in v['rows'] for p in range(r['first_target'],r['last_target_exclusive'])]
                assert len(positions)==len(set(positions))==1024
                assert hashlib.sha256(b''.join(struct.pack('<q',p) for p in positions)).hexdigest()==v['target_positions_sha256']
                if target_sha is None:target_sha=v['target_positions_sha256']
                assert v['target_positions_sha256']==target_sha
                assert v['perplexity']==math.exp(v['nll_sum']/1024)
                if case=='bf16':assert v['perplexity']==13.566049199388152
                if case=='finite_independent9':assert v['perplexity']==OLD[seed]
                case_data.setdefault(case,[]).append(v)
                scores.append(dict(family=family,case=case,seed=seed,ppl=v['perplexity'],nll=v['nll_sum'],tokens=1024))
        family_result={}
        for case,data in case_data.items():
            values=[v['perplexity'] for v in data]
            family_result[case]=dict(ppl_seeds=values,mean=statistics.mean(values),sample_sd=statistics.stdev(values),
                diagnostics=None if case=='bf16' else aggregate_diag(data))
        for mode in ('independent9',)+modes:
            path=root/'seed0'/('mean_'+mode+'.json');v=json.loads(path.read_bytes())
            assert v['scored_tokens']==1024 and v['all_layer_calls']==[8]*36
            assert v['conditional_NL_mean_only'] and v['GU_samples']==64 and v['NL_samples'] is None
            assert v['target_positions_sha256']==target_sha
            family_result['mean_'+mode]=dict(seed=0,ppl=v['perplexity'],diagnostics=aggregate_diag([v]))
            scores.append(dict(family=family,case='mean_'+mode,seed=0,ppl=v['perplexity'],nll=v['nll_sum'],tokens=1024))
        results[family]=family_result
    summary=dict(status='completed',protocol='fixed1024-target suffix/context2048;all36 FFNs/allprefix;not completeWT2',
        model=dict(id='Qwen/Qwen3-4B',revision='1cfa9a7208912126459214e8b04321603b3df60c',posttrained=True),
        dependency='PR207@104a2e49;immutable execution5d49ea97502d',prepared_sha256=prepared_sha,
        target_positions_sha256=target_sha,results=results,
        probe='at most16 evenly spaced token rows/layer/call;same-upstream comparison;not full-tensor accuracy',
        storage=dict(per_g_u_pair_bits={'9total':18,'8total':16},pairs_per_FFN=9728,
            pair_payload_bytes={'9total':21888,'8total':19456},shared_scale_tag_bytes=76,
            independent_sigmoid_address_if_stored_bytes=9728,
            note='logical payload only;not macro area,measured power or new hardware state.9total rawg and normalizedg have different code semantics.'),
        scope='No training/refit/fullWT2/RTL/PPA/default change;GU FP32 restoration oracle;same initial seed is not draw-level pairing',
        failed_first_snapshot='dca16c4a/CPU3499 test-reference dtype mismatch;core unchanged;failed log retained;blocked3500/3501 cancelled',
        raw_files=len(files),postprocessor_sha256=digest(Path(__file__)))
    dump(frozen_dir/'SUMMARY.json',summary);dump(frozen_dir/'RAW_FILES.json',files)
    with (frozen_dir/'SCORES.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(scores[0]));writer.writeheader();writer.writerows(scores)
    # Small reproducible raw archive; preserve original JSON/log bytes and SHA.
    for family,(prefix,_) in FAMILIES.items():
        archive=frozen_dir/('raw_'+prefix+'.tar.gz')
        if not archive.exists():
            with tarfile.open(archive,'w:gz') as t:
                for p in sorted((frozen_dir/prefix).rglob('*')):
                    if p.is_file():t.add(p,arcname=p.relative_to(frozen_dir).as_posix(),recursive=False)
        with tarfile.open(archive,'r:gz') as t:
            for member in t.getmembers():
                raw=t.extractfile(member).read();key='results/'+member.name
                assert hashlib.sha256(raw).hexdigest()==files[key]['sha256']
        summary.setdefault('raw_archives',{})[family]=dict(file=archive.name,bytes=archive.stat().st_size,sha256=digest(archive))
    dump(frozen_dir/'SUMMARY.json',summary)
    print(json.dumps({k:{c:({j:x[j] for j in ('mean','sample_sd')} if 'mean' in x else x['ppl'])
                         for c,x in v.items()} for k,v in results.items()},indent=2))


if __name__=='__main__':main()
