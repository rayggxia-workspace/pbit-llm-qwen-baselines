"""Shape-verified component budget, NOT token latency or total chip energy.

Prices are existing measured incremental tariffs. Missing costs stay excluded;
failed TT250 SC PPA is never converted to a valid price. Weight-stream floors
are mathematical bounds, not multiplication of the pilot's layer latency.
"""
from pathlib import Path
import argparse,hashlib,json

HERE=Path(__file__).resolve().parent
load=lambda p:json.loads(Path(p).read_bytes())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def compute(workspace):
    w=Path(workspace);fp=w/'architecture_tlm/ffn_digital_contract_20261107/PROFILES.json'
    sp=w/'architecture_tlm/module_refresh_20261107/FFN_PROFILE.json'
    f=load(fp)['profiles'];s=load(sp)['versions'];models=load(HERE/'CURRENT_WORKLOAD_PLAN.json')['models']
    results=[];prices={}
    for clock in (100,250):
        b=f[str(clock)+'_BF16']['prices'];d=f[str(clock)+'_W8']['prices']
        prices[str(clock)]=dict(BF16_FMA_incremental_pJ=b['pool']['incremental_pJ'],
            W8_decode_incremental_pJ=d['decode']['incremental_pJ'],
            A9W8_DOT64_incremental_pJ=d['integer_GU']['incremental_pJ'],
            SwiGLU_incremental_pJ=b['nonlinear']['incremental_pJ'],
            FP32_reduction_ADD_incremental_pJ=b['reduction']['incremental_pJ'])
    for key,entry in models.items():
        m=entry['shape'];H,F,L,Q,KV,D,V=[m[n] for n in ('hidden','ffn','layers','q_heads','kv_heads','head_dim','vocab')]
        ffn_MAC=L*3*H*F;projection_MAC=L*H*(2*Q+2*KV)*D;head_MAC=H*V
        BF16_bytes=2*(ffn_MAC+projection_MAC+head_MAC)
        W8_bytes=ffn_MAC+2*(projection_MAC+head_MAC)
        assert BF16_bytes==entry['useful_work']['total_weight_bytes_including_head']['BF16']
        # Metadata/embedding/norm/KV/burst padding are separate, not hidden in
        # the mandatory matrix-weight floor or charged as another full table.
        row=dict(model=key,model_id=entry['model_id'],revision=entry['revision'],
            config_sha256=entry['config_sha256'],shape=m,FFN_MAC=ffn_MAC,
            projection_MAC=projection_MAC,lm_head_MAC=head_MAC,
            matrix_weight_bytes=dict(BF16=BF16_bytes,SC_or_W8=W8_bytes),
            weight_only_time_floor_ms={name:n/136.46055437100213/1e6 for name,n in [('BF16',BF16_bytes),('SC_or_W8',W8_bytes)]},
            weight_only_energy_mJ_at4pJbit={name:n*32/1e9 for name,n in [('BF16',BF16_bytes),('SC_or_W8',W8_bytes)]},
            clocks={})
        for clock in (100,250):
            p=prices[str(clock)];core=s[str(clock)+'MHz']['core']
            digital_b=ffn_MAC*p['BF16_FMA_incremental_pJ']+L*F*p['SwiGLU_incremental_pJ']+3*L*(2*F+H)*p['FP32_reduction_ADD_incremental_pJ']
            digital_w=(L*2*H*F//64)*p['A9W8_DOT64_incremental_pJ']+L*H*F*(p['BF16_FMA_incremental_pJ']+p['W8_decode_incremental_pJ'])+L*F*p['SwiGLU_incremental_pJ']+3*L*H*p['FP32_reduction_ADD_incremental_pJ']
            sc=None
            if core is not None:
                gu=core['modes']['GU']['incremental_pJ_per_frame_over_seed17_waiting']
                wd=core['modes']['Wd']['incremental_pJ_per_frame_over_seed17_waiting']
                sc=(L*2*H*F//8192)*gu+(L*H*F//8192)*wd
            row['clocks'][str(clock)]=dict(FFN_internal_incremental_mJ=dict(BF16=digital_b/1e9,W8_mixed=digital_w/1e9,SC=None if sc is None else sc/1e9),
                projection_internal_incremental_mJ=projection_MAC*p['BF16_FMA_incremental_pJ']/1e9,
                lm_head_internal_incremental_mJ=head_MAC*p['BF16_FMA_incremental_pJ']/1e9,
                SC_price_status='valid_SS100_core_tariff' if sc is not None else 'pending_qualified_shortT_TT250_PPA')
        results.append(row)
    return dict(status='component_budget_not_complete_system_PPA',models=results,prices=prices,
        sources_sha256={str(fp.relative_to(w)).replace('\\','/'):sha(fp),str(sp.relative_to(w)).replace('\\','/'):sha(sp)},
        prices_include='Existing calibrated internal incremental activity above matched idle; no node scaling of power.',
        exclusions=['SRAM,KV and norm/metadata traffic,DRAM command-state and PHY/controller energy',
          'Attention logic and sampling/front/feedback/capture','host format/scale selection/control/clock-tree and full residency',
          'actual end-to-end latency and average power','model accuracy or task quality'],
        safeguards=['Do not sum these into a claimed total system energy','Do not multiply a single-layer pilot into claimed token time',
                    'No valid TT250 SC core tariff is synthesized from failed timing data'])

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    r=compute(a.workspace);a.out.write_bytes((json.dumps(r,indent=2)+'\n').encode());print(json.dumps(dict(status=r['status'],models=len(r['models']))))
