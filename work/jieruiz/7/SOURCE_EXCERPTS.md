# Current local FFN source excerpts

These are audit inputs, not a newly integrated/published v5/v6 runtime. Original full-file hashes are in evidence.json.

## memory_schedule_v5.py:166-188 (BankedMixin.vectors)

```python
def vectors(self,ready,ops=0,nonlinear=0):
    if self.stream_argmax_done and ops==self.shape['vocab_size'] and nonlinear==0:
        self.stream_argmax_done=False;return ready
    d=self.cfg['digital'];n=ops*d['vector_interface_bytes_per_op']+nonlinear*d['nonlinear_interface_bytes_per_op']
    live=min(n,max(4096,self.shape['intermediate_size']*8))
    self.other_peak=max(self.other_peak,65536+live)
    if 65536+live>self.work_mem.capacity:raise ValueError('vector workspace overflow')
    # Interface is processed in finite chunks, not a full n-byte allocation.
    t=ready;remaining=math.ceil(n/2)
    while remaining:
        size=min(remaining,live)
        t=self.work_mem.transfer(t,65536,size,False,'vector_input');remaining-=size
    start=max(t,self.digital_free)
    cycles=math.ceil(ops/d['vector_ops_per_cycle'])+math.ceil(nonlinear/d['nonlinear_ops_per_cycle'])
    t=start+cycles*self.period;self.digital_free=t
    self.actions['vector_ops']+=ops;self.actions['nonlinear_ops']+=nonlinear
    self.energy['digital_vector']+=ops*d['vector_op_pJ']*1e-12
    self.energy['digital_nonlinear']+=nonlinear*d['nonlinear_op_pJ']*1e-12
    remaining=math.ceil(n/2)
    while remaining:
        size=min(remaining,live)
        t=self.work_mem.transfer(t,65536,size,True,'vector_output');remaining-=size
    return t
```

## memory_schedule_v5.py:219-247 (BankedMixin.stochastic_matrix)

```python
def stochastic_matrix(self,name,inp,out,ready):
    if inp%64 or out%64:raise ValueError('64x64 mapping required')
    T=self.cfg['samples'];E=self.engines;current=ready;groups=out//64
    self.other_peak=max(self.other_peak,out*4+64*9//8)
    for k in range(inp//64):
        encoded=self.vectors(current,64*self.cfg['sc_cost']['input_encode_vector_ops'])
        current=self.rng_hierarchy.begin_tile(encoded,(self.tile_serial,name,k));self.tile_serial+=1
        fetch_at=current
        for j in range(0,groups,E):
            count=min(E,groups-j)
            loaded=self.weights.tile_ready(name,(k*groups+j)*4096,count*4096,fetch_at,tiles=count)
            start=self.rng_hierarchy.restore_wave(max(current,loaded))
            kernel=(T+1)*self.period
            _,rng_time=self.rng_hierarchy.input_wave(start,count,T)
            duration=max(kernel,rng_time);current=start+duration
            self.weights.release(current)
            self.raw_bits+=T*8;self.sc_compute_ns+=kernel;self.rng_service_ns+=rng_time
            self.sc_active_engine_ns+=count*kernel;self.sc_wait_engine_ns+=count*(duration-kernel)
            self.actions['sc_tile_frames']+=count;self.actions['sc_product_trials']+=count*4096*T
            self.energy['SC_logic_active']+=self.body_W*count*kernel*1e-9
            self.energy['SC_shared_input_frontend']+=self.front_W*kernel*1e-9
            self.energy['SC_wait']+=count*max(0,duration-kernel)*self.cfg['sc_cost']['wait_W_per_engine']*1e-9
            fetch_at=start if self.cfg['double_buffer'] else current
        self.rng_hierarchy.end_tile()
        current=self.vectors(current,out*self.cfg['sc_cost']['finalize_vector_ops_per_partial'])
        current=self.work_mem.transfer(current,0,out*4,False,'partial_read')
        current=self.work_mem.transfer(current,0,out*4,True,'partial_write')
        self.traffic['scratch_partial_bytes']+=2*out*4
    return current
```

## system_decode.py:322-441 (DecodeModel.run)

