"""Same-GPU FlashInfer/SDPA ablation; dependencies/weights remain frozen.

No training, quantization or PPL. Failed numerical gates remain visible and do
not get promoted to accepted full-model energy/performance results.
"""
from pathlib import Path
import argparse,contextlib,gc,hashlib,importlib.metadata,json,os,sys,time,types
from contract import BACKENDS,validate,guard_values


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,indent=2,allow_nan=False);f.write('\n')
def emit(**x):print(json.dumps(x),flush=True)


def load(root):
    manifest=json.loads((root/'SOURCE_MANIFEST.json').read_bytes())
    for name,digest in manifest['files_sha256'].items():assert sha(root/name)==digest,name
    sys.path.insert(0,str(root/'dependencies'))
    import controlled_remeasure as c
    c.load_dependencies(root/'dependencies')
    return c


def core(c,fi,backend,q,k,v,scale):
    """Q[Hq,D], K/V[Hkv,L,D]; already QK-normalized and RoPE-applied."""
    if backend.startswith('flashinfer'):
        return fi.single_decode_with_kv_cache(q,k,v,kv_layout='HND',
            pos_encoding_mode='NONE',use_tensor_cores=backend.endswith('tensor'),sm_scale=scale)
    from torch.nn.attention import SDPBackend,sdpa_kernel
    if backend=='sdpa_expanded':
        factor=q.shape[0]//k.shape[0]
        # Match the installed HF repeat_kv path rather than a different copy.
        from transformers.models.qwen3.modeling_qwen3 import repeat_kv
        kk=repeat_kv(k.unsqueeze(0),factor);vv=repeat_kv(v.unsqueeze(0),factor)
        with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
            return c.F.scaled_dot_product_attention(q[None,:,None,:],kk,vv,
                dropout_p=0.,is_causal=False,scale=scale)[0,:,0,:]
    with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
        return c.F.scaled_dot_product_attention(q[None,:,None,:],k[None],v[None],
            dropout_p=0.,is_causal=False,scale=scale,enable_gqa=True)[0,:,0,:]


class Adapter:
    def __init__(self,c,fi,model,legacy,length,backend,*,capacity=None,capture=False):
        self.c=c;self.fi=fi;self.model=model;self.length=length;self.backend=backend;self.capture=capture;self.calls=[]
        self.cache=c.StaticCache(config=model.config,max_batch_size=1,max_cache_len=capacity or length,
                                  device='cuda',dtype=c.torch.bfloat16)
        positions=c.torch.arange(legacy[0][0].shape[-2],device='cuda')
        for i,(key,value) in enumerate(legacy):self.cache.update(key,value,i,{'cache_position':positions})
        self.position=c.torch.tensor([length-1],device='cuda')

    def __enter__(self):
        c=self.c;self.registry=c.q3.ALL_ATTENTION_FUNCTIONS;self.old=self.registry['sdpa']
        self.mask=self.model.model._update_causal_mask;owner=self
        def attention(module,query,key,value,attention_mask,dropout=0.,scaling=None,**kwargs):
            assert query.shape[:3]==(1,32,1) and key.shape[1]==value.shape[1]==8
            assert attention_mask is None and dropout==0. and not module.training
            q=query[0,:,0,:];k=key[0,:,:owner.length,:];v=value[0,:,:owner.length,:]
            # HND strides are forwarded to kernels. No prefix contiguous-copy.
            if owner.capture:owner.calls.append((q.clone(),k,v,scaling))
            y=core(c,owner.fi,owner.backend,q,k,v,scaling)
            return y[None,None,:,:],None
        def mask(model,attention_mask,input_tensor,cache_position,past_key_values,output_attentions=False):
            assert input_tensor.shape[:2]==(1,1) and attention_mask is None
            assert past_key_values is owner.cache and not output_attentions
            return None
        if isinstance(self.registry,dict):self.registry['sdpa']=attention
        else:self.registry.register('sdpa',attention)
        self.model.model._update_causal_mask=types.MethodType(mask,self.model.model)
        return self

    def __exit__(self,*args):
        if isinstance(self.registry,dict):self.registry['sdpa']=self.old
        else:self.registry.register('sdpa',self.old)
        self.model.model._update_causal_mask=self.mask

    def run(self,token):
        return self.model(input_ids=token,past_key_values=self.cache,use_cache=True,
            cache_position=self.position,position_ids=self.position.unsqueeze(0),return_dict=True,logits_to_keep=1)


