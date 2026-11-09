"""Recompute the 2x2 FFN-mode / QKVO interaction from the public NLL ledger."""
from pathlib import Path
import gzip,json,math

def main():
    p=Path(__file__).resolve().parent/'joint_mean_diagnostic_20261109.json.gz'
    data=json.loads(gzip.decompress(p.read_bytes()))
    rows={r['case']:r for r in data['results']}
    for w in ['t64','wh64']:
        print(w,{m:rows[w+'_'+m]['ppl'] for m in ['sampled','mean']})
    effects={}
    for m in ['sampled','mean']:
        a,b=rows['t64_'+m],rows['wh64_'+m]
        effects[m]=(b['nll_sum']-a['nll_sum'])/2048
        print(m,'QKVO replacement mean-NLL penalty',effects[m],
              'PPL ratio',math.exp(effects[m]),
              'paired segment NLL deltas',[(y['nll_sum']-x['nll_sum'])/256 for x,y in zip(a['records'],b['records'])])
        for r in [a,b]:
            assert r['FFN_mode']==m and len(r['FFN_runtime_audit'])==36
            for audit in r['FFN_runtime_audit'].values():
                assert audit[m+'_calls']==audit['calls']>0
                if m=='mean':assert audit['sampled_input_frames']==audit['sampled_and_frames']==0
    print('difference in replacement penalties',effects['sampled']-effects['mean'])
    print('Diagnostic only: encoded plug-in mean and different down reduction; not the exact expectation of the nonlinear network.')

if __name__=='__main__':main()
