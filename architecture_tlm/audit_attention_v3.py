"""Audit stored results and actual transaction logs, not a second estimator."""
import argparse
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);args=p.parse_args()
    results=[]
    for path in sorted(args.directory.glob('*.json')):
        d=json.loads(path.read_text(encoding='utf-8'))
        if 'attention_v3' not in d:continue
        count=d['config']['decode_tokens'];a=d['attention_v3'];mode=a['config']['mode']
        assert abs(d['metrics']['scenario_mJ_per_token']-sum(d['energy_J'].values())/count*1000)<1e-7
        assert abs(d['metrics']['mean_TPOT_ms']-sum(d['time_ns'].values())/count/1e6)<1e-6
        assert d['quality_reference_ppl'] is None
        assert a['peak_live_bytes']<=d['config']['scratchpad']['capacity_MiB']*1024**2
        shape=d['actual_shape'];dim=shape['hidden_size']//shape['num_attention_heads']
        assert d['actions']['ATT_QK_MAC']==d['actions']['ATT_selected_QK_tokens']*dim
        assert len(a['rows'])==shape['num_hidden_layers']*shape['num_attention_heads']*count
        if mode in ('pv','screen_pv','ising'):
            expected=len(a['rows'])*a['config']['samples']
            assert d['actions'].get('ATT_PV_MAC',0)==0
            assert d['actions']['ATT_V_additions']==expected*dim
            assert d['actions']['ATT_random_words']>0
        resources=defaultdict(float);transactions=0
        with gzip.open(path.parent/a['transactions_file'],'rt',encoding='utf-8') as f:
            for line in f:
                ev=json.loads(line);transactions+=1
                for resource in ev.get('reserved_resources',[ev['resource']]):
                    assert ev['start_ns']+1e-6>=resources[resource],(path,resource,ev)
                    resources[resource]=ev['end_ns']
                assert ev['end_ns']>=ev['start_ns']
                assert ev['end_ns']<=sum(d['time_ns'].values())+1e-6
                if 'address' in ev:assert ev['address']%64==0
                if ev['name']=='ising_online_update_loop':assert ev['retained_rng_words']==2
        sources={}
        for name in ('attention_tlm_v3.py','attention_reference_v3.py'):
            current=hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
            sources[name]=current==d['source_hashes'][name]
        results.append(dict(file=path.name,transactions=transactions,ledger_and_resource_audit='PASS',source_matches=sources))
    if not results:raise SystemExit('No attention_v3 results')
    out=dict(checked_results=len(results),results=results,
        scope='bookkeeping/causality audit only; not numerical LLM PPL or silicon calibration')
    (args.directory/'verification.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,indent=2))


if __name__=='__main__':main()