def compare(c,r,y):
    r=r.float();y=y.float()
    rel=((r-y).norm()/r.norm()).item()
    out=guard_values(rel,c.torch.equal(r.argmax(-1),y.argmax(-1)))
    out.update(max_abs=(r-y).abs().max().item(),bitwise_equal=c.torch.equal(r,y))
    return out


def profile(c,fn,folder):
    from torch.profiler import profile,ProfilerActivity
    with profile(activities=[ProfilerActivity.CPU,ProfilerActivity.CUDA]) as p:
        for _ in range(3):fn()
        c.torch.cuda.synchronize()
    names=sorted({e.name for e in p.events() if str(e.device_type).endswith('CUDA')})
    assert names
    p.export_chrome_trace(str(folder/'CORE_TRACE.json'))
    return dict(kernel_names=names,flash_kernel_observed=any('flash' in n.lower() for n in names))


def native(c,fi,model,legacy,token,backend,meter,context,steps,repeats):
    rows=[]
    for rep in range(repeats):
        op=Adapter(c,fi,model,legacy,context,backend,capacity=context+steps-1)
        next_id=token.clone();generated=[]
        with op:
            # Prewarm kernels with the SAME padded HND strides, then reset the
            # position and cache entry. It does not change the fixed prefix.
            op.run(next_id);c.torch.cuda.synchronize()
            c.exclusive(meter.uuid);before=meter.state();e0=meter.energy_mJ();t0=time.perf_counter()
            for i in range(steps):
                op.length=context+i;op.position.fill_(context+i-1)
                out=op.run(next_id);next_id=out.logits[:,-1].argmax(-1,keepdim=True);generated.append(next_id)
            c.torch.cuda.synchronize();t1=time.perf_counter();e1=meter.energy_mJ()
        row=c.counter_result(e0,e1,t0,t1,steps)
        row.update(repeat=rep,state_before=before,state_after=meter.state(),first_KV_length=context,
                   last_KV_length=context+steps-1,generated_ids_sha256=c.tensor_hash(c.torch.cat(generated,-1)),
                   primary_energy_window_suitable=t1-t0>=3.,argmax_included=True,prefill_included=False,
                   growing_KV=True,cuda_graph=False)
        rows.append(row);emit(event='native',backend=backend,context=context,repeat=rep,ms=row['wall_ms_per_item'])
        del op,out,next_id,generated;gc.collect();c.torch.cuda.empty_cache()
    assert len({r['generated_ids_sha256'] for r in rows})==1
    return dict(repeats=rows,summary=c.summarize(rows),scope='B1 continuous autoregressive decode;256 steps;static capacity,valid prefix only;includes argmax and growing KV')


