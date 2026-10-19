"""Reconstruct recorded max4 routing and separate QK sparsity from K traffic.

This is a routing/byte-accounting audit of synthetic fixtures. It does not
run a language model, modify the selector, or predict new energy/performance.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from attention_reference_v3 import TraceSource, selector

ROOT=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def union_probability(probabilities):
    return 1-math.prod(1-p for p in probabilities)


def audit_case(context):
    path=ROOT/f'results/attention_v3_verified_20261015/fixed_sc_exact_screen_pv_c{context}.json'
    d=json.loads(path.read_text(encoding='utf-8'))
    cfg=copy.deepcopy(d['config']['attention_v3']);shape=d['actual_shape']
    # Preserve the recorded calibration bytes; the earlier publication copy
    # has equal JSON values but different line endings and therefore a new hash.
    calibration=ROOT/f'results/screen_k_traffic_audit_20261017/archived_inputs/attention_max4_c{context}.json'
    assert sha(calibration)==d['attention_v3']['trace']['calibration_sha256']
    if cfg.get('trace_file'):raise ValueError('this audit expects the recorded synthetic fixture')
    cfg['calibration_file']=str(calibration)
    source=TraceSource(cfg,shape)
    q=shape['num_attention_heads'];kv=shape['num_key_value_heads'];group=q//kv
    dim=shape['hidden_size']//q;vector_bytes=dim*2;burst=d['config']['external_memory']['burst_bytes']
    assert (q,kv,dim,burst)==(14,2,64,256)
    assert d['config']['external_memory'].get('backend','link')!='dramsys'
    tokens=d['config']['decode_tokens'];layers=shape['num_hidden_layers']
    totals=dict(possible_head_tokens=0,selected_head_tokens=0,full_K_bytes=0,
        logical_K_bytes=0,physical_K_Link256_bytes=0,head_probability_weighted=0.,
        expected_independent_logical_K_bytes=0.,expected_group_shared_logical_K_bytes=0.,
        expected_independent_physical_K_Link256_bytes=0.,
        expected_group_shared_physical_K_Link256_bytes=0.,
        expected_global_shared_physical_K_Link256_bytes=0.,
        free_probabilities=0,saturated_free_probabilities=0)
    for token in range(tokens):
        length=context+token;block_lengths=[min(64,length-i) for i in range(0,length,64)]
        blocks=len(block_lengths);forced={0,blocks-1,max(0,blocks-2)}
        for layer in range(layers):
            probabilities=[];masks=[]
            for head in range(q):
                logits=source.logits(token,layer,head,length)
                bias,temp=source.parameters(layer,head)
                indices,info=selector(logits,bias,temp,source.random(token,layer,head,'router'))
                masks.append(set(info['selected_blocks']))
                probabilities.append(info['block_probabilities'])
                totals['selected_head_tokens']+=len(indices)
                for b,p in enumerate(info['block_probabilities']):
                    totals['head_probability_weighted']+=p*block_lengths[b]
                    if b not in forced:
                        totals['free_probabilities']+=1
                        totals['saturated_free_probabilities']+=int(p<=.01 or p>=.99)
            totals['possible_head_tokens']+=q*length
            totals['full_K_bytes']+=kv*length*vector_bytes
            for k in range(kv):
                selected=set().union(*masks[k*group:(k+1)*group])
                totals['logical_K_bytes']+=sum(block_lengths[b] for b in selected)*vector_bytes
            all_selected=set().union(*masks)
            # Existing layout: each token K0/K1 share an aligned 256B burst.
            totals['physical_K_Link256_bytes']+=sum(block_lengths[b] for b in all_selected)*256
            for b,n in enumerate(block_lengths):
                p=[probabilities[h][b] for h in range(q)]
                max_by_group=[]
                for k in range(kv):
                    ps=p[k*group:(k+1)*group];mx=max(ps);max_by_group.append(mx)
                    totals['expected_independent_logical_K_bytes']+=union_probability(ps)*n*vector_bytes
                    totals['expected_group_shared_logical_K_bytes']+=mx*n*vector_bytes
                totals['expected_independent_physical_K_Link256_bytes']+=union_probability(p)*n*256
                totals['expected_group_shared_physical_K_Link256_bytes']+=union_probability(max_by_group)*n*256
                totals['expected_global_shared_physical_K_Link256_bytes']+=max(p)*n*256
    actions=d['actions'];traffic=d['traffic']
    assert totals['selected_head_tokens']==actions['ATT_selected_QK_tokens']
    assert totals['possible_head_tokens']==actions['ATT_possible_QK_tokens']
    assert totals['logical_K_bytes']==traffic['attention_K_useful_bytes']
    assert totals['physical_K_Link256_bytes']==traffic['attention_K_physical_bytes']
    denom=totals['full_K_bytes']
    ratios=dict(headwise_QK_retention=totals['selected_head_tokens']/totals['possible_head_tokens'],
        actual_K_logical_fraction=totals['logical_K_bytes']/denom,
        actual_K_Link256_physical_fraction=totals['physical_K_Link256_bytes']/denom,
        expected_headwise_retention=totals['head_probability_weighted']/totals['possible_head_tokens'],
        summary_read_fraction=traffic['attention_summary_read_physical_bytes']/denom,
        cold_summary_K_fraction=traffic.get('attention_summary_build_K_physical_bytes',0)/denom,
        historical_V_read_useful_including_reloads_fraction=traffic['attention_V_gather_useful_bytes']/denom,
        historical_V_Link256_physical_fraction=traffic['attention_V_gather_physical_bytes']/denom,
        free_probabilities_saturated_fraction=totals['saturated_free_probabilities']/totals['free_probabilities'])
    for name in ['expected_independent_logical_K_bytes','expected_group_shared_logical_K_bytes',
                 'expected_independent_physical_K_Link256_bytes',
                 'expected_group_shared_physical_K_Link256_bytes',
                 'expected_global_shared_physical_K_Link256_bytes']:
        ratios[name.replace('_bytes','_fraction')]=totals[name]/denom
    return dict(context=context,shape=dict(qheads=q,kvheads=kv,group=group,head_dim=dim),
        tokens=tokens,layers=layers,seed=cfg['seed'],samples=cfg['samples'],
        backend='historical simplified Link, 256B request granularity; NOT DRAMSys',
        fixture=source.provenance,source_result=str(path.relative_to(ROOT)),
        source_result_sha256=sha(path),calibration_sha256=sha(calibration),
        original_attention_config=d['config']['attention_v3'],totals=totals,ratios=ratios,
        summary=dict(vectors_per_64_tokens=4,format='FP32',
            bytes_per_layer_at_initial_context=kv*math.ceil(context/64)*4*dim*4,
            bytes_all_layers_at_initial_context=layers*kv*math.ceil(context/64)*4*dim*4,
            note='decode reads summaries from DRAM; cold construction paid once; prefill_prebuilt is a boundary assumption'),
        limitations=['input logits are independent synthetic Gaussians, not measured Qwen',
            'full V baseline equals full K bytes; reported V useful includes LRU reloads, not unique V union',
            '64B addressed lower byte count equals logical K for aligned 128B vectors; not a latency/energy prediction',
            'shared-uniform expectations are an analytical bound/candidate, not a new TLM or PPL result',
            'no new selection policy or PV v6 screening integration enabled'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--contexts',type=int,nargs='+',default=[2048,8192])
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise SystemExit('Refusing to overwrite an audit')
    cases=[audit_case(c) for c in a.contexts]
    result=dict(kind='recorded routing reconstruction and analytical traffic only',
        code_base='9608c0d06cf8b421cbbd348aca4fc84c5990aae7',
        source_sha256={p:sha(ROOT/p) for p in ['audit_screen_k_traffic.py','attention_reference_v3.py','attention_tlm_v3.py']},
        cases=cases)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps([dict(context=c['context'],ratios=c['ratios']) for c in cases]))


if __name__=='__main__':main()
