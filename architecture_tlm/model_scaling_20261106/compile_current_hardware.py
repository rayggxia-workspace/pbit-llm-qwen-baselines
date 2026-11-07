"""Three-model/two-chip workload manifest; no model load or simulated PPA."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,math
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_bytes())

def compile_plan(project):
    project=Path(project).resolve()
    helper=project/'architecture_tlm/equal_area_100_250_20261107/workload.py'
    spec=importlib.util.spec_from_file_location('current_shape_work',helper)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    target_path=helper.with_name('TARGETS.json');targets=load(target_path)
    sources={str(helper):sha(helper),str(target_path):sha(target_path)}
    identities={r['key']:r for r in load(HERE/'evidence/MODEL_IDENTITIES.json')}
    models={};cases=[]
    for key,filename in [('qwen3_4b','qwen3_4b_config.json'),('llama32_3b','llama32_3b_config.json'),('deepseek_7b','deepseek_7b_config.json')]:
        p=HERE/'evidence'/filename;c=load(p);sources[str(p)]=sha(p)
        model=dict(hidden=c['hidden_size'],ffn=c['intermediate_size'],layers=c['num_hidden_layers'],
            q_heads=c['num_attention_heads'],kv_heads=c['num_key_value_heads'],
            head_dim=c.get('head_dim',c['hidden_size']//c['num_attention_heads']),vocab=c['vocab_size'])
        assert model['q_heads']%model['kv_heads']==0
        assert model['hidden']%64==model['ffn']%64==0
        useful=module.counts(model,2048,128)
        H,F=model['hidden']//64,model['ffn']//64
        # One signedPoT exponent per64x64 tile, for g/u/down separately.
        metadata=3*H*F
        models[key]=dict(model_id=identities[key]['repo'],revision=identities[key]['revision'],
            config_sha256=sha(p),shape=model,tie_word_embeddings=c['tie_word_embeddings'],
            qk_norm=c.get('qk_norm',key=='qwen3_4b'),Q_per_KV=model['q_heads']//model['kv_heads'],
            KV_waves_on8_groups=math.ceil(model['kv_heads']/8),
            W8_exponent_metadata_bytes_per_layer=metadata,
            metadata_exceeds_legacy32KiB=metadata>32768,useful_work=useful,
            ideal_weight_stream_ms={k:v/136.4606/1e6 for k,v in useful['total_weight_bytes_including_head'].items()})
        for clock,t in targets['versions'].items():
            for scheme in ('SC_ising','BF16_dense','W8_dense','W8_screen'):
                cases.append(dict(model=key,clock_MHz=int(clock),scheme=scheme,
                    context=2048,batch=1,layers=model['layers'],
                    SRAM_KiB=t['SRAM_KiB'],area_target55_mm2=t['target_area55_mm2'],
                    physical_chip_fixed_across_models=True,include_embedding_and_lm_head=True,
                    external_config_sha256=targets['same_external_config_sha256'],
                    GU_samples=16 if scheme=='SC_ising' else None,
                    Wd_samples=32 if scheme=='SC_ising' else None,
                    K=128 if scheme in ('SC_ising','W8_screen') else None,
                    S=64 if scheme=='SC_ising' else None,
                    trace_contract='same reference candidate geometry for screened pair; explicit sampler timing/addresses' if scheme in ('SC_ising','W8_screen') else 'deterministic full context tiled onlineSoftmax/PV',
                    status='requires_parameterized_executing_adapter',
                    latency_ms=None,energy_mJ=None))
    assert len(cases)==24
    assert models['llama32_3b']['Q_per_KV']==3
    assert models['deepseek_7b']['KV_waves_on8_groups']==4
    assert models['deepseek_7b']['W8_exponent_metadata_bytes_per_layer']==33024
    return dict(status='workload_plan_not_simulated',scope='hardware_only_no_accuracy_or_GPU_baseline',
        weights_required=False,tokenizer_or_corpus_required=False,
        per_clock_chip_is_fixed=True,models=models,cases=cases,sources_sha256=sources,
        attention_data_policy='reference/synthetic traces and stated scenarios, not real model text statistics',
        seeds=[17,503,1009],uncertainty_cases=['concentrated','uniform','dispersed_memory_access'],
        no_quality_claim=True,no_new_PPA=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--project',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    r=compile_plan(a.project);a.out.write_bytes((json.dumps(r,indent=2)+'\n').encode())
    print(json.dumps(dict(status=r['status'],models=3,cases=len(r['cases']))))
