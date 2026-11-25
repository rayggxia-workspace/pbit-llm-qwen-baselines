"""Independent event consumer for resource/dependency checks, not actor replay."""
from collections import Counter, defaultdict
import json


def validate(path,contract,sram=None):
    tiles={}; cores={}; used=defaultdict(set); expected=defaultdict(int)
    returns=Counter(); counts=Counter(); phase_scope=None; terminal=False
    physical=Counter(); caches={}; output_cores=defaultdict(set); owners={}
    rng_steps=Counter();seeded=set()
    for line in path.open(encoding='utf-8'):
        r=json.loads(line);event=r['event'];counts[event]+=1;terminal=False
        ident=r.get('transaction_id');core=r.get('core');t=r['ns']
        if event=='stage_begin':
            phase_scope=(r['command'],r['layer'],r['mode'])
            caches={}
        if event=='weight_load_begin':
            assert core not in cores,('overwrite',r)
            assert ident not in tiles,('duplicate tile',r)
            cores[core]=ident;tiles[ident]={'load':t,'bytes':0,'addresses':set(),
                'beats':[],'beat_ns':[],'capture':None,'input':False,'rng':False}
        if event=='rng_state_ready':
            assert ident in tiles;tiles[ident]['rng']=True
            if r.get('mapping')=='local_persistent':
                assert core in seeded and r['start_steps']==rng_steps[core,r['mode']],r
        if event=='rng_seed_load':
            assert core not in seeded,r
            seeded.add(core)
        if event=='dma_return' and r['target'].startswith('CIM_core'):
            returns[ident]+=r['bytes']
        if event=='dma_landed' and r['resource'].startswith('CIM_core'):
            assert cores.get(core)==ident and 'accept' not in tiles[ident],r
            assert r['offset']%64==0 and 0<=r['offset']<=8192-64
            assert r['offset'] not in tiles[ident]['addresses'],('duplicate weight beat',r)
            assert r['first_bank']==(r['offset']//16)%16 and r['first_row']==r['offset']//256,r
            tiles[ident]['addresses'].add(r['offset'])
            tiles[ident]['bytes']+=r['bytes']
        if event=='weight_ready':
            assert tiles[ident]['bytes']==8192 and returns[ident]==8192,r
            assert tiles[ident]['addresses']==set(range(0,8192,64)),r
            tiles[ident]['ready']=t
        if event=='memory_complete': physical[(r['reason'],r['write'])]+=r['physical_bytes']
        if event in ('input_cache_fill','input_cache_hit'):
            key=(r['command'],r['layer'],r['mode'],r['k'])
            if event=='input_cache_hit': assert caches.get(core)==key,r
            else:caches[core]=key
            tiles[ident]['input']=True
        if event=='result_reserve':
            assert r['slot'] not in used[core];used[core].add(r['slot'])
            assert len(used[core])<=contract['result']['slots_per_core']
        if event=='state_owner_acquire':
            key=(r['command'],r['layer'],r['mode'],r['state_slot'])
            assert key not in owners and r['k']==0,r
            owners[key]=r['out_group']
        if event=='command_accept':
            row=tiles[ident];assert row['input'] and row['rng'] and 'ready' in row,r
            key=(r['command'],r['layer'],r['mode'],r['out_group'])
            assert r['k']==expected[key],('K dependency',r)
            output_cores[key].add(core)
            row['accept']=t
        if event=='sample_last':
            row=tiles[ident];row['last_sample']=t;row['samples']=r['samples']
            assert t-row['accept']==r['samples']*contract['period_ns']
            rng_steps[core,r['mode']]+=r['samples']
        if event=='result_valid':tiles[ident]['valid']=t
        if event=='result_capture':
            row=tiles[ident];assert row['valid']<=t and r['slot'] in used[core]
            capture=(contract['result']['columns']+contract['result']['capture_lanes']-1)//contract['result']['capture_lanes']
            expected_cycles=contract['base_frame_cycles'][r['mode']]-1+capture
            assert t-row['accept']==expected_cycles*contract['period_ns'],r
            row['capture']=t
        if event=='cim_release':
            assert tiles[ident]['capture'] is not None and tiles[ident]['capture']<=t
            assert cores.pop(core)==ident
        if event=='result_beat_accept':
            row=tiles[ident];assert row['capture'] is not None and r['slot'] in used[core]
            row['beats'].append(r['beat'])
            row['beat_ns'].append(t)
            assert r['values']==contract['state']['lanes'] and r['wire_bits']==32,r
            if len(row['beat_ns'])>1:
                assert t-row['beat_ns'][-2]==contract['state']['beat_II_cycles']*contract['period_ns'],r
        if event=='result_slot_release':
            assert tiles[ident]['beats']==list(range(contract['state']['packet_beats']))
            assert t-tiles[ident]['beat_ns'][-1]>=contract['state']['beat_II_cycles']*contract['period_ns'],r
            used[core].remove(r['slot']);tiles[ident]['slot_release']=t
        if event=='state_commit':
            assert tiles[ident]['slot_release']<=t
            key=(r['command'],r['layer'],r['mode'],r['out_group'])
            assert expected[key]==r['k'];expected[key]+=1;tiles[ident]['commit']=t
        if event=='state_owner_release':
            assert r['transaction_id'] in tiles and 'commit' in tiles[ident]
            key=(r['command'],r['layer'],r['mode'],r['state_slot'])
            assert owners.pop(key)==r['out_group'],r
        if event=='stage_done':
            assert not cores and not any(used.values()) and not owners
            assert all('commit' in row for name,row in tiles.items())
            assert phase_scope==(r['command'],r['layer'],r['mode']);terminal=True
    assert terminal,'trace missing final stage completion or truncated'
    assert counts['weight_load_begin']==counts['command_accept']==counts['result_capture']==counts['cim_release']==counts['state_commit']
    assert not cores and not any(used.values())
    if sram:
        for (tag,write),value in physical.items():
            assert value==sram['by_tag'][tag]['write_words' if write else 'read_words']*16,(tag,value)
    return dict(status='PASS',tiles=len(tiles),events=dict(counts),
        crossK_commit_order=True,result_capture_before_CIM_release=True,
        result_slot_released_after_four_beats=True,state_owner_exclusion=True,weight_bytes_and_routes=True,
        physical_16B_actions_match_parent_SRAM=bool(sram),
        local_seed_loads=len(seeded),local_PRNG_advances_only_on_accepted_samples=True,
        outputs_executed_across_multiple_cores=sum(len(x)>1 for x in output_cores.values()))
