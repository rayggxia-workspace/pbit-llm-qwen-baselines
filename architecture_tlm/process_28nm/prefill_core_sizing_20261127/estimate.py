"""Resource sizing for 2K Qwen3-4B prefill; not the decode TLM or a bank replay."""
from pathlib import Path
import argparse,hashlib,json,math

ROOT=Path(__file__).resolve().parents[3]
MODEL=dict(id='Qwen/Qwen3-4B',revision='1cfa9a7208912126459214e8b04321603b3df60c',
           layers=36,hidden=2560,intermediate=9728,q_heads=32,kv_heads=8,head_dim=128,vocabulary=151936)

def workload(prompt=2048):
    m=MODEL;L,H,I=(m[k] for k in ['layers','hidden','intermediate']);Q=m['q_heads']*m['head_dim'];KV=m['kv_heads']*m['head_dim']
    gu=prompt*L*(I//64)*(H//64);wd=prompt*L*(H//128)*(I//64)
    qkvo_mac=prompt*L*H*(2*Q+2*KV);pairs=prompt*(prompt+1)//2
    attention_mac=L*pairs*Q*2;ffn_mac=prompt*L*3*H*I
    assert (gu+wd)*8192==ffn_mac
    return dict(prompt=prompt,gu_frames=gu,wd_frames=wd,ffn_mac=ffn_mac,
        qkvo_mac=qkvo_mac,attention_mac=attention_mac,causal_pairs_per_layer=pairs,
        softmax_vector_ops=L*pairs*m['q_heads']*8,
        norm_rope_residual_ops=L*prompt*(16*H+8*(Q+KV)),
        ffn_weight_bytes=L*3*H*I,qkvo_weight_bytes=L*2*H*(2*Q+2*KV),
        ffn_final_GU_groups=prompt*L*(I//64),ffn_final_Wd_groups=prompt*L*(H//128),
        state_update_values=(gu+wd)*128,KV_width=KV,head_mac=H*m['vocabulary'],head_bytes=2*H*m['vocabulary'])

def estimate(*,cores,lanes,vector_lanes,state_workers,encoders,rows,clock=250e6,prompt=2048,
             state_bits=64,state_GBs=2048,dram_GBs=100,gu_samples=16,wd_samples=32):
    w=workload(prompt);chunks=math.ceil(prompt/rows);f=clock
    gu_c=gu_samples+2;wd_c=wd_samples+2
    weighted_cycles=w['gu_frames']*gu_c+w['wd_frames']*wd_c
    ff_compute=weighted_cycles/(cores*f)
    # One 8KiB tile per resident core; 32 cycles to program, then reuse for rows tokens.
    tile_loads=MODEL['layers']*(MODEL['intermediate']//64)*(MODEL['hidden']//64)*chunks
    tile_loads+=MODEL['layers']*(MODEL['hidden']//128)*(MODEL['intermediate']//64)*chunks
    program=tile_loads*32/(cores*f)
    state_alu=w['state_update_values']/(state_workers*32*f)
    # First K starts from zero and last K is encoded, with no state-SRAM writeback.
    gu_groups=w['ffn_final_GU_groups'];wd_groups=w['ffn_final_Wd_groups']
    state_io=(2*(w['gu_frames']+w['wd_frames'])-2*(gu_groups+wd_groups))*128*(state_bits/8)
    state_sram=state_io/(state_GBs*1e9)
    ff_dram=w['ffn_weight_bytes']*chunks/(dram_GBs*1e9)
    qkvo_dram=w['qkvo_weight_bytes']*chunks/(dram_GBs*1e9)
    qkvo_compute=w['qkvo_mac']*17/16/(lanes*f)
    attn_compute=w['attention_mac']*17/16/(lanes*f)
    softmax=w['softmax_vector_ops']/(vector_lanes*f)
    norm=w['norm_rope_residual_ops']/(vector_lanes*f)
    codec=(gu_groups*15+wd_groups*9)/(encoders*f)
    kv_read=MODEL['layers']*w['KV_width']*4*sum(min(prompt,start+rows) for start in range(0,prompt,rows))
    # BF16 hidden read/write + Q/attention output traffic, g/u P8 write/read, KV append.
    extra_io=prompt*MODEL['layers']*(8*MODEL['hidden']+8*MODEL['q_heads']*MODEL['head_dim']+5*MODEL['intermediate']+4*w['KV_width'])
    io_s=extra_io/(dram_GBs*1e9)
    head=max(w['head_mac']*17/16/(lanes*f),w['head_bytes']/(dram_GBs*1e9))
    # Proposed prefill backend pipelines independent rows across SRAM and update phases.
    stages=dict(FFN=max(ff_compute+program,state_alu,state_sram,ff_dram),
        QKVO=max(qkvo_compute,qkvo_dram),dense_attention=max(attn_compute+softmax,kv_read/(dram_GBs*1e9)),
        norm_rope_residual=norm,FFN_encoding=codec,other_external_IO=io_s,lm_head=head)
    return dict(cores=cores,FMA_lanes=lanes,vector_lanes=vector_lanes,state_workers32=state_workers,
        encoder_copies=encoders,weight_reuse_tokens=rows,clock_MHz=f/1e6,dram_effective_GBs=dram_GBs,
        state_port_aggregate_GBs=state_GBs,state_bits=state_bits,total_service_s=sum(stages.values()),stages=stages,
        floors=dict(FFN_compute_s=ff_compute,FFN_program_s=program,state_alu_s=state_alu,state_sram_s=state_sram,
                    FFN_weight_DRAM_s=ff_dram,QKVO_compute_s=qkvo_compute,QKVO_weight_DRAM_s=qkvo_dram),
        planning_state_payload_bytes=cores*rows*128*state_bits//8,
        CIM_weight_bytes=cores*8192,state_RW_bytes=state_io,weight_DRAM_bytes=(w['ffn_weight_bytes']+w['qkvo_weight_bytes'])*chunks,
        state_pipeline='proposed independent-row SRAM/update overlap, not current blocking state_worker',
        state_serial_phase_sensitivity_s=sum(stages.values())-stages['FFN']+max(ff_compute+program,state_alu+state_sram,ff_dram))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-root',type=Path);args=ap.parse_args()
    w=workload();c=w['gu_frames']*18+w['wd_frames']*34
    assert (w['gu_frames'],w['wd_frames'])==(448266240,224133120)
    assert c==15689318400
    profiles=[dict(cores=n,lanes=256,vector_lanes=16,state_workers=2,encoders=1,rows=128) for n in [5,32,64,96]]
    profiles += [dict(cores=n,lanes=16384,vector_lanes=512,state_workers=16,encoders=4,rows=128) for n in [32,64,96]]
    profiles += [dict(cores=n,lanes=32768,vector_lanes=1024,state_workers=32,encoders=8,rows=256,state_GBs=4096) for n in [64,128,192]]
    cases=[estimate(**p) for p in profiles]
    sensitivities=[estimate(cores=96,lanes=16384,vector_lanes=512,state_workers=16,encoders=4,rows=b,dram_GBs=bw)
                   for b in [32,64,128,256] for bw in [80,100,120]]
    fixture=Path(__file__).with_name('SOURCE_INPUTS.json');inputs=json.loads(fixture.read_bytes())
    sources={x['path']:x['sha256'] for x in inputs.values()}
    if args.source_root:
        for x in inputs.values():
            raw=(args.source_root/x['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==x['sha256']
            x['data']=json.loads(raw)
    cfg,contract,binding=(inputs[k]['data'] for k in ['config','contract','binding'])
    assert cfg['clock_MHz']==binding['clock_MHz']==250 and cfg['weight_bytes_per_core']==8192
    assert cfg['banks_per_core']==16 and cfg['rows_per_bank']==32 and cfg['word_bytes']==16
    assert contract['base_frame_cycles']=={'GU':18,'Wd':34}
    assert binding['FFN_core']['modes']['GU']['frame_cycles']==18 and binding['FFN_core']['modes']['Wd']['frame_cycles']==34
    assert binding['shared_FMA']['input_II_cycles']==1 and binding['shared_FMA']['latency_cycles']==4
    out=dict(status='analytical_resource_sizing_not_full_TLM',date='2026-11-27',model=MODEL,workload=w,
       sources_sha256=sources,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
       fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
       sampling=dict(GU=16,Wd=32,GU_frame_cycles=18,Wd_frame_cycles=34),
       ideal_FFN_core_seconds=c/250e6,ideal_FFN_min_cores_for_2s=math.ceil(c/250e6/2),
       ideal_FFN_min_cores_for_1s=math.ceil(c/250e6),
       alternative_QKVO_as_PCIM=dict(scope='new W8/sampling algorithm; quality not validated',
          additional_core_seconds=w['qkvo_mac']/8192*18/250e6,total_linear_core_seconds=c/250e6+w['qkvo_mac']/8192*18/250e6),
       cases=cases,sensitivity=sensitivities,
       boundary='dense exact attention, BF16 QKVO, final prompt token head only; rows reuse and scaled services are proposed, not existing prefill RTL or bank schedule')
    p=Path(__file__).with_name('RESULTS.json');raw=(json.dumps(out,indent=2)+'\n').encode();p.write_bytes(raw);p.with_suffix('.sha256').write_text(hashlib.sha256(raw).hexdigest()+'\n',encoding='ascii')
    print(json.dumps(dict(ideal_FFN_core_seconds=out['ideal_FFN_core_seconds'],workload=w,cases=[{k:r[k] for k in ['cores','FMA_lanes','vector_lanes','total_service_s','stages','planning_state_payload_bytes']} for r in cases],sensitivity=[{k:r[k] for k in ['weight_reuse_tokens','dram_effective_GBs','total_service_s']} for r in sensitivities]),indent=2))

if __name__=='__main__':main()