def main():
    p=argparse.ArgumentParser();p.add_argument('--prepared',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--root',type=Path,required=True)
    a=p.parse_args();root=a.root.resolve();cfg=validate(json.loads((root/'CONFIG.json').read_bytes()))
    c=load(root);torch=c.torch
    assert 'SLURM_JOB_ID' in os.environ and torch.cuda.device_count()==1
    import flashinfer as fi
    from transformers import AutoModelForCausalLM,AutoTokenizer
    assert importlib.metadata.version('flashinfer-python')==cfg['flashinfer_version']
    a.output.mkdir(parents=True,exist_ok=False)
    prepared,model_path=c.verify(a.prepared)
    tok=AutoTokenizer.from_pretrained(str(model_path),local_files_only=True)
    ids=torch.tensor(tok(Path(prepared['data']['wiki.test.raw']['path']).read_text(encoding='utf-8'),add_special_tokens=False).input_ids,dtype=torch.long)
    assert c.tensor_hash(ids)==prepared['test_token_ids_sha256_le_int64']
    props=torch.cuda.get_device_properties(0);uuid=str(props.uuid)
    if not uuid.startswith('GPU-'):uuid='GPU-'+uuid
    c.exclusive(uuid);meter=c.Nvml(uuid)
    env=dict(job=os.environ['SLURM_JOB_ID'],gpu=props.name,uuid_sha256=hashlib.sha256(uuid.encode()).hexdigest(),
        torch=torch.__version__,transformers=importlib.metadata.version('transformers'),flashinfer=cfg['flashinfer_version'],
        model_revision=prepared['revision'],prepared_sha256=sha(a.prepared),input_sha256=c.tensor_hash(ids),
        config_sha256=sha(root/'CONFIG.json'),source_manifest_sha256=sha(root/'SOURCE_MANIFEST.json'),
        model_files_sha256={x['name']:x['sha256'] for x in prepared['files']},
        isolation='Only the single Slurm-allocated GPU;refuse foreign compute processes',
        no_quantization=True,prefill_in_decode_window=False,whole_energy='NVML cumulative board energy including on-board memory',
        engine_scope=cfg['scope'])
    save(a.output/'ENVIRONMENT.json',env)
    model=AutoModelForCausalLM.from_pretrained(str(model_path),torch_dtype=torch.bfloat16,attn_implementation='sdpa',local_files_only=True).eval().to('cuda')
    statuses=[]
    with torch.inference_mode():
      for context in cfg['contexts']:
        folder=a.output/str(context);folder.mkdir();guards={b:[] for b in BACKENDS};captures=None;benchmark_prefix=None
        # Three disjoint real-text positions. Every backend sees the SAME
        # unmodified-model KV and decode input; no greedy divergence in gates.
        for offset in cfg['probe_offsets']:
            legacy,token,prefill=c.build_prefix(model,ids[offset:offset+context-1][None].to('cuda'))
            original=c.one(model,legacy,token);reference=original.logits.clone()
            if offset==0:
                next_token=reference[:,-1].argmax(-1,keepdim=True)
                legacy_next=original.past_key_values.to_legacy_cache()
                reference_next=c.one(model,legacy_next,next_token).logits.clone()
                del legacy_next
            del original
            for backend in BACKENDS:
                try:
                    op=Adapter(c,fi,model,legacy,context,backend,capture=backend=='sdpa_expanded' and offset==0)
                    with op:y=op.run(token).logits.clone()
                    g=compare(c,reference,y);g.update(offset=offset,kind='fixed_HND',input_token_sha256=c.tensor_hash(ids[offset:offset+context-1]))
                    if backend=='sdpa_expanded':assert g['bitwise_equal'],'static-only SDPA must remain bitwise identical'
                    if op.capture:
                        assert len(op.calls)==36;captures=op.calls
                    guards[backend].append(g)
                    del op,y
                    if offset==0:
                        # Growing decode has larger HND head strides than a
                        # compact fixed cache. Validate that actual interface
                        # and two causal updates before any timing window.
                        growing=Adapter(c,fi,model,legacy,context,backend,capacity=context+cfg['native_steps']-1)
                        with growing:
                            y=growing.run(token).logits
                            g0=compare(c,reference,y);g0.update(offset=0,kind='padded_growing_step0')
                            growing.length=context+1;growing.position.fill_(context)
                            y=growing.run(next_token).logits
                            g1=compare(c,reference_next,y);g1.update(offset=0,kind='padded_growing_step1')
                        guards[backend].extend([g0,g1]);del growing,y
                except Exception as e:
                    guards[backend].append(dict(offset=offset,accepted=False,error_type=type(e).__name__,error=str(e)))
            if offset==0:benchmark_prefix=(legacy,token)
            del legacy,token,reference
            if offset==0:del next_token,reference_next
            gc.collect();torch.cuda.empty_cache()
        save(folder/'LOGIT_GUARDS.json',guards);assert captures is not None and benchmark_prefix is not None
        # Independent FP32-math oracle for first/middle/last real layer inputs.
        from torch.nn.attention import SDPBackend,sdpa_kernel
        module_guards={b:[] for b in BACKENDS}
        for layer in (0,17,35):
            q,k,v,scale=captures[layer]
            with sdpa_kernel(SDPBackend.MATH):
                oracle=c.F.scaled_dot_product_attention(q[None,:,None,:].float(),k[None].float(),v[None].float(),dropout_p=0.,is_causal=False,scale=scale,enable_gqa=True)[0,:,0,:]
            for backend in BACKENDS:
                try:
                    y=core(c,fi,backend,q,k,v,scale);rel=((y.float()-oracle).norm()/oracle.norm()).item()
                    module_guards[backend].append(dict(layer=layer,relative_L2=rel,accepted=rel<=cfg['module_relative_L2_max']))
                except Exception as e:module_guards[backend].append(dict(layer=layer,accepted=False,error=str(e)))
        save(folder/'MODULE_GUARDS.json',module_guards)
        legacy,token=benchmark_prefix
        for backend in BACKENDS:
            row=dict(context=context,backend=backend,whole_gate=all(g['accepted'] for g in guards[backend]),module_gate=all(g['accepted'] for g in module_guards[backend]))
            out=folder/backend;out.mkdir();emit(event='backend_start',**row)
            c.exclusive(uuid)
            if row['module_gate']:
                def module_work():
                    for q,k,v,scale in captures:result=core(c,fi,backend,q,k,v,scale)
                    return result
                mg,mo=c.graph_callable(module_work)
                result=c.series(mg.replay,meter,cfg['module_window_s'],cfg['repeats'],8.,25.,telemetry=True)
                result['scope']='isolated attention-core replay,36 real layer inputs;not additive whole-model rail energy'
                save(out/'ATTENTION_CORE_GRAPH.json',result);save(out/'KERNELS.json',profile(c,module_work,out))
                del mg,mo,module_work;gc.collect();torch.cuda.empty_cache()
            if row['whole_gate'] and row['module_gate']:
                op=Adapter(c,fi,model,legacy,context,backend)
                with op:
                    work=lambda:op.run(token)
                    expected=work().logits.clone();graph,y=c.graph_callable(work)
                    assert torch.equal(expected,y.logits),'same-backend Graph/eager mismatch'
                    result=c.series(graph.replay,meter,cfg['whole_window_s'],cfg['repeats'],15.,60.,telemetry=True)
                    result['scope']='fixed single-token full-model CUDA Graph forward;no argmax or KV growth'
                    save(out/'WHOLE_FIXED_GRAPH.json',result)
                    # Profile outside the primary energy/time window.
                    save(out/'WHOLE_MODULE_TIMES.json',c.profile(model,work,expected,out,steps=3))
                    del graph,y,expected,work
                del op;gc.collect();torch.cuda.empty_cache()
                save(out/'NATIVE_GREEDY.json',native(c,fi,model,legacy,token,backend,meter,context,cfg['native_steps'],cfg['repeats']))
                row['status']='completed'
            else:row['status']='numerical_or_support_gate_failed';row['whole_formal_measurement_skipped']=True
            save(out/'STATUS.json',row);statuses.append(row)
            c.exclusive(uuid)
        del captures,benchmark_prefix,legacy,token;gc.collect();torch.cuda.empty_cache()
    c.exclusive(uuid)
    files={str(f.relative_to(a.output)):dict(sha256=sha(f),bytes=f.stat().st_size) for f in a.output.rglob('*') if f.is_file()}
    save(a.output/'ARTIFACT_MANIFEST.json',files)
    save(a.output/'COMPLETED.json',dict(status='completed_with_documented_gates',job=os.environ['SLURM_JOB_ID'],
        manifest_sha256=sha(a.output/'ARTIFACT_MANIFEST.json'),cases=statuses,
        failed_cases=[r for r in statuses if r['status']!='completed'],
        note='failed numerical candidates are not accepted energy/performance results;no vLLM/SGLang or PPL claim'))
    emit(event='all_finished',cases=statuses)


if __name__=='__main__':main()
