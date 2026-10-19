"""Core-service-only FFN mapping comparison; no memory/energy/PPL prediction.

Compare the same total number of 64x64 SC engines. The spatial pipeline
enumeration is intentionally limited, not a proof of optimal scheduling.
"""
import argparse
import hashlib
import json
from math import ceil
from pathlib import Path


def spatial_pipeline(h, m, total, gu_engines, block_tiles, tile=64):
    if not (0 < gu_engines < total and h % tile == 0 and m % tile == 0 and block_tiles > 0):
        raise ValueError('invalid split or dimensions')
    down_engines = total-gu_engines
    gu_end = down_end = 0
    events = []
    for start in range(0, m//tile, block_tiles):
        n = min(block_tiles, m//tile-start)
        gu_work = (h//tile)*ceil(2*n/gu_engines)
        down_work = n*ceil((h//tile)/down_engines)
        gu_start = gu_end
        gu_end += gu_work
        down_start = max(down_end, gu_end)
        down_end = down_start+down_work
        events.append(dict(channel_tile_start=start,channel_tiles=n,
            gu_start=gu_start,gu_end=gu_end,down_start=down_start,down_end=down_end))
    # Check data dependencies and mutual exclusion within each engine partition.
    for i,e in enumerate(events):
        assert e['down_start'] >= e['gu_end']
        if i:
            assert e['gu_start'] >= events[i-1]['gu_end']
            assert e['down_start'] >= events[i-1]['down_end']
    return dict(wave_span=down_end,gu_engines=gu_engines,down_engines=down_engines,
        channel_block=block_tiles*tile,events=events)


def compare(evidence):
    s=evidence['shape'];c=evidence['config']
    h=s['hidden_size'];m=s['intermediate_size'];layers=s['num_hidden_layers'];tile=64
    f=c['frequency_hz'];blocks=[1,2,4,8,16,32,64,m//tile]
    rows=[]
    for total in [8,16,32,64]:
        serial=(h//tile)*ceil((2*m//tile)/total)+(m//tile)*ceil((h//tile)/total)
        g=total//2;u=total-g
        branches=(h//tile)*max(ceil((m//tile)/g),ceil((m//tile)/u))
        branched=branches+(m//tile)*ceil((h//tile)/total)
        candidates=[spatial_pipeline(h,m,total,eg,b) for eg in range(1,total) for b in blocks]
        best=min(candidates,key=lambda x:(x['wave_span'],x['gu_engines'],x['channel_block']))
        assert best['gu_engines']+best['down_engines']==total
        for T in [256,1024,4096]:
            wave_ms=(T+1)/f*1000*layers
            rows.append(dict(total_engines=total,samples=T,
                stagewise_wave_count=serial,stagewise_core_ms_per_token=serial*wave_ms,
                separate_G_U_then_reuse_for_down_wave_count=branched,
                pipeline_best_in_enumerated_set=dict(**best,core_ms_per_token=best['wave_span']*wave_ms),
                pipeline_over_stagewise=best['wave_span']/serial))
    time=evidence['historical']['time_ns'];n=c['decode_tokens']
    old_ffn=sum(v for k,v in time.items() if k.startswith('FFN_'))/n/1e6
    old_total=evidence['historical']['metrics']['mean_TPOT_ms']
    return dict(kind='analytical SC service comparison only; NOT a new TLM/runtime/RTL/quality result',
        shape=dict(h=h,m=m,layers=layers),frequency_hz=f,
        historical_result_sha256=evidence['historical']['sha256'],
        search=dict(total_engines=[8,16,32,64],gu_engine_allocations='all positive splits',
                    channel_block_tiles=blocks,samples=[256,1024,4096]),
        assumptions=['one independent GU partition and one Down partition in pipeline',
            'paired g/u must complete all input reductions before activation',
            'current 64-input-block broadcasting protocol retained inside each matrix',
            'same T for GU/Down; one wave takes T+1 cycles',
            'pipeline activation, input re-encoding, memory transfers, extra RNG/frontend, and buffer costs are zero here',
            'unbounded interstage queue and accumulator availability assumed; not a feasible resource/area proof',
            'same total engines is not same total chip area because the spatial pipeline needs independent frontends/buffers'],
        historical=dict(total_ms_per_token=old_total,FFN_ms_per_token=old_ffn,
            non_FFN_ms_per_token=old_total-old_ffn,
            lm_head_ms_per_token=time['lm_head']/n/1e6,
            comment='old synthetic 2K DRAMSys/TLM timing; not rerun or used as certified energy'),
        results=rows,quality='not evaluated; changing T requires matched BF16 and multi-seed PPL evaluation')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise SystemExit('Refusing to overwrite existing result')
    data=compare(json.loads(a.evidence.read_text(encoding='utf-8')))
    data['tool_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps([dict(engines=r['total_engines'],T=r['samples'],
        stage_ms=r['stagewise_core_ms_per_token'],pipeline_ms=r['pipeline_best_in_enumerated_set']['core_ms_per_token'])
        for r in data['results'] if r['samples']==4096]))


if __name__=='__main__':main()
