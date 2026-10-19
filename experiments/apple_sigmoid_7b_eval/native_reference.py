"""Short official AXLearn CPU forwards for independently checking the inference port."""
from pathlib import Path
import argparse,json,os
assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
os.environ['JAX_PLATFORMS']='cpu'
import jax
import jax.numpy as jnp
import numpy as np
import sentencepiece as spm
import tensorstore as ts
from axlearn.common.module import functional
from axlearn.common.attention import (SigmoidAttention, ALiBiAttentionLogitBiasLayer,
    FusedQKVLinear, ScaleQuery, ScaleKey, TransformerLayer, RepeatedTransformerLayer)
from axlearn.common.decoder import Decoder
from axlearn.common.embedding import TransformerTextEmbeddings
from axlearn.common.layers import RMSNorm, set_bias_recursively, set_norm_recursively


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--tokenizer',type=Path,required=True);p.add_argument('--kind',choices=['sigmoid','softmax'],required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--dtype',choices=['float32','bfloat16'],default='float32');p.add_argument('--weight-dtype',choices=['float32','bfloat16'],default='bfloat16');args=p.parse_args()
    dtype=getattr(jnp,args.dtype)
    param_dtype=getattr(jnp,args.weight_dtype)
    # Recreate the public Gala inference config directly from official layers.
    # Avoid importing trainer/data factories and their unrelated TF/SeqIO stack.
    norm=RMSNorm.default_config().set(eps=1e-5,forward_dtype=None)
    layer=TransformerLayer.default_config()
    layer.self_attention.set(structure='hybridnorm')
    layer.feed_forward.set(structure='hybridnorm',hidden_dim=11008,activation=('nn.silu','linear'))
    layer.self_attention.attention.set(num_heads=32,causal=True,
        input_linear=FusedQKVLinear.default_config(),
        query_scale=ScaleQuery.default_config().set(norm=norm.clone()),
        key_scale=ScaleKey.default_config().set(norm=norm.clone()))
    if args.kind=='sigmoid':
        att=layer.self_attention.attention
        kw=dict(att.items());del kw['klass']
        layer.self_attention.attention=SigmoidAttention.default_config().set(**kw).set(seq_len=4096)
    cfg=Decoder.default_config().set(name='native_gala',dtype=dtype,dim=4096,vocab_size=32768,
        transformer=RepeatedTransformerLayer.default_config().set(num_layers=32,layer=layer),
        emb=TransformerTextEmbeddings.default_config().set(pos_emb=None),
        attention_mask=ALiBiAttentionLogitBiasLayer.default_config().set(num_heads=32),
        logits_partition_spec=(None,None,None))
    set_bias_recursively(cfg,False)
    set_norm_recursively(cfg,norm)
    args.output.parent.mkdir(exist_ok=True,parents=True)
    args.output.with_suffix('.config.txt').write_text(str(cfg),encoding='utf-8')
    model=cfg.instantiate(parent=None)
    params={}
    base=args.source/'gda/model'
    for m in sorted(base.rglob('.zarray')):
        keys=m.parent.relative_to(base).parts
        print('LOAD_NATIVE','/'.join(keys),flush=True)
        a=ts.open({'driver':'zarr','kvstore':{'driver':'file','path':str(m.parent)+'/'}}).result().read().result()
        node=params
        for k in keys[:-1]:node=node.setdefault(k,{})
        node[keys[-1]]=jnp.asarray(a,dtype=param_dtype).astype(dtype)
        del a
    sp=spm.SentencePieceProcessor(model_file=str(args.tokenizer))
    text='The capital of France is Paris.\nA small language model should predict the next word.'
    ids=np.array([sp.encode(text.replace('\n','<n>'),out_type=int)],dtype=np.int32)
    outputs,_=functional(model,state=params['decoder'],is_training=False,prng_key=jax.random.PRNGKey(0),
        inputs={'input_batch':{'input_ids':jnp.asarray(ids)}})
    logits=outputs['logits']
    logits=np.asarray(logits,dtype=np.float32)
    args.output.parent.mkdir(exist_ok=True,parents=True)
    np.savez(args.output,input_ids=ids,logits=logits)
    print('NATIVE_REFERENCE_COMPLETE',args.kind,args.dtype,ids.shape,logits.shape,flush=True)

if __name__=='__main__':main()
