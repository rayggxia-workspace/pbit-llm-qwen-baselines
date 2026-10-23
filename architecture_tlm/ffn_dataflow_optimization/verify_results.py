"""Independent artifact/trace audit; never invokes a simulation runner.

Cycle evidence is compared by separately recorded equivalence/output hashes.
The event payload is independently rehashed and its resource/credit/address
history checked here. This is artifact and conditional-contract validation,
not STA, PPA, full FFN or a second floating-point arithmetic implementation.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
from itertools import groupby
import json
import math
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PROFILE = dict(period_ps=10000, encode_latency=2, encode_ii=1, encode_depth=4,
    restore_latency=2, restore_ii=1, restore_lanes=1, restore_depth=4,
    add_latency=1, add_ii=1, add_capacity=2, encoded_groups=1)
EQUIVALENCE_KEYS = ('finish_ps','accepted_ps','completion_ps','actions','trace',
    'memory_reads','buffer_peak','buffer_final','resource_peak','resource_stats','process_ticks')
MAIN_CONFIG = dict(groups=4,tiles=8,rows_per_tile=64,samples=32,weight_slots=1,counter_slots=1,
    counter_read_bytes=16,counter_read_ports=1,staging_packets=4,partial_write_slots=4,
    partial_word_bytes=16,packet_metadata_bytes=16,w8_macs_per_cycle=512,w8_scale_latency=2,
    w8_scale_ii=1,profile=None,feed_overrides=None,sink_start_ps=0)
MAIN_CANDIDATES = {
    'baseline':{},'restore4_only':{'profile':{'restore_lanes':4}},
    'read128_only':{'counter_read_bytes':128},
    'read128_restore4':{'counter_read_bytes':128,'profile':{'restore_lanes':4}},
    'pipeline2':{'counter_read_bytes':128,'weight_slots':2,'counter_slots':2,'profile':{'restore_lanes':4}},
    'pipeline2_addII4':{'counter_read_bytes':128,'weight_slots':2,'counter_slots':2,
                       'profile':{'restore_lanes':4,'add_ii':4}},
    'pipeline2_stage1':{'counter_read_bytes':128,'weight_slots':2,'counter_slots':2,
                       'staging_packets':1,'profile':{'restore_lanes':4}},
    'weight2_only':{'weight_slots':2}}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),
                                    allow_nan=False).encode()).hexdigest()


def record(raw):
    return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def integer(value, label, minimum=0):
    require(type(value) is int and value >= minimum, 'invalid integer: '+label)
    return value


def confined(root, relative):
    path=(root/relative).resolve()
    require(path.is_relative_to(root.resolve()), 'artifact path escapes directory')
    return path


def source_audit(source, cache):
    key=digest(source['files'])+digest(source['dependencies'])+source['commit']
    require(source['source_sha256']==digest(source['files']), 'source digest mismatch')
    lock=source['dependencies']
    dep_digest=hashlib.sha256(json.dumps(lock,sort_keys=True).encode()).hexdigest()
    require(source['dependency_source_sha256']==dep_digest, 'dependency lock digest mismatch')
    if key in cache:return
    from .dependencies import SOURCES
    require(set(lock['sources'])==set(SOURCES),'dependency source set differs')
    expected_sources={'architecture_tlm/ffn_dataflow_optimization/'+name for name in
                      ('__init__.py','dependencies.py','fixtures.py','model.py','run.py')}
    require(set(source['files'])==expected_sources,'execution source coverage differs')
    objects=[(source['commit'],p,info) for p,info in source['files'].items()]
    for name,spec in SOURCES.items():
        actual=lock['sources'][name]
        require(actual['commit']==spec['commit'] and set(actual['files'])==set(spec['files']),
                'dependency revision/file set differs: '+name)
        objects.extend((actual['commit'],p,info) for p,info in actual['files'].items())
    require(sum(len(v['files']) for v in lock['sources'].values())==13,'expected thirteen dependency files')
    env=dict(os.environ,GIT_NO_LAZY_FETCH='1')
    for commit,path,info in objects:
        require('\\' not in path and '..' not in Path(path).parts,'noncanonical Git source path')
        raw=subprocess.check_output(['git','cat-file','blob',commit+':'+path],cwd=ROOT,env=env)
        require(record(raw)==info,'frozen Git source differs: '+path)
    cache.add(key)


def fixture_audit(folder, source_cache):
    manifest=read(folder/'FIXTURES.json');source=read(folder/'EXECUTION.json')
    source_audit(source,source_cache)
    items=manifest['files'];seeds=manifest['seeds']
    require(len(set(seeds))==len(seeds)==len(items),'duplicate/missing fixture seeds')
    require({x['seed'] for x in items}==set(seeds),'fixture seed coverage differs')
    fixtures={}
    for item in items:
        path=confined(folder,item['path']);raw=path.read_bytes()
        require(record(raw)=={k:item[k] for k in ('bytes','sha256')},'fixture file bytes changed')
        f=json.loads(raw);claimed=f['fixture_sha256'];body=dict(f);body.pop('fixture_sha256')
        require(digest(body)==claimed==item['fixture_sha256'],'fixture content identity changed')
        require((f['seed'],f['groups'],f['tiles'])==(item['seed'],manifest['groups'],manifest['tiles']),
                'fixture dimensions/seed mismatch')
        for name in ('inputs','packets','expected_sc','expected_w8','sc_partials','w8_partials','w8_unscaled'):
            require(digest(f[name])==f['hashes'][name],'fixture component hash differs: '+name)
        require(f['rows']==f['tiles']*f['rows_per_tile'],'fixture row geometry')
        require(all(len(f[k])==f['groups'] for k in ('inputs','packets','sc_partials','w8_partials','w8_unscaled')),
                'fixture group coverage')
        for k in range(f['groups']):
            g=f['inputs'][k]
            require(len(g['words'])==64 and len(g['weights'])==f['rows'],'fixture operands incomplete')
            require(len(g['scale_words'])==f['tiles'],'fixture scale coverage')
            require([t//(256//f['samples']) for t in g['thresholds']]==list(range(f['samples'])),
                    'fixture thresholds not one draw per stratum')
            for row,packet in enumerate(f['packets'][k]):
                require(packet['weight_scale_word']==g['scale_words'][row//f['rows_per_tile']],
                        'fixture per-tile scale mismatch')
                require(packet['sc_word']==f['sc_partials'][k][row],'fixture SC partial mismatch')
        fixtures[item['seed']]=f
    require({p.name for p in folder.glob('seed*.json')}=={x['path'] for x in items},'unmanifested fixture file')
    return manifest,source,fixtures


def specifications(cfg, method, partial_cycles):
    p=cfg['profile'];rows=cfg['tiles']*cfg['rows_per_tile']
    # Tuple: period, instances, capacity per instance, latency, issue interval.
    resources={'feed':(50000,1,1,None,1),'sample_or_mac':(10000,1,1,
        cfg['samples'] if method=='sc' else max(64,math.ceil(rows*64/cfg['w8_macs_per_cycle'])),None),
        'control':(10000,1,4,1,1),'counter_read':(10000,cfg['counter_read_ports'],1,
        math.ceil(((96 if method=='sc' else 4)+cfg['packet_metadata_bytes'])/cfg['counter_read_bytes']),None),
        'partial_io':(12500,1,1,partial_cycles,1),'add':(10000,1,p['add_capacity'],p['add_latency'],p['add_ii'])}
    buffers={'fabric_free':1,'weight_free':cfg['weight_slots'],'counter_free':cfg['counter_slots'],
             'staging_free':cfg['staging_packets'],'write_free':cfg['partial_write_slots']}
    for lane in range(p['restore_lanes']):
        resources['restore'+str(lane)]=(10000,1,p['restore_depth'],
            p['restore_latency'] if method=='sc' else cfg['w8_scale_latency'],
            p['restore_ii'] if method=='sc' else cfg['w8_scale_ii'])
        buffers['out_free'+str(lane)]=p['restore_depth']
    return resources,buffers


def trace_audit(value, fixture):
    cfg,method,native=value['config'],value['method'],value['native_result']
    feed_cfg=value['feed_templates'][0]['config'];contract=value['partial_io_contract']
    fabric_ps=math.ceil(16*10**12/feed_cfg['fabric_bytes_per_second'])
    service_raw=feed_cfg['read_latency_sram_cycles']*12500+feed_cfg['cdc_delay_ps']+fabric_ps
    partial_cycles=math.ceil(service_raw/12500)
    expected_contract=dict(transaction_bytes=16,sram_read_latency_cycles=feed_cfg['read_latency_sram_cycles'],
        sram_period_ps=12500,read_latency_ps=feed_cfg['read_latency_sram_cycles']*12500,
        cdc_delay_ps=feed_cfg['cdc_delay_ps'],fabric_bytes_per_second=feed_cfg['fabric_bytes_per_second'],
        fabric_transfer_ps=fabric_ps,unrounded_service_ps=service_raw,service_sram_cycles=partial_cycles,
        service_ps=partial_cycles*12500,rounding_guard_ps=partial_cycles*12500-service_raw,
        shared_lock_full_service=True)
    require({k:contract[k] for k in expected_contract}==expected_contract,'partial service formula differs')
    resources,buffers=specifications(cfg,method,partial_cycles)
    credits=dict(buffers);credit_peak={n:0 for n in buffers};resource_peak={n:0 for n in resources}
    stats={n:dict(accepted=0,completed=0,execution_ps=0,held_ps=0,output_blocked_ps=0) for n in resources}
    occupancy={n:[0]*s[1] for n,s in resources.items()};issue_free=defaultdict(int);complete_free=defaultdict(int)
    accepted={};completed={};actions=Counter();active={}
    trace=native['trace'];times=[e['time_ps'] for e in trace]
    require(times==sorted(times),'native trace is not chronological')
    for t,events_iter in groupby(trace,key=lambda e:e['time_ps']):
        integer(t,'trace time');events=list(events_iter)
        accept_shadow=dict(credits);output_shadow=dict(credits)
        occ_shadow={n:list(v) for n,v in occupancy.items()};starts=[];ends=[]
        for e in events:
            require(e['kind'] in ('stall','stall_end','accept','complete'),'unexpected native event')
            require(e['resource'] in resources,'unknown native resource')
            if e['kind'] not in ('accept','complete'):continue
            name=e['resource'];period,instances,capacity,latency,ii=resources[name]
            instance=integer(e['instance'],'resource instance')
            require(instance<instances and t%period==0,'resource instance/clock violation')
            ident=e['op'];key=(name,instance)
            if e['kind']=='accept':
                require(ident not in accepted,'duplicate operation accept')
                require(occ_shadow[name][instance]<capacity and t>=issue_free[key],'resource capacity/II exceeded')
                if name=='feed':latency=math.ceil(e['metadata']['actual_preload_ps']/period)
                if ii is None:ii=latency
                require(e['due_ps']==t+latency*period,'operation latency differs from configuration')
                for b,n in e['inputs'].items():
                    integer(n,'credit input',1);require(b in buffers and accept_shadow[b]>=n,'finite credit underflow')
                    accept_shadow[b]-=n
                occ_shadow[name][instance]+=1;issue_free[key]=t+ii*period
                accepted[ident]=e;starts.append(e);actions.update(e['actions']);stats[name]['accepted']+=1
            else:
                require(ident in active and ident not in completed,'complete without unique earlier accept')
                a=active[ident]
                require(not any(other['resource']==name and other['instance']==instance and
                                other['time_ps']<a['time_ps'] and other['op'] not in completed
                                for other in active.values()),'in-order resource completion reordered')
                require((a['resource'],a['instance'],a['due_ps'],a['metadata'])==
                        (name,instance,e['due_ps'],e['metadata']),'completion identity changed')
                require(e['accepted_ps']==a['time_ps'] and t>=e['due_ps'],'early/wrong completion')
                require(e['completion_port']==0 and t>=complete_free[key],'completion-port conflict')
                complete_free[key]=t+period
                for b,n in e['outputs'].items():
                    integer(n,'credit output',1);require(b in buffers and output_shadow[b]+n<=buffers[b],'finite credit overflow')
                    output_shadow[b]+=n
                ends.append(e);completed[ident]=e
                stat=stats[name];stat['completed']+=1;stat['execution_ps']+=e['due_ps']-a['time_ps']
                stat['held_ps']+=t-a['time_ps'];stat['output_blocked_ps']+=t-e['due_ps']
        for e in ends:
            del active[e['op']];occupancy[e['resource']][e['instance']]-=1
        for e in starts:
            active[e['op']]=e;occupancy[e['resource']][e['instance']]+=1
        for b in buffers:
            credits[b]=accept_shadow[b]+output_shadow[b]-credits[b]
            require(0<=credits[b]<=buffers[b],'committed credit count invalid')
            credit_peak[b]=max(credit_peak[b],buffers[b]-credits[b])
        for n in resources:resource_peak[n]=max(resource_peak[n],sum(occupancy[n]))
    require(not active and credits==buffers,'unreleased flight or finite credit')
    require(native['buffer_final']==credits and native['buffer_peak']==buffers,'reported buffer counters differ')
    require(native['resource_peak']==resource_peak and native['resource_stats']==stats,'resource statistics differ')
    require(value['storage']['credit_peak_used']==credit_peak,'credit peak differs')
    require(native['accepted_ps']=={n:e['time_ps'] for n,e in accepted.items()},'accepted index differs')
    require(native['completion_ps']=={n:e['time_ps'] for n,e in completed.items()},'completion index differs')
    require(native['finish_ps']==max(native['completion_ps'].values()),'finish time differs')
    require(native['actions']==dict(actions),'native action reduction differs')
    require(not native['memory_reads'] and not native['process_ticks'],'unexpected native memory/process boundary')

    groups,rows=cfg['groups'],fixture['rows'];count=groups*rows;payload=(96 if method=='sc' else 4)+16
    beats=math.ceil(payload/cfg['counter_read_bytes']);wave=rows*64
    expected={'weight_preload_bytes':groups*wave,'weight_read_transactions':groups*wave//feed_cfg['word_bytes'],
        'local_packet_read_bytes':count*payload,'local_packet_physical_bytes':count*beats*cfg['counter_read_bytes'],
        'counter_read_beats':count*beats,'cross_k_fp32_add':count,
        'partial_write_logical_bytes':count*4,'partial_write_physical_bytes':count*16}
    if groups>1:expected.update(partial_read_logical_bytes=(groups-1)*rows*4,partial_read_physical_bytes=(groups-1)*rows*16)
    if method=='sc':expected.update(complete_b4_restore=count,sc_accepted_samples=groups*cfg['samples'],
                                  sc_weight_input_trials=count*64*cfg['samples'])
    else:expected.update(w8_fp32_scale=count,w8_mac=count*64)
    require(dict(actions)==expected,'analytical action conservation failed')
    expected_ops=set()
    def operation(ident,resource,inputs,outputs):
        require(accepted[ident]['resource']==resource and accepted[ident]['inputs']==inputs and
                completed[ident]['outputs']==outputs,'operation resource/credit contract differs: '+ident)
    def after(consumer,producer):
        require(accepted[consumer]['time_ps']>completed[producer]['time_ps'],'dependency/visibility violation: '+consumer)
    layout=value['storage']['sram_layout'];partial_base=layout['partial_base']
    require(layout['weight_wave_bases']==[k*wave for k in range(groups)],'weight wave alias')
    require(partial_base==groups*wave and layout['reserved_bytes']==partial_base+math.ceil(rows*4/16)*16,
            'partial/weight allocation overlap or incorrect reservation')
    require(layout['reserved_bytes']<=layout['capacity_bytes'],'SRAM physical addresses exceed capacity')
    intervals=[]
    for k in range(groups):
        pre='k%04d'%k;expected_ops.update((pre+'.feed',pre+'.produce',pre+'.counter_release'))
        operation(pre+'.feed','feed',{'fabric_free':1,'weight_free':1},{'fabric_free':1})
        operation(pre+'.produce','sample_or_mac',{'counter_free':1},{'weight_free':1})
        operation(pre+'.counter_release','control',{}, {'counter_free':1})
        after(pre+'.produce',pre+'.feed')
        require(accepted[pre+'.feed']['metadata']['weight_base']==k*wave,'feed base differs')
        intervals.append((accepted[pre+'.feed']['time_ps'],completed[pre+'.feed']['time_ps']))
        for row in range(rows):
            base=pre+'.r%05d'%row
            names={suffix:base+'.'+suffix for suffix in ('counter_read','restore','add','partial_write')}
            if k:names['partial_read']=base+'.partial_read'
            lane=row%cfg['profile']['restore_lanes']
            operation(names['counter_read'],'counter_read',{'staging_free':1},{})
            operation(names['restore'],'restore'+str(lane),{'out_free'+str(lane):1},{'staging_free':1})
            operation(names['add'],'add',{'write_free':1},{'out_free'+str(lane):1})
            operation(names['partial_write'],'partial_io',{'fabric_free':1},{'fabric_free':1,'write_free':1})
            if k:operation(names['partial_read'],'partial_io',{'fabric_free':1},{'fabric_free':1})
            expected_ops.update(names.values());after(names['counter_read'],pre+'.produce')
            after(names['restore'],names['counter_read']);after(names['add'],names['restore'])
            after(names['partial_write'],names['add']);after(pre+'.counter_release',names['counter_read'])
            if k:
                after(names['partial_read'],names['restore'])
                after(names['partial_read'],'k%04d.r%05d.partial_write'%(k-1,row))
                after(names['add'],names['partial_read'])
            for suffix in ('partial_read','partial_write'):
                if suffix not in names:continue
                ident=names[suffix];m=accepted[ident]['metadata']
                require((m['address'],m['physical_address'],m['byte_enable'],m['conservative_transaction_bytes'])==
                        (partial_base+row*4,partial_base+(row*4//16)*16,15<<(row*4%16),16),'partial byte-address/mask mismatch')
                intervals.append((accepted[ident]['time_ps'],completed[ident]['time_ps']))
    require(set(accepted)==set(completed)==expected_ops,'native operation coverage differs')
    intervals.sort();require(all(a[1]<b[0] for a,b in zip(intervals,intervals[1:])),
                            'shared fabric/partial transactions overlap or use same-edge bypass')
    return accepted,completed


def payload_audit(value,fixture,deps):
    accepted,completed=trace_audit(value,fixture)
    cfg=value['config'];rows=fixture['rows'];groups=cfg['groups'];method=value['method']
    require((cfg['groups'],cfg['tiles'],cfg['rows_per_tile'],cfg['samples'])==
            (fixture['groups'],fixture['tiles'],fixture['rows_per_tile'],fixture['samples']),
            'fixture and execution geometry differs')
    require(value['output_words']==fixture['expected_'+method],'output differs from method reference')
    require(len(value['row_receipts'])==groups*rows,'restore receipt coverage differs')
    require({(x['group'],x['row']) for x in value['row_receipts']}==
            {(k,r) for k in range(groups) for r in range(rows)},'duplicate/missing restore receipt')
    for x in value['row_receipts']:
        require(x['word']==fixture[method+'_partials'][x['group']][x['row']],'restored partial differs')
        prefix='k%04d.r%05d'%(x['group'],x['row'])
        require(x['restore']==prefix+'.restore' and x['counter_read']==prefix+'.counter_read' and
                x['lane']==x['row']%cfg['profile']['restore_lanes'],'restore row identity differs')
        require(x['restore_done_ps']==completed[x['restore']]['time_ps'],'restore completion receipt differs')
    require(len(value['feed_templates'])==len(value['feed_receipts'])==groups,'feed wave coverage differs')
    feed_cfg=deps.feed.candidate_config('resident',inputs=64,outputs=cfg['rows_per_tile'],tiles=cfg['tiles'],
                                      samples=cfg['samples'],**(cfg['feed_overrides'] or {}))
    payload=(96 if method=='sc' else 4)+cfg['packet_metadata_bytes'];p=cfg['profile']
    allocation=dict(weight_hold_bytes=cfg['weight_slots']*feed_cfg.local_weight_hold_bytes,
        counter_allocated_bytes=cfg['counter_slots']*rows*112,producer_payload_bytes_per_slot=rows*payload,
        w8_accumulator_allocated_bytes=rows*4,counter_payload_bytes_per_output=96 if method=='sc' else 4,
        metadata_bytes_per_output=16,staging_allocated_bytes=cfg['staging_packets']*112,
        staging_payload_bytes_per_packet=payload,output_slots=p['restore_lanes']*p['restore_depth'],
        output_slot_bytes=24,pending_partial_write_bytes=cfg['partial_write_slots']*20,
        partial_sram_bytes=math.ceil(rows*4/16)*16,partial_logical_bytes=rows*4,
        uncharacterized_restore_pipeline_internal_bits=None,feed_response_bytes=feed_cfg.response_buffer_bytes,
        sample_hold_bits=feed_cfg.sample_hold_capacity_bits)
    require({k:value['storage'][k] for k in allocation}==allocation,'storage provision/demand accounting differs')
    require(value['storage']['sram_layout']['capacity_bytes']==feed_cfg.sram_capacity_bytes and
            value['storage']['sram_layout']['weight_wave_bytes']==feed_cfg.wave_bytes,'SRAM storage scope differs')
    from dataclasses import asdict
    require(value['feed_template']==value['feed_templates'][0],'primary feed template differs')
    sram=bytearray(feed_cfg.sram_capacity_bytes)
    for k,(template,receipt) in enumerate(zip(value['feed_templates'],value['feed_receipts'])):
        require(template['config']==asdict(feed_cfg),'feed configuration differs')
        require(template['addresses']==list(range(k*feed_cfg.wave_bytes,(k+1)*feed_cfg.wave_bytes,feed_cfg.word_bytes)),
                'feed physical addresses not distinct complete wave')
        require(deps.feed.validate(feed_cfg,template['events'],template['addresses'],template['sample_tokens'])==template['summary'],
                'independent feed template validation differs')
        require(digest(template)==receipt['template_sha256'],'feed template hash mismatch')
        payload=bytes(w&255 for row in fixture['inputs'][k]['weights'] for w in row)
        sram[k*feed_cfg.wave_bytes:(k+1)*feed_cfg.wave_bytes]=payload
        require(hashlib.sha256(payload).hexdigest()==receipt['weight_payload_sha256'],'feed operand payload differs')
        start=accepted['k%04d.feed'%k]['time_ps'];require(start==receipt['offset_ps'] and start%50000==0,'feed shift clock phase')
        preload=max(e['t_ps'] for e in template['events'] if e['kind']=='hold_write')
        feed_meta=accepted['k%04d.feed'%k]['metadata']
        require(feed_meta['actual_preload_ps']==preload and feed_meta['template_sha256']==digest(template) and
                feed_meta['weight_payload_sha256']==receipt['weight_payload_sha256'],'native feed binding differs')
        require(receipt['group']==k and receipt['weight_base']==k*feed_cfg.wave_bytes and
                receipt['last_hold_write_ps']==start+preload and
                receipt['exclusive_end_ps']==completed['k%04d.feed'%k]['time_ps'] and
                receipt['consumer_start_ps']==accepted['k%04d.produce'%k]['time_ps'] and
                receipt['consumer_end_ps']==completed['k%04d.produce'%k]['time_ps'],'feed interval receipt differs')
        shifted=[]
        for e in template['events']:
            if e['kind'].startswith('sample_') or e['kind']=='consume_resident':continue
            n=dict(e)
            for key in ('t_ps','start_ps','end_ps'):
                if key in n:n[key]+=start
            if 'sram_cycle' in n:n['sram_cycle']+=start//12500
            for key in ('core_cycle','start_core_cycle','end_core_cycle'):
                if key in n:n[key]+=start//10000
            shifted.append(n)
        if method=='sc':
            tokens=['k%d.sample%d'%(k,i) for i in range(cfg['samples'])]
            begin=accepted['k%04d.produce'%k]['time_ps']
            for i,token in enumerate(tokens):
                t=begin+i*10000
                shifted.extend([dict(kind='sample_begin',t_ps=t,sample=i,token=token,core_cycle=t//10000,
                    sequence_index=i,held_sample_bits=feed_cfg.sample_state_bits),
                    dict(kind='consume_resident',t_ps=t+10000,sample=i,token=token,start_ps=t,
                    start_core_cycle=t//10000,end_core_cycle=t//10000+1,nbytes=feed_cfg.wave_bytes),
                    dict(kind='sample_end',t_ps=t+10000,sample=i,token=token,consumed_bytes=feed_cfg.wave_bytes)])
            shifted.sort(key=lambda e:(e['t_ps'],deps.feed._RANK[e['kind']],e.get('read_id',-1)))
            require(deps.feed.validate(feed_cfg,shifted,template['addresses'],tokens)==receipt['replay_validation'],
                    'independent actual-SC feed validation differs')
        require(digest(shifted)==receipt['shifted_trace_sha256'],'translated feed trace hash differs')
    partial=value['partial_receipts'];base=value['storage']['sram_layout']['partial_base']
    require(len(partial)==(2*groups-1)*rows,'partial receipt count differs')
    expected_ids={ident for ident in accepted if ident.endswith(('.partial_read','.partial_write'))}
    require({x['operation'] for x in partial}==expected_ids,'partial receipt operation coverage differs')
    require([x['completion_ps'] for x in partial]==sorted(x['completion_ps'] for x in partial),
            'partial receipts not completion ordered')
    partial_words=[0]*rows;next_write=[0]*rows
    for x in partial:
        k,row=x['group'],x['row'];kind=x['kind'];ident=x['operation']
        require(kind in ('read','write') and 0<=k<groups and 0<=row<rows,'invalid partial receipt identity')
        address=base+4*row;physical=address//16*16;mask=15<<(address%16)
        require(ident=='k%04d.r%05d.partial_%s'%(k,row,kind) and
                x['completion_ps']==completed[ident]['time_ps'],'partial completion identity differs')
        require((x['address'],x['physical_address'],x['byte_enable'])==(address,physical,mask),
                'partial receipt address or byte mask differs')
        before=bytes(sram[physical:physical+16]);require(x['before_hex']==before.hex(),'partial before image differs')
        if kind=='read':
            require(k>0 and next_write[row]==k and x['word']==partial_words[row]==
                    int.from_bytes(sram[address:address+4],'little'),'partial read content/order differs')
        else:
            require(next_write[row]==k,'partial write group order differs')
            wanted=deps.restore.add_words(partial_words[row],fixture[method+'_partials'][k][row])
            require(x['word']==wanted,'ordered cross-group FP32 partial differs')
            sram[address:address+4]=wanted.to_bytes(4,'little');partial_words[row]=wanted;next_write[row]+=1
        after=bytes(sram[physical:physical+16]);require(x['after_hex']==after.hex(),'partial after image differs')
        require(all(a==b for i,(a,b) in enumerate(zip(before,after)) if not mask&(1<<i)),
                'partial write corrupts neighboring SRAM bytes')
    require(next_write==[groups]*rows and partial_words==value['output_words'],'final partial SRAM coverage differs')
    require(hashlib.sha256(sram).hexdigest()==value['final_sram_sha256'],'complete final SRAM hash differs')
    return len(accepted)


def main_grid(cases,fixtures):
    """The registered acceptance grid is explicit, independent of run manifests."""
    require(set(fixtures)=={0,1,2},'main48 requires exactly seeds 0, 1, 2')
    for f in fixtures.values():
        require((f['groups'],f['tiles'],f['rows_per_tile'],f['samples'])==(4,8,64,32),
                'main48 fixture geometry differs')
    expected={f'{name}_{method}_seed{seed}':dict(id=f'{name}_{method}_seed{seed}',candidate=name,
              method=method,seed=seed,config={**MAIN_CONFIG,**overrides})
              for name,overrides in MAIN_CANDIDATES.items() for seed in (0,1,2) for method in ('sc','w8')}
    require(len(cases)==48 and {c['id'] for c in cases}==set(expected),
            'main48 requires all eight candidates, three seeds and two methods (48 cases)')
    require(all(c==expected[c['id']] for c in cases),'main48 candidate configuration differs')


def verify(fixtures_dir,run_dirs,dependency_root,expected_grid='main48'):
    from .dependencies import load
    deps=load(dependency_root);cache=set();fm,fs,fixtures=fixture_audit(fixtures_dir,cache)
    records=[];seen=set();pairs=defaultdict(dict);all_cases=[]
    require(expected_grid in ('main48','manifest'),'unsupported expected grid')
    for folder in run_dirs:all_cases.extend(read(folder/'RUN_MANIFEST.json')['cases'])
    if expected_grid=='main48':main_grid(all_cases,fixtures)
    for folder in run_dirs:
        source=read(folder/'EXECUTION.json');source_audit(source,cache)
        require(source['files']==fs['files'] and source['dependencies']==fs['dependencies'],'fixture/run execution sources differ')
        require(source['dependencies']==deps.lock,'verification dependency cache differs from execution')
        manifest=read(folder/'RUN_MANIFEST.json')
        require(manifest['source_sha256']==source['source_sha256'] and manifest['execution_commit']==source['commit'],
                'run manifest source differs')
        require(manifest['fixture_manifest']==record((fixtures_dir/'FIXTURES.json').read_bytes()),'fixture manifest changed')
        cases=manifest['cases'];ids=[x['id'] for x in cases]
        require(len(set(ids))==len(ids),'duplicate manifest case')
        require(not list(folder.glob('*.FAILURE.json')),'run contains failure record')
        require({p.name for p in folder.glob('*.json.gz')}=={n+'.json.gz' for n in ids},'result case coverage differs')
        require({p.name for p in folder.glob('*.receipt.json')}=={n+'.receipt.json' for n in ids},'receipt case coverage differs')
        for case in cases:
            ident=case['id'];require(ident not in seen,'duplicate case across runs');seen.add(ident)
            require(case['method'] in ('sc','w8') and case['seed'] in fixtures,'unknown fixture/method')
            fixture=fixtures[case['seed']];receipt=read(folder/(ident+'.receipt.json'))
            require(receipt['case']==case and receipt['file']==ident+'.json.gz','receipt case/file differs')
            compressed=(folder/receipt['file']).read_bytes()
            require(record(compressed)=={k:receipt[k] for k in ('bytes','sha256')},'gzip payload SHA differs')
            raw=gzip.decompress(compressed)
            require(record(raw)==dict(bytes=receipt['json_bytes'],sha256=receipt['json_sha256']),'raw JSON SHA differs')
            value=json.loads(raw)
            require(value['case']==case and value['source']==source,'result source/case differs')
            cfg={**case['config'],'profile':{**PROFILE,**(case['config']['profile'] or {})}}
            require(value['config']==cfg and value['method']==case['method'],'result configuration differs')
            for field in ('full_physical_area_mm2','full_physical_energy_J','quality_ppl'):
                require(value[field] is None,'unsupported physical/quality claim')
            require(value['fixture_sha256']==receipt['fixture_sha256']==fixture['fixture_sha256'],'fixture binding differs')
            require(value['input_sha256']==fixture['hashes']['inputs'],'shared input hash differs')
            require(receipt['source_sha256']==source['source_sha256'],'receipt source digest differs')
            require(receipt['finish_ps']==value['native_result']['finish_ps']==value['metrics']['finish_ps'],'finish receipt differs')
            require(receipt['metrics']==value['metrics'] and receipt['storage']==value['storage'],'receipt summary differs')
            require(value['output_reference_equal'] is True and receipt['output_reference_equal'] is True,'numeric gate not passed')
            require(manifest['mode']=='both' and value['cycle_event_equal'] is True and receipt['cycle_event_equal'] is True,
                    'cycle/event confirmation required')
            equivalence=digest({k:value['native_result'][k] for k in EQUIVALENCE_KEYS});output=digest(value['output_words'])
            observables=digest({key:value[key] for key in ('partial_receipts','feed_receipts','row_receipts','final_sram_sha256','storage')})
            for field,wanted in [('event_equivalence_sha256',equivalence),('cycle_equivalence_sha256',equivalence),
                                 ('event_output_sha256',output),('cycle_output_sha256',output),
                                 ('event_observables_sha256',observables),('cycle_observables_sha256',observables)]:
                require(value.get(field)==wanted and receipt.get(field)==wanted,'missing/inconsistent cycle evidence: '+field)
            operations=payload_audit(value,fixture,deps)
            key=(case['candidate'],case['seed']);require(case['method'] not in pairs[key],'duplicate paired method')
            pairs[key][case['method']]=(cfg,value['storage'])
            records.append(dict(case=ident,run=folder.as_posix(),operations=operations,
                gzip_sha256=receipt['sha256'],json_sha256=receipt['json_sha256'],
                fixture_sha256=fixture['fixture_sha256'],output_sha256=output,
                equivalence_sha256=equivalence,observables_sha256=observables,
                finish_ps=receipt['finish_ps'],passed=True))
    for key,pair in pairs.items():
        require(set(pair)=={'sc','w8'},'missing same-configuration SC/W8 partner: '+str(key))
        require(pair['sc'][0]==pair['w8'][0],'paired hardware configuration differs')
        # Method-specific payload demand may differ; provisioned maxima must not.
        for name in ('weight_hold_bytes','counter_allocated_bytes','staging_allocated_bytes','output_slots',
                     'output_slot_bytes','pending_partial_write_bytes','partial_sram_bytes','sram_layout',
                     'feed_response_bytes','sample_hold_bits','w8_accumulator_allocated_bytes'):
            require(pair['sc'][1][name]==pair['w8'][1][name],'paired storage allocation differs: '+name)
    require(pairs,'no result cases')
    for candidate in {k[0] for k in pairs}:
        require({seed for name,seed in pairs if name==candidate}==set(fixtures),'candidate seed coverage incomplete')
    return dict(passed=True,expected_grid=expected_grid,cases=len(records),pairs=len(pairs),fixtures=len(fixtures),records=records,
        verifier=dict(path=Path(__file__).relative_to(ROOT).as_posix(),**record(Path(__file__).read_bytes())),
        execution_commit=fs['commit'],execution_source_sha256=fs['source_sha256'],
        dependency_source_sha256=fs['dependency_source_sha256'],
        checks=['gzip and raw JSON hashes','fixture and expected-word hashes','frozen five source and thirteen dependency Git blobs',
                'exact planned cases and paired configurations','numeric output and independent native trace conservation',
                'separate cycle/event equivalence receipts','finite credits/resource instances/latency/II',
                'distinct SRAM weight/partial addresses and exclusive fabric','ordered partial byte-mask replay and final SRAM SHA',
                'rounded partial endpoint service charge','imported independent feed validator'],
        scope='artifact and conditional-contract audit; no simulation rerun, STA, PPA, full FFN or PPL')


def main():
    p=argparse.ArgumentParser();p.add_argument('--fixtures',type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--dependencies',type=Path,default=os.environ.get('FFN_DATAFLOW_DEPS'))
    p.add_argument('--expected-grid',choices=('main48','manifest'),default='main48',
                   help='main48 is formal acceptance; manifest is partial/debug audit only')
    a=p.parse_args();require(a.dependencies is not None,'--dependencies or FFN_DATAFLOW_DEPS required')
    result=verify(a.fixtures,a.runs,a.dependencies,a.expected_grid)
    with a.output.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:result[k] for k in ('passed','cases','pairs','fixtures')}))


if __name__=='__main__':main()
