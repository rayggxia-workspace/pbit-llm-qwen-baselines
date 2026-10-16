"""Stored-result ledger, resource, compaction and no-double-sampling audit."""
import argparse
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);args=p.parse_args();checks=[]
    for path in sorted(args.directory.glob('*.json')):
        d=json.loads(path.read_text(encoding='utf-8'))
        if 'attention_v4' not in d:continue
        a=d['attention_v4'];rows=a['rows'];count=d['config']['decode_tokens'];actions=d['actions']
        cap=a['ising']['capacity'];N=a['config']['samples'];shape=d['actual_shape']
        assert len(rows)==shape['num_hidden_layers']*shape['num_attention_heads']*count
        assert all(1<=r['selected_tokens']<=cap for r in rows)
        assert all(len(r['candidate_map'])==r['selected_tokens'] for r in rows)
        for r in rows:
            L=d['config']['context_tokens']+r['token']
            assert len(set(r['candidate_map']))==r['selected_tokens']
            assert all(0<=i<L for i in r['candidate_map'])
            if a['config']['selection']=='fixed_budget':
                blocks=set(i//64 for i in r['candidate_map'])
                assert len(blocks)==min((L+63)//64,a['config']['budget_blocks'])
        assert actions.get('ATT_softmax_nonlinear',0)==0
        assert actions.get('ATT_cdf_vector',0)==0
        assert actions.get('ATT_PV_MAC',0)==0
        assert actions.get('ATT_ising_attempts',0)==0
        assert actions['ATT_Ising_macro_requests']==len(rows)
        assert actions['ATT_Ising_output_indices']==len(rows)*N
        assert actions['ATT_V_additions']==len(rows)*N*(shape['hidden_size']//shape['num_attention_heads'])
        router_words=sum(shape['num_hidden_layers']*shape['num_attention_heads']*((d['config']['context_tokens']+t+63)//64) for t in range(count))
        assert actions['ATT_random_words']==router_words
        assert abs(sum(d['energy_J'].values())/count*1000-d['metrics']['scenario_mJ_per_token'])<1e-7
        assert abs(sum(d['time_ns'].values())/count/1e6-d['metrics']['mean_TPOT_ms'])<1e-7
        assert abs(d['energy_J']['ATT_Ising_macro_active_config']-a['ising']['active_and_config_J'])<1e-10
        assert a['peak_live_bytes']<=d['config']['scratchpad']['capacity_MiB']*1024**2
        resources=defaultdict(float);n=0
        with gzip.open(path.parent/a['transactions_file'],'rt',encoding='utf-8') as f:
            for line in f:
                ev=json.loads(line);n+=1;r=ev['resource']
                assert ev['start_ns']+1e-7>=resources[r],(path,r,ev)
                assert ev['end_ns']>=ev['start_ns'];resources[r]=ev['end_ns']
                if ev['name']=='Ising_macro':
                    assert ev['valid_candidates']+ev['masked_slots']==cap
                    assert ev['config_bits']==cap*(a['config']['ising']['bias_bits']+1)
                    assert ev['retained_internal_output_indices']==1
        for source in ('screen_ising_tlm_v4.py','ising_macro_v4.py'):
            assert hashlib.sha256((Path(__file__).parent/source).read_bytes()).hexdigest()==d['source_hashes'][source]
        checks.append(dict(file=path.name,transactions=n,status='PASS'))
    if not checks:raise SystemExit('no v4 results')
    report=dict(checked_cases=len(checks),cases=checks,scope='transaction and ledger consistency; NOT hardware/PPL validation')
    (args.directory/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
