"""Replay encoding/counters/restoration through an explicit Issue116 backend.

Synthetic FP32 groups and W8 matrices, fixed stratified T words, no model/PPL.
The fixture producer is a software test boundary, not a timed SC implementation.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import random
import struct
import sys

from .adapter import Adapter, Profile
from .arithmetic import accumulate_counts, encode, restore_bins, add_words
from .backend import load


def word(value):
    return int.from_bytes(struct.pack('<f', value), 'little')


def fixture(samples, rows=64, groups=2, seed=20261023):
    rng = random.Random(seed)
    out = []
    for group in range(groups):
        values = [word(rng.uniform(-8,8)) for _ in range(64)]
        values[:8] = [word(v) for v in (8.,-8.,2.,-2.,.5,-.5,0.,-0.)]
        weights = [[rng.randrange(-128,128) for _ in range(64)] for _ in range(rows)]
        weights[0] = [-128]*64
        thresholds = [i*(256//samples)+rng.randrange(256//samples) for i in range(samples)]
        out.append(dict(words=values, weights=weights, thresholds=thresholds,
                        weight_scale_word=word(.03125*(group+1))))
    return out


def reference(data, samples):
    """Direct scalar W8 dot product; independent of either counter layout."""
    partial = [0]*len(data[0]['weights'])
    for group in data:
        e = encode(group['words'], frac=23)
        for row, weights in enumerate(group['weights']):
            sums = [sum(w*(-1 if e['input_sign'][i] else 1)
                        for threshold in group['thresholds'] for i,w in enumerate(weights)
                        if e['bins'][i] == b and (e['true_one'][i] or threshold < e['q'][i]))
                    for b in range(4)]
            restored = restore_bins(sums, top_exp=e['top_exp'],
                                    weight_scale_word=group['weight_scale_word'], samples=samples)
            partial[row] = add_words(partial[row], restored)
    return partial


def execute(api, data, samples, representation, profile, mode, sink_start_ps=0):
    resources, buffers = profile.specs(api)
    resources += [api.Resource('fixture', api.Clock('er.clock',profile.period_ps),1,capacity=2,
                               provenance='test-only precomputed counter producer; not SC timing')]
    k = api.Kernel(resources,buffers)
    adapter = Adapter(k,api,profile)
    rows = len(data[0]['weights'])
    previous, previous_release = (), ()
    source_counts = {}
    for index, group in enumerate(data):
        name = f'g{index:03d}'
        enc_id = adapter.add_encode(name,group['words'],deps=previous_release)
        producer = name+'.fixture'
        def produce(kernel,op,name=name,group=group):
            e = adapter.encoded[name]
            bits = [[int(t < q) for q in e['q']] for t in group['thresholds']]
            source_counts[name] = [accumulate_counts(weights,e['input_sign'],e['bins'],bits,
                representation=representation,count_width=(64*samples).bit_length(),true_one=e['true_one'])
                for weights in group['weights']]
        k.add(api.Operation(producer,'fixture',deps=(enc_id,),on_complete=produce))
        previous, release = adapter.add_restore_tile(name,rows=rows,
            counter_provider=lambda row,name=name:source_counts[name][row],
            representation=representation,count_width=(64*samples).bit_length(),samples=samples,
            weight_scale_word=group['weight_scale_word'],deps=(producer,),
            previous_adds=previous,sink_start_ps=sink_start_ps)
        previous_release = (release,)
    result = k.run(mode)
    values = [adapter.partial[row] for row in range(rows)]
    assert not adapter.encoded and not adapter.restored
    for lane in range(profile.restore_lanes):
        assert result.buffer_final[f'er.restore{lane}.free'] == profile.restore_depth
        assert result.buffer_final[f'er.restore{lane}.ready'] == 0
    return result, values, adapter.receipts


def save(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--backend-root',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    api, hashes=load(args.backend_root)
    cases=[]
    for samples in (16,32,64):
        data=fixture(samples)
        save(args.out/f'input_t{samples}.json',data)
        gold=reference(data,samples)
        for lanes in (1,4):
            profile=Profile(restore_lanes=lanes,add_ii=2)
            for representation in ('input_sign_twos_complement','product_sign_magnitude'):
                key=f't{samples}_l{lanes}_'+('twos' if representation.startswith('input') else 'magnitude')
                a, va, ra=execute(api,data,samples,representation,profile,'cycle',sink_start_ps=300000)
                b, vb, rb=execute(api,data,samples,representation,profile,'event',sink_start_ps=300000)
                assert a.equivalence_payload()==b.equivalence_payload() and ra==rb and va==vb==gold
                assert b.actions=={'complete_encode_group64':2,'encoded_values':128,
                                   'complete_restore_output_b4':128,'cross_k_fp32_add':128}
                save(args.out/(key+'.json'),dict(profile=asdict(profile),representation=representation,
                    samples=samples,finish_ps=b.finish_ps,actions=b.actions,buffer_peak=b.buffer_peak,
                    buffer_final=b.buffer_final,resource_peak=b.resource_peak,
                    resource_stats=b.resource_stats,values_hex=[f'{v:08x}' for v in vb],
                    cycle_steps=a.steps,event_steps=b.steps,cycle_event_equal=True,direct_dot_equal=True))
                if samples==32 and lanes==1 and representation.startswith('input'):
                    save(args.out/'representative_trace.json',dict(trace=b.trace,receipts=rb,
                        accepted_ps=b.accepted_ps,completion_ps=b.completion_ps))
                cases.append(dict(id=key,finish_ps=b.finish_ps,restore_outputs=128,passed=True))
    summary=dict(passed=True,cases=cases,scope='synthetic CPU integration using actual Issue116 API',
        backend_source_sha256=hashes,python=sys.version,platform=platform.platform(),
        arithmetic='B4 / q256 / true-one / fixed W8 / per-bin FP32 FUSED0 / ordered cross-k adds',
        timing='conditional cycles; fixture counter production is not SC timing; not complete FFN',
        reservation='inflight + completed + downstream-add occupancy <= depth per lane',
        limits=['No default FFN replacement','No PPL','No STA','No physical power/area'],
        area_um2=None,energy_pj=None,sta_frequency_hz=None)
    save(args.out/'SUMMARY.json',summary)
    print(json.dumps({'passed':True,'cases':len(cases),'restore_outputs':sum(c['restore_outputs'] for c in cases)}))


if __name__=='__main__':
    main()
