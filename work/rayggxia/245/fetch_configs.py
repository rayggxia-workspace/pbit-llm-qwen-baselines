"""Fetch small public metadata/config only; never model weights or credentials."""
from pathlib import Path
import ast,hashlib,json,urllib.request,urllib.error

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'architecture_tlm/model_scaling_20261106/evidence'
OUT.mkdir(parents=True,exist_ok=True)
MODELS={'llama32_3b':'meta-llama/Llama-3.2-3B-Instruct',
        'deepseek_7b':'deepseek-ai/deepseek-llm-7b-chat',
        'qwen3_4b':'Qwen/Qwen3-4B'}
rows=[]
for key,repo in MODELS.items():
    attempts=[];meta=None
    for host in ('https://huggingface.co','https://hf-mirror.com'):
        url=host+'/api/models/'+repo
        try:
            with urllib.request.urlopen(url,timeout=30) as response:meta=json.loads(response.read())
            attempts.append(dict(url=url,status='metadata_ok'));break
        except Exception as error:attempts.append(dict(url=url,error=type(error).__name__,message=str(error)))
    if meta is None:raise RuntimeError(attempts)
    revision=meta['sha'];config=None
    for host in ('https://huggingface.co','https://hf-mirror.com'):
        url=host+'/'+repo+'/resolve/'+revision+'/config.json'
        try:
            with urllib.request.urlopen(url,timeout=30) as response:raw=response.read()
            config=json.loads(raw);path=OUT/(key+'_config.json');path.write_bytes(raw)
            attempts.append(dict(url=url,status='config_ok',sha256=hashlib.sha256(raw).hexdigest()));break
        except Exception as error:attempts.append(dict(url=url,error=type(error).__name__,message=str(error)))
    if config is None and key=='llama32_3b':
        # The canonical HF config is gated. Use Meta's public SKU and check
        # tied embeddings/FFN width against the exact public tensor count.
        api='https://api.github.com/repos/meta-llama/llama-models/commits/main'
        with urllib.request.urlopen(api,timeout=30) as response:commit=json.load(response)['sha']
        source_url='https://raw.githubusercontent.com/meta-llama/llama-models/'+commit+'/models/sku_list.py'
        with urllib.request.urlopen(source_url,timeout=30) as response:source=response.read()
        tree=ast.parse(source.decode())
        vocab=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
                   and any(isinstance(t,ast.Name) and t.id=='LLAMA3_VOCAB_SIZE' for t in n.targets))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='arch_args_3b')
        value=next(n.value for n in fn.body if isinstance(n,ast.Return))
        args={ast.literal_eval(k):(vocab if isinstance(v,ast.Name) and v.id=='LLAMA3_VOCAB_SIZE' else ast.literal_eval(v))
              for k,v in zip(value.keys,value.values)}
        d=args['dim'];f=((int(8*d/3*args['ffn_dim_multiplier'])+args['multiple_of']-1)//args['multiple_of'])*args['multiple_of']
        config=dict(architectures=['LlamaForCausalLM'],model_type='llama',hidden_size=d,intermediate_size=f,
            num_hidden_layers=args['n_layers'],num_attention_heads=args['n_heads'],num_key_value_heads=args['n_kv_heads'],
            head_dim=d//args['n_heads'],vocab_size=vocab,tie_word_embeddings=True,hidden_act='silu',
            qk_norm=False,config_provenance='derived_from_Meta_public_SKU_plus_exact_HF_tensor_count_not_downloaded_HF_config')
        count=args['n_layers']*(3*d*f+2*d*(d+args['n_kv_heads']*config['head_dim'])+2*d)+vocab*d+d
        assert count==meta['safetensors']['total']==3212749824
        attempts.append(dict(url=source_url,status='public_official_architecture_verified',
            source_sha256=hashlib.sha256(source).hexdigest(),source_commit=commit,exact_parameter_count=count))
        archive=ROOT.parents[1]/'project_archives/model_scaling245_20261106';archive.mkdir(parents=True,exist_ok=True)
        (archive/'llama_sku_list.py').write_bytes(source)
        raw=(json.dumps(config,indent=2)+'\n').encode();(OUT/(key+'_config.json')).write_bytes(raw)
    if config is None:raise RuntimeError(attempts)
    rows.append(dict(key=key,repo=repo,revision=revision,config_sha256=hashlib.sha256(raw).hexdigest(),
        public_parameter_count=meta.get('safetensors',{}).get('total'),
        model_type=config['model_type'],posttrained=True,posttrained_basis='official named Instruct/Chat checkpoint; Qwen3-4B post-trained checkpoint rule',
        attempts=attempts,weights_downloaded=False))
(OUT/'MODEL_IDENTITIES.json').write_bytes((json.dumps(rows,indent=2)+'\n').encode())
print(json.dumps([dict(key=x['key'],revision=x['revision'],config_sha256=x['config_sha256']) for x in rows]))
