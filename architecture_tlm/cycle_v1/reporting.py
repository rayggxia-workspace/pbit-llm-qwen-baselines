"""Derived trace inspection; never convert overlapping sums into power."""
from collections import Counter, defaultdict
import html
import json


def timeline_summary(kernel,result):
    intervals=defaultdict(list)
    stalls=Counter()
    open_stalls={}
    requests=defaultdict(Counter)
    waits=defaultdict(list)
    rows=[]
    for event in result.trace:
        key=event.get('op'),event.get('phase')
        if event['kind']=='stall':
            if key in open_stalls:
                start,reason=open_stalls[key]
                stalls[reason.split(':')[0]]+=event['time_ps']-start
                waits[key[0]].append({'phase':key[1],'start_ps':start,'end_ps':event['time_ps'],'reason':reason})
            open_stalls[key]=(event['time_ps'],event['reason'])
        elif event['kind']=='stall_end' and key in open_stalls:
            start,reason=open_stalls.pop(key)
            stalls[reason.split(':')[0]]+=event['time_ps']-start
            waits[key[0]].append({'phase':key[1],'start_ps':start,'end_ps':event['time_ps'],'reason':reason})
        elif event['kind']=='accept' and 'address' in event:
            counter=requests[event['resource']]
            counter['write_bytes' if event['write'] else 'read_bytes']+=event['size_bytes']
            counter['requests']+=1
            counter['line_beats']+=sum(event['bank_beats'].values())
    if open_stalls:
        raise AssertionError('completed execution retained an open stall interval')
    for ident,start in result.accepted_ps.items():
        op=kernel.operations[ident]
        end=result.completion_ps[ident]
        intervals[op.resource].append((start,end))
        row={'id':ident,'resource':op.resource,'start_ps':start,'end_ps':end,
             'dependencies':list(op.deps),'inputs':dict(op.inputs),'outputs':dict(op.outputs),
             'actions':dict(op.actions),'metadata':dict(op.metadata)}
        row['wait_intervals']=waits.get(ident,[])
        resource=kernel.resources.get(op.resource) or kernel.memory_ports[op.resource]
        row['clock']={'name':resource.clock.name,'period_ps':resource.clock.period_ps,'phase_ps':resource.clock.phase_ps}
        row['latency_cycles']=op.latency_cycles if op.latency_cycles is not None else resource.latency_cycles
        row['ii_cycles']=op.ii_cycles if op.ii_cycles is not None else resource.ii_cycles
        if op.memory:
            row['memory']={'address':op.memory.address,'bytes':op.memory.size_bytes,'write':op.memory.write}
        rows.append(row)
    active={}
    for name,spans in intervals.items():
        total=0;left=right=None
        for start,end in sorted(spans):
            if right is None or start>right:
                if right is not None: total+=right-left
                left,right=start,end
            else: right=max(right,end)
        total+=right-left
        active[name]={'at_least_one_inflight_ps':total,
                      'at_least_one_inflight_fraction':total/result.finish_ps if result.finish_ps else 0,
                      'meaning':'union of accepted-to-completed intervals; includes stalled occupancy; not switching utilization'}
    for stats in requests.values():
        stats['effective_GB_per_s']=(stats['read_bytes']+stats['write_bytes'])*1000/result.finish_ps if result.finish_ps else 0
    chain=[]
    ident=max(result.completion_ps,key=result.completion_ps.get,default=None)
    while ident is not None:
        op=kernel.operations[ident]
        chain.append({'operation':ident,'resource':op.resource,'accepted_ps':result.accepted_ps[ident],
                      'completed_ps':result.completion_ps[ident]})
        ident=max(op.deps,key=result.completion_ps.get,default=None)
    return {'resource_inflight_union':active,'memory_requests':dict(requests),
            'latest_dependency_backtrace':list(reversed(chain)),
            'backtrace_note':'latest completed explicit predecessor only; resource/credit hazards may dominate; not a complete critical-path proof',
            'stall_operation_ps':dict(stalls),
            'stall_note':'sum of per-operation intervals, may overlap; not an additive wall-clock decomposition'},rows


def write_inspector(path,summary,rows):
    payload=json.dumps({'summary':summary,'rows':rows},ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    document='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>周期执行检查台</title>
<style>body{font:15px system-ui;margin:24px;background:#f6f8fa;color:#172b4d}input,select{padding:8px;margin:8px}button{cursor:pointer}#grid{height:55vh;overflow:auto;background:white;border:1px solid #ccd} .row{display:flex;height:25px;border-bottom:1px solid #eee}.name{width:330px;flex-shrink:0;overflow:hidden;white-space:nowrap;font:11px monospace}.track{position:relative;flex:1}.bar{position:absolute;top:4px;height:17px;min-width:2px;border:0;background:#2176ae;border-radius:2px}pre{white-space:pre-wrap;max-height:30vh;overflow:auto;background:white;padding:12px}.note{color:#586b7c}</style>
<h1>周期执行检查台</h1><p class="note">点击时间条查看依赖、资源、实际地址、输入/输出额度和动作。时间为配置模型；不代表 STA、PPA 或完整模型质量。</p>
<label>操作或资源 <input id="filter" placeholder="weight / sampler / sram"></label>
<label>起点 ns <input id="left" type="number" min="0" value="0"></label>
<label>终点 ns <input id="right" type="number" min="0"></label><button id="reset">全程</button>
<p id="status"></p><div id="grid"></div><pre id="detail"></pre>
<script>const DATA=__DATA__;const $=x=>document.getElementById(x);const finish=DATA.summary.finish_ps/1000;$('right').value=finish;
function render(){const text=$('filter').value.toLowerCase(),a=Number($('left').value),b=Number($('right').value);$('grid').replaceChildren();if(!(b>a)){ $('status').textContent='终点须大于起点';return;}
const rows=DATA.rows.filter(r=>(r.id+' '+r.resource).toLowerCase().includes(text)&&r.end_ps/1000>=a&&r.start_ps/1000<=b);$('status').textContent=`匹配 ${rows.length} 个操作；显示前 2000 个。总时间 ${finish} ns。`;
for(const r of rows.slice(0,2000)){const row=document.createElement('div');row.className='row';const name=document.createElement('span');name.className='name';name.textContent=r.id;const track=document.createElement('div');track.className='track';const bar=document.createElement('button');bar.className='bar';const start=Math.max(a,r.start_ps/1000),end=Math.min(b,r.end_ps/1000);bar.style.left=(start-a)/(b-a)*100+'%';bar.style.width=Math.max(.12,(end-start)/(b-a)*100)+'%';bar.title=r.resource+' '+r.start_ps/1000+' → '+r.end_ps/1000+' ns';bar.onclick=()=>{$('detail').textContent=JSON.stringify(r,null,2)};track.append(bar);row.append(name,track);$('grid').append(row)}}
for(const id of ['filter','left','right'])$(id).addEventListener('input',render);$('reset').onclick=()=>{$('left').value=0;$('right').value=finish;render()};$('detail').textContent=JSON.stringify(DATA.summary,null,2);render();</script></html>'''
    path.write_text(document.replace('__DATA__',payload),encoding='utf-8')
