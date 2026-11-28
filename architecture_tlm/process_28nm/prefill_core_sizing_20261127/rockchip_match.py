"""Matched short-prompt resource budget; analytical, not a prefill bank replay.

Reuses frozen, measured 28nm prices and the old shape/contract fixture.
No weight download, numeric quality simulation, or default configuration mutation.
"""
from pathlib import Path
import hashlib
import json
import math

D = Path(__file__).resolve().parent


def shape(name):
    if name == 'MiniCPM3-4B':
        # OpenBMB config and actual MLA q_a/q_b/kv_a/kv_b/o implementation.
        return dict(layers=62, H=2560, I=6400, vocab=73448, heads=40,
                    qdim=96, vdim=64,
                    projections=[(2560,768),(768,3840),(2560,288),
                                 (256,5120),(2560,2560)])
    return dict(layers=36,H=2560,I=9728,vocab=151936,heads=32,
                qdim=128,vdim=128,
                projections=[(2560,4096),(2560,1024),(2560,1024),(4096,2560)])


def counts(m, N=128):
    L,H,I = (m[k] for k in ['layers','H','I'])
    assert H % 128 == 0 and I % 64 == 0
    gu = N*L*(I//64)*(H//64)  # one GU frame:64g +64u
    wd = N*L*(H//128)*(I//64)
    final_gu=N*L*(I//64); final_wd=N*L*(H//128)
    ff_weights=L*3*H*I
    q_weights=L*sum(k*n for k,n in m['projections'])
    pairs=N*(N+1)//2
    return dict(gu_frames=gu,wd_frames=wd,ffn_mac=N*ff_weights,
        projection_mac=N*q_weights,
        attention_mac=L*pairs*m['heads']*(m['qdim']+m['vdim']),
        ffn_weight_bytes=ff_weights,projection_weight_bytes=q_weights,
        final_gu=final_gu,final_wd=final_wd,
        state_values=(gu+wd)*128,
        state_RW_bytes=(2*(gu+wd)-2*(final_gu+final_wd))*128*8,
        softmax_vector_ops=L*pairs*m['heads']*8,
        norm_rope_proxy_ops=L*N*(16*H+8*m['heads']*(m['qdim']+m['vdim'])),
        head_MAC=H*m['vocab'],head_weight_bytes=H*m['vocab'])


def estimate(name, *, cores, bw, rows=32, gu_T=16, wd_T=32,
             digital_copies=8, vector_lanes=32, state_workers=2,
             state_banks=64, prices):
    N=128; f=250e6; m=shape(name); w=counts(m,N)
    sc=(w['gu_frames']*(gu_T+2)+w['wd_frames']*(wd_T+2))/(f*cores)
    chunks=math.ceil(N/rows)
    loads=(w['gu_frames']+w['wd_frames'])//N*chunks
    program=loads*32/(f*cores)
    state_alu=w['state_values']/(state_workers*32*f)
    payload=cores*rows*128*8
    state_banks=max(state_banks,math.ceil(payload/4096))
    state_bw=state_banks*16*f
    state_mem=w['state_RW_bytes']/state_bw
    ff_dram=w['ffn_weight_bytes']*chunks/(bw*1e9)
    ws=prices['WS_B16']
    mac_rate=digital_copies*ws['task_DOT64']*64/(ws['task_ns']*1e-9)
    proj_compute=w['projection_mac']/mac_rate
    # Digital task is the measured16-row workload, independent of P-CIM rows.
    digital_chunks=math.ceil(N/16)
    proj_dram=w['projection_weight_bytes']*digital_chunks/(bw*1e9)
    soft=w['softmax_vector_ops']/(vector_lanes*f)
    kv=m['layers']*m['heads']*(m['qdim']+m['vdim'])*sum(min(N,t+16) for t in range(0,N,16))
    attention=max(w['attention_mac']/mac_rate+soft,kv/(bw*1e9))
    codec=(w['final_gu']*15+w['final_wd']*9)/f
    norm=w['norm_rope_proxy_ops']/(vector_lanes*f)
    # Charge a finite, explicit staging proxy; BF16 residuals and metadata included.
    io=N*m['layers']*(8*m['H']+8*m['heads']*m['qdim']+5*m['I']+4*m['heads']*m['vdim'])
    head=max(w['head_MAC']/mac_rate,w['head_weight_bytes']/(bw*1e9))
    other=dict(projections=max(proj_compute,proj_dram),attention=attention,
               norm_rope_residual=norm,ffn_encoding=codec,
               activation_staging=io/(bw*1e9),last_token_head=head)
    ff=max(sc+program,state_alu,state_mem,ff_dram)
    ff_serial=max(sc+program,state_alu+state_mem,ff_dram)
    assert payload <= state_banks*4096
    #10bit internal code includes sign/scale metadata; numeric activation remains A8.
    #Reserve X,paired g/u,BF16 residual,8 digital double-buffer tiles and DMA.
    workspace=rows*(2*m['I']+m['H'])*10//8+rows*m['H']*2+digital_copies*2*8192+16384
    physical_workspace=math.ceil(workspace/(256*1024))*256*1024
    return dict(model=name,cores=cores,GU_T=gu_T,Wd_T=wd_T,rows_per_weight=rows,
        clock_MHz=250,DRAM_peak_GBs=33.792,DRAM_effective_GBs=bw,
        digital_WS16_copies=digital_copies,digital_useful_TOPS=mac_rate*2/1e12,
        vector_lanes=vector_lanes,state_workers32=state_workers,
        state_banks4KiB=state_banks,state_SRAM_GBs=state_bw/1e9,
        state_payload_KiB=payload/1024,state_physical_KiB=state_banks*4,
        workspace_payload_lower_bound_bytes=workspace,
        workspace_provisioned_KiB=physical_workspace/1024,
        ff_floors_s=dict(compute=sc,program=program,state_ALU=state_alu,
                         state_SRAM=state_mem,DRAM=ff_dram),
        FFN_s=ff,other_stages_s=other,
        total_s=ff+sum(other.values()),
        serial_state_sensitivity_s=ff_serial+sum(other.values()),
        PCIM_compute_area_reference_mm2=cores*prices['SC_GU']['area_mm2'],
        digital_compute_area_reference_mm2=digital_copies*ws['area_mm2'],
        covers='128-token prefill and last-position full head;not64 decode steps')


def main():
    prices=json.loads((D/'AREA_REVIEW_INPUTS.json').read_bytes())
    cases=[estimate(n,cores=c,bw=27,prices=prices) for n in ['MiniCPM3-4B','Qwen3-4B'] for c in [4,5,6,8]]
    sensitivity=[estimate('MiniCPM3-4B',cores=c,bw=bw,rows=r,prices=prices)
                 for c in [5,6,8] for bw in [20,27,30] for r in [16,32,64]]
    sampling=[]
    for g,d in [(8,32),(16,32),(32,64),(64,128)]:
        candidates=[estimate('MiniCPM3-4B',cores=c,bw=27,gu_T=g,wd_T=d,prices=prices)
                    for c in range(1,33)]
        winners=[x for x in candidates if x['total_s'] <= 1.40849]
        sampling.append(dict(GU_T=g,Wd_T=d,first_passing_budget=winners[0] if winners else None))
    assert counts(shape('MiniCPM3-4B'))['gu_frames']==31744000
    assert counts(shape('MiniCPM3-4B'))['wd_frames']==15872000
    assert counts(shape('MiniCPM3-4B'))['ffn_mac']==(31744000+15872000)*8192
    assert abs((31744000*18+15872000*34)/250e6-4.44416)<1e-10
    for c in cases:
        assert abs(c['total_s']-c['FFN_s']-sum(c['other_stages_s'].values()))<1e-10
        assert c['serial_state_sensitivity_s']>=c['total_s']-1e-10
    out=dict(status='analytical_matched_input_budget_not_hardware_or_model_measurement',
        date='2026-11-27',reference=dict(platform='RK3588',model='MiniCPM3-4B',
        matrix_weights_bits=8,matrix_activation_bits=8,prompt_tokens=128,
        generated_tokens=64,TTFT_s=1.40849,decode_tokens_s=5.94,
        benchmark_url='https://github.com/airockchip/rknn-llm/blob/main/benchmark.md',
        exact_board_model_revision_kernel_precision_map='not disclosed in benchmark'),
        source_urls=['https://huggingface.co/openbmb/MiniCPM3-4B/raw/main/config.json',
                     'https://huggingface.co/openbmb/MiniCPM3-4B/raw/main/modeling_minicpm.py',
                     'https://raw.githubusercontent.com/airockchip/rknn-llm/main/scripts/fix_freq_rk3588.sh',
                     'https://wiki.radxa.com/Rock5/hardware/5b'],
        model_shapes={n:shape(n) for n in ['MiniCPM3-4B','Qwen3-4B']},
        counts={n:counts(shape(n)) for n in ['MiniCPM3-4B','Qwen3-4B']},
        cases=cases,sensitivity=sensitivity,sampling=sampling,
        price_input_SHA256=hashlib.sha256((D/'AREA_REVIEW_INPUTS.json').read_bytes()).hexdigest(),
        source_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        assumptions=['A8/W8 for main matmuls,INT32 numeric accumulation;P-CIM local count+64bit cross-K unchanged',
          'SNG converts signed A8 magnitude toP8 threshold;sign/scale metadata counted separately,not called extra A8 precision',
          'dense causal Attention;no sparse K/PV benefit assumed;nonmatrix costs proxy rather than Rockchip internals',
          'same128-token count/model public shape,not same text/checkpoint/RKLLM numeric forward',
          '16/32 sampling transfers Qwen timing cost,not proven MiniCPM quality',
          '33.792GB/s peak is Rock5B/script reference;20/27/30 effective scenarios,not measured RKLLM trace',
          'independent-row state pipeline;serialized state phases reported as sensitivity',
          'current measured19bit local-price reference,21bit price delta unknown',
          'integer matrix task pricing/native throughput may use P8/sign representation,not new signedA8 PPA',
          'unpriced top-level buffers,conversion,network and control area;no claim of complete die',
          'temperature/voltage250MHz prices retained;no scaling Rockchip1GHz to250MHz',
          'no prompt tokenization/host/software launch measurement;time is service budget'],
        verification=dict(independent_FFN_MAC_frames=True,MiniCPM_MLA_projections=True,
                          stage_sum=True,state_payload_fits_banks=True,no_new_jobs=True))
    raw=(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    (D/'ROCKCHIP_MATCH_RESULTS.json').write_bytes(raw)
    (D/'ROCKCHIP_MATCH_RESULTS.sha256').write_text(hashlib.sha256(raw).hexdigest()+'\n',encoding='ascii')
    print(json.dumps({'cases':[{k:x[k] for k in ['model','cores','FFN_s','total_s','serial_state_sensitivity_s']} for x in cases],
                      'checks':out['verification']},ensure_ascii=False,indent=2))


if __name__=='__main__': main()
