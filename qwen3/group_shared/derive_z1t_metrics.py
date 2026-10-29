"""Read-only re-expression of frozen Issue206 quality and model geometry.

No GPU/RTL/TLM run; mathematical MAC counts are not stochastic gate counts.
"""
import hashlib,json,math,pathlib,statistics
R=pathlib.Path(__file__).resolve().parents[2]
P=R/'qwen3/results/group_shared_20261028/FULL_WT2_G64B4_SUMMARY.json'
v=json.loads(P.read_bytes());assert v['status']=='completed' and v['target_count_per_seed']==299077
def loss(case):
    vals=[r[case]['nll_sum']/r[case]['scored_tokens'] for r in v['results']]
    mean=statistics.mean(vals)
    return dict(mean_CE_nats_per_token=mean,mean_bits_per_token=mean/math.log(2),
        pooled_seed_PPL=math.exp(mean),mean_PPL=statistics.mean(r[case]['perplexity'] for r in v['results']),
        CE_seed_sample_SD=statistics.stdev(vals),scored_tokens_per_seed=299077)
quality={k:loss(k) for k in ('bf16','g64b4')}
quality['delta_CE_nats']=quality['g64b4']['mean_CE_nats_per_token']-quality['bf16']['mean_CE_nats_per_token']
quality['delta_bits_per_token']=quality['delta_CE_nats']/math.log(2)
quality['arithmetic_mean_PPL_change_percent']=(quality['g64b4']['mean_PPL']/quality['bf16']['mean_PPL']-1)*100
quality['BPB']=None;quality['BPB_reason']='BPE token CE/log(2) is bits/token;true bits/byte needs UTF8 byte coverage aligned with scored targets;not computed.'
L,D,I,V,H,Hkv,dh=36,2560,9728,151936,32,8,128
ffn=L*3*D*I
proj=L*(D*H*dh+2*D*Hkv*dh+H*dh*D)
embed_head=V*D
norms=L*(2*D+2*dh)+D
total=ffn+proj+embed_head+norms
assert total==4022468096 and ffn==2689597440
geometry=dict(layers=L,hidden=D,FFN_width=I,vocab=V,Q_heads=H,KV_heads=Hkv,head_dim=dh,
    FFN_weights=ffn,attention_projection_weights=proj,tied_embedding_and_lm_head_weights=embed_head,norm_weights=norms,
    unique_learned_parameters=total,FFN_parameter_percent=100*ffn/total,
    logical_FFN_W8_bytes=ffn,logical_FFN_BF16_bytes=2*ffn,weight_storage_reduction_percent=50,
    storage_exclusions='scales/labels/alignment/bias-free_Qwen;not SRAM capacity or DRAM traffic')
work=[]
for K in (2048,8192):
    qk_pv=2*L*H*dh*K
    mac=ffn+proj+embed_head+qk_pv
    work.append(dict(K_including_current_token=K,FFN_MAC=ffn,QKV_Wo_MAC=proj,lm_head_MAC=embed_head,QK_PV_MAC=qk_pv,
        total_major_MAC=mac,equivalent_major_FLOPs=2*mac,FFN_MAC_percent=100*ffn/mac,
        excludes='norm/rope/softmax/SwiGLU_elementwise/residual/index/control/sampling/conversion;batch1 dense decode reference,not measured throughput'))
def zparams(d):
    # AFTConv qkv output2D+H,hidden4D;each sparse Linear has bias;2 DyT/block.
    l,h,s,k,vocab,seq=4,4,4,4,50257,256
    linear_weights=l*k*(8*d+h)
    linear_biases=l*(8*d+h)
    dyt=l*(4*d+2)+(2*d+1)
    conv=l*h*s
    embedding=vocab*d;head=vocab*d+vocab
    learned=linear_weights+linear_biases+dyt+conv+embedding+head
    fixed_pe=seq*d
    return dict(D=d,assumed_layers=l,assumed_H=h,assumed_kernel=s,fan_in=k,vocab=vocab,sequence=seq,
        block_weights_and_biases_and_norms_and_conv=linear_weights+linear_biases+(dyt-(2*d+1))+conv,
        learned_parameters_by_code=learned,embedding_parameters=embedding,lm_head_parameters=head,
        fixed_PE_floats=fixed_pe,code_float_leaf_count_including_PE=learned+fixed_pe,
        index_INT32_bytes_if_stored4=4*linear_weights,
        note='shape derivation,no checkpoint loaded;active_params sums all floating leaves,including PE buffer;indices int excluded;512 entry illustrative geometry,not claimed exact blog model.')
out=dict(status='derived_from_existing_results',quality_source_sha256=hashlib.sha256(P.read_bytes()).hexdigest(),
    quality_execution_source=v['source'],quality=quality,qwen=geometry,dense_reference_work=work,
    z1t_shape_derivations=[zparams(12288),zparams(512)],
    unavailable=['matched training FLOPs/scaling law','full-system energy/token with calibrated all-module boundary','ASIC decode latency matched currentG64 risk4','same-corpus same-tokenizer Z1T quality','physical finite-sample chip results'],
    no_new_GPU=True,no_new_EDA=True,no_new_TLM=True)
print(json.dumps(out,ensure_ascii=False,indent=2))