```python
def run(self):
    s=self.shape;h=s['hidden_size'];m=s['intermediate_size'];v=s['vocab_size'];layers=s['num_hidden_layers']
    kv_dim=s['num_key_value_heads']*(h//s['num_attention_heads'])
    cursor=0.;token_times=[]
    for token in range(self.cfg['decode_tokens']):
        begin=cursor
        if token==0 and self.rng_hierarchy:
            cursor=self.stamp('RNG_startup',cursor,self.rng_hierarchy.ensure_seeded(cursor),token=token)
        L=self.cfg['context_tokens']+token
        # Tied embedding and lm_head share the same cache address space.
        t=self.weights.request('lm_head',7*h*2,h*2,cursor)
        cursor=self.stamp('embedding',cursor,t,token=token)
        t=self.vectors(cursor,nonlinear=h//s['num_attention_heads'])
        cursor=self.stamp('norm_rope_residual',cursor,t,token=token)
        for layer in range(layers):
            t=self.vectors(cursor,4*h,1)
            cursor=self.stamp('norm_rope_residual',cursor,t,layer,token)
            t=self.digital_matrix(f'L{layer}/qkv',h,h+2*kv_dim,cursor)
            cursor=self.stamp('QKV_projection',cursor,t,layer,token)
            t=self.vectors(cursor,3*(h+kv_dim)+(h+2*kv_dim)) # RoPE plus QKV biases
            address=self.ext.layout.address(f'L{layer}/KV',(L-1)*self.ext.layout.kv_token_bytes,2*kv_dim*2)
            t=self.ext.access(t,2*kv_dim*2,'KV',True,address=address)
            cursor=self.stamp('norm_rope_residual',cursor,t,layer,token)
            t=self.attention(cursor,L,layer)
            cursor=self.stamp('QK_softmax_PV',cursor,t,layer,token)
            t=self.digital_matrix(f'L{layer}/Wo',h,h,cursor)
            cursor=self.stamp('output_projection',cursor,t,layer,token)
            t=self.vectors(cursor,5*h,1)
            cursor=self.stamp('norm_rope_residual',cursor,t,layer,token)
            if self.engines:
                t=self.stochastic_matrix(f'L{layer}/gu',h,2*m,cursor)
                cursor=self.stamp('FFN_gate_up',cursor,t,layer,token)
                # Normal SiLU(g)*u, then fixed Sz encoding in both SC exploratory paths.
                t=self.vectors(cursor,2*m,m)
                cursor=self.stamp('FFN_SwiGLU',cursor,t,layer,token)
                t=self.stochastic_matrix(f'L{layer}/down',m,h,cursor)
                cursor=self.stamp('FFN_down',cursor,t,layer,token)
            else:
                bpw=1 if self.variant=='digital_int8_ffn' else 2
                t=self.digital_matrix(f'L{layer}/gu',h,2*m,cursor,bpw)
                cursor=self.stamp('FFN_gate_up',cursor,t,layer,token)
                t=self.vectors(cursor,2*m,m)
                cursor=self.stamp('FFN_SwiGLU',cursor,t,layer,token)
                t=self.digital_matrix(f'L{layer}/down',m,h,cursor,bpw)
                cursor=self.stamp('FFN_down',cursor,t,layer,token)
            t=self.vectors(cursor,h)
            cursor=self.stamp('norm_rope_residual',cursor,t,layer,token)
        t=self.vectors(cursor,4*h,1)
        cursor=self.stamp('norm_rope_residual',cursor,t,token=token)
        t=self.digital_matrix('lm_head',h,v,cursor)
        cursor=self.stamp('lm_head',cursor,t,token=token)
        t=self.vectors(cursor,v) # greedy argmax, no vocabulary softmax
        cursor=self.stamp('token_select',cursor,t,token=token)
        token_times.append(cursor-begin)
    seconds=cursor*1e-9
    external_diagnostic=self.ext.finish(cursor) if hasattr(self.ext,'finish') else {'backend':'simplified Link'}
    # All standby terms are explicit parameters. No weight DFF added here.
    w=self.cfg['weight_macro'];sp=self.cfg['scratchpad'];r=self.cfg['rng'];sc=self.cfg['sc_cost']
    self.energy['weight_sram_leakage']+=w['cache_MiB']*w['leakage_W_per_MiB']*seconds
    self.energy['weight_macro_hold']+=self.engines*w['active_tile_hold_W']*seconds
    self.energy['scratch_leakage']+=sp['capacity_MiB']*sp['leakage_W_per_MiB']*seconds
    self.energy['digital_idle']+=self.cfg['digital']['idle_W']*seconds
    if not hasattr(self.ext,'finish'):
        self.energy['external_background']+=self.cfg['external_memory']['background_W']*seconds
    self.energy['control_interconnect']+=self.cfg['control_interconnect_W']*seconds
    rng_diagnostic=None
    if self.engines:
        rate=r['sources']*r['source_clock_hz']*r['raw_bits_per_source_cycle']
        power=r['sources']*r['source_power_W']
        if self.rng_hierarchy:
            rng_diagnostic=self.rng_hierarchy.finish(cursor)
            for key,value in rng_diagnostic['energy_J'].items():self.energy[key]+=value
            rate=rng_diagnostic['nominal_output_capacity_bits']/seconds
        else:
            self.energy['RNG_sources']+=power*(seconds if r['always_running'] else self.rng_service_ns*1e-9)
            self.energy['RNG_fabric_FIFO']+=r['fifo_distribution_W']*seconds
        self.energy['SC_idle']+=max(0,self.engines*cursor-self.sc_active_engine_ns-self.sc_wait_engine_ns)*sc['idle_W_per_engine']*1e-9
        assert self.raw_bits<=rate*seconds*(1+1e-9)
    else:rate=0.
    count=len(token_times)
    area=(w['cache_MiB']*w['area_mm2_per_MiB']+sp['capacity_MiB']*sp['area_mm2_per_MiB']+
          self.cfg['digital']['area_mm2']+self.engines*(sc['logic_area_mm2_per_engine']+w['active_tile_area_mm2'])+
          (r['sources']*r['area_mm2_per_source'] if self.engines else 0))
    if rng_diagnostic:
        area+=rng_diagnostic['area_mm2']-r['sources']*r['area_mm2_per_source']
    quality={'digital_bf16':11.652735,'digital_int8_ffn':11.681130}.get(self.variant)
    if self.variant=='dual_sc_sz':quality={256:127803.483024,1024:42.762909,4096:13.948997}.get(self.cfg['samples'])
    result=dict(variant=self.variant,scope='batch1 decode, full24 layers and lm_head; no prefill',
        implementation='Python macro-level LT model, not SystemC/TLM2 or RTL',
        config=self.cfg,quality_reference_ppl=quality,
        weight_validity_contract=dict(per_weight_bits=0,energy_J=0,area_mm2=0,
            policy='complete tile load before compute; zero-pad tail; no partial/uninitialized use',
            note='legacy G1 costs never included q3 SRAM validity bank; no subtraction credit'),
        stochastic_core_power_provenance=('fixed-weight G1 per-cycle replicated with assumed shared frontend'
            if self.variant=='fixed_sc_exact' else 'adjustable proxy from fixed-weight G1, NOT measured dual-stream core'
            if self.variant=='dual_sc_sz' else 'no stochastic core'),
        stochastic_activity_case=self.profile['case'] if self.engines else None,
        sample_power_extrapolated=self.engines>0 and self.cfg['samples']!=4096,
        quality_warning='numerical reference only; timing/storage/cost assumptions do not validate hardware precision or correlation',
        metrics=dict(mean_TPOT_ms=sum(token_times)/count/1e6,first_decode_ms=token_times[0]/1e6,
            subsequent_decode_ms=token_times[1]/1e6 if count>1 else None,
            tokens_per_second=count/seconds,scenario_mJ_per_token=sum(self.energy.values())/count*1e3,
            parameterized_area_mm2=area,area_budget_feasible=area<=self.cfg['area_budget_mm2'],TTFT_ms=None),
        energy_J=dict(self.energy),time_ns=dict(self.time_categories),actions=dict(self.actions),traffic=dict(self.traffic),
        external_memory_model=external_diagnostic,
        weight_cache=dict(hits=self.weights.hits,misses=self.weights.misses,peak_bytes=self.weights.peak),
        bounds=dict(SC_wave_compute_ms=self.sc_compute_ns/1e6,RNG_service_ms=self.rng_service_ns/1e6,
            replay_service_ms=self.replay_ns/1e6,raw_rng_bits=self.raw_bits,
            source_nominal_capacity_bits=rate*seconds,scratch_peak_bytes=self.scratch_peak,
            local_weight_resident_bits=self.engines*w['local_resident_bits_per_tile']),
        energy_complete_measured=False,scenario_cost_coverage='all configured terms charged; unmodeled PHY/CTS/startup/host/prefill excluded',
        events=self.events,
        source_hashes={'system_decode.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'evidence_contract.json':hashlib.sha256((ROOT/'configs/evidence_contract.json').read_bytes()).hexdigest()})
    if rng_diagnostic:
        result['rng_hierarchy']=rng_diagnostic
        result['quality_warning']+='; hierarchical Bivium streams NOT validated by the inherited PPL'
        result['scenario_cost_coverage']='configured scenario costs including RNG startup; uncalibrated local RNG/analog/root costs, SC dual proxy, no PHY/CTS/host/prefill'
        result['source_hashes']['rng_hierarchy.py']=hashlib.sha256((ROOT/'rng_hierarchy.py').read_bytes()).hexdigest()
    return result
```
