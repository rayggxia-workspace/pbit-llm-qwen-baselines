"""Tile-level event estimate, not per-beat/native DRAM simulation.

Run a GU/Wd layer once, not84million64B transfers for a whole token. Calibration
offsets retain the reference stage's conversion/bank/input/control overhead.
Changing sample count still contends for finite slots, cores and state ports.
"""
from collections import deque
from pathlib import Path
import argparse,heapq,itertools,json,math,time

def order(groups,blocks,batch):
    if batch:
        count=(groups+batch-1)//batch;small,extra=divmod(groups,count);base=0;out=[]
        for i in range(count):
            size=small+(i<extra)
            out.extend((o,k) for k in range(blocks) for o in range(base,base+size));base+=size
        return out
    return [(o,k) for k in range(blocks) for o in range(groups)]

def stage(samples,*,groups,blocks,batch=0,cores=12,slots=32,state_ports=2,
          bandwidth_GBs=136.4606,load_latency_ns=40.,state_service_ns=60.,
          preloaded=0,clock_MHz=100):
    if min(samples,groups,blocks,cores,slots,state_ports,bandwidth_GBs,clock_MHz)<=0:
        raise ValueError('positive resources required')
    period=1000/clock_MHz;compute=(samples+2)*period
    tasks=deque(enumerate(order(groups,blocks,batch)))
    events=[];serial=itertools.count();ready={};expected=[0]*groups;occupied=set()
    core_free=[True]*cores;credits=[0]*cores;input_key=[None]*cores
    port_free=[True]*state_ports;retire=deque();completed=[0];now=[0.];mem_free=[0.]
    def later(t,kind,*args):heapq.heappush(events,(t,next(serial),kind,args))
    def load(slot,initial=False):
        if not tasks:return
        ix,(out,k)=tasks.popleft()
        if initial and ix<preloaded:later(0,'load',slot,ix,out,k);return
        begin=max(now[0],mem_free[0]);mem_free[0]=begin+8192/bandwidth_GBs
        later(mem_free[0]+load_latency_ns,'load',slot,ix,out,k)
    for s in range(min(slots,len(tasks))):load(s,True)
    while events:
        t,_,kind,args=heapq.heappop(events);now[0]=t
        if kind=='load':
            slot,ix,out,k=args;ready[slot]=(ix,out,k)
        elif kind=='core':
            core,slot,out,k=args;core_free[core]=True;retire.append((core,out,k));load(slot)
        elif kind=='state':
            port,core,out,k=args;port_free[port]=True;credits[core]-=1
            occupied.remove(out);expected[out]=k+1;completed[0]+=1
        for port in range(state_ports):
            if not port_free[port] or not retire:continue
            core,out,k=retire.popleft();port_free[port]=False
            later(t+state_service_ns,'state',port,core,out,k)
        for core in range(cores):
            if not core_free[core] or credits[core]>=2:continue
            eligible=[(ix,slot,out,k) for slot,(ix,out,k) in ready.items()
                      if expected[out]==k and out not in occupied]
            if not eligible:continue
            ix,slot,out,k=min(eligible,key=lambda x:((input_key[core]!=x[3]) if batch else False,x[0]))
            del ready[slot];occupied.add(out);credits[core]+=1;core_free[core]=False
            input_cost=period if input_key[core]!=k else 0;input_key[core]=k
            later(t+input_cost+compute,'core',core,slot,out,k)
    assert completed[0]==groups*blocks and not ready and not tasks and not occupied
    weight_floor=max(0,groups*blocks-preloaded)*8192/bandwidth_GBs
    floors=dict(weight_ns=weight_floor,compute_ns=groups*blocks*compute/cores,
        state_ns=groups*blocks*state_service_ns/state_ports)
    return dict(elapsed_ns=now[0],frames=groups*blocks,floors=floors,
        dominant_floor=max(floors,key=floors.get),samples=samples)

def estimate(profile,gu_samples,wd_samples,bandwidth_GBs=None):
    # The phase offsets are calibrated at the recorded reference bandwidth.
    # Recalibrating both sides at a new bandwidth cancels the memory penalty.
    # Other stages also depend on bandwidth, so reject that unsupported scan.
    bw=profile['bandwidth_GBs']
    if bandwidth_GBs is not None and not math.isclose(bandwidth_GBs,bw,rel_tol=1e-12,abs_tol=1e-12):
        raise ValueError('sample-only estimator requires the reference bandwidth; use a new memory replay for bandwidth changes')
    layers=profile['layers'];hidden=profile['hidden'];ffn=profile['ffn']
    stages={};reference=profile.get('reference_samples',64)
    for mode,t,groups,blocks,batch,preload in (
        ('GU',gu_samples,ffn//64,hidden//64,96,32),
        ('NL_Wd',wd_samples,hidden//128,ffn//64,0,0)):
        options=dict(groups=groups,blocks=blocks,batch=batch,preloaded=preload,
            cores=profile['cores'],slots=profile['weight_slots'],state_ports=profile['state_ports'],
            bandwidth_GBs=bw,load_latency_ns=profile.get('tile_load_latency_ns',40),
            state_service_ns=profile.get('state_service_ns',60),clock_MHz=profile.get('clock_MHz',100))
        base=stage(reference,**options);new=stage(t,**options)
        reference_ms=profile['phase_totals_ms'][mode]
        delta_ms=(new['elapsed_ns']-base['elapsed_ns'])*layers*1e-6
        value=max(0,reference_ms+delta_ms)
        stages[mode]=dict(estimated_total_ms=value,reference_total_ms=reference_ms,
            change_ms=value-reference_ms,one_layer_tile_model=new,
            reference_one_layer_tile_model=base,
            calibration_offset_ms=reference_ms-base['elapsed_ns']*layers*1e-6)
    total=profile['including_lm_head_ms']+sum(x['change_ms'] for x in stages.values())
    head=profile['lm_head_stage_ms']
    return dict(GU_samples=gu_samples,NL_Wd_samples=wd_samples,
        including_lm_head_ms=total,lm_head_stage_ms=head,excluding_lm_head_stage_ms=total-head,
        change_percent=(total/profile['including_lm_head_ms']-1)*100,
        bandwidth_GBs=bw,stages=stages,reference_configuration=profile['configuration'],
        scope='calibrated tile event estimate; finite slot/core/state and macro bandwidth; not native LPDDR or measured PPA')

def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',type=Path,default=Path(__file__).with_name('REFERENCE_PROFILE.json'))
    p.add_argument('--gu',type=int,default=8);p.add_argument('--wd',type=int,default=32)
    p.add_argument('--bandwidth',type=float);p.add_argument('--scan',action='store_true');p.add_argument('--out',type=Path)
    a=p.parse_args();profile=json.loads(a.profile.read_bytes());start=time.perf_counter()
    pairs=[(64,64),(32,32),(16,32),(8,32),(8,16),(4,32)] if a.scan else [(a.gu,a.wd)]
    results=[estimate(profile,x,y,a.bandwidth) for x,y in pairs]
    out=dict(reference=profile,results=results,wall_seconds=time.perf_counter()-start)
    if a.out:a.out.write_bytes((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())
    for r in results:print(json.dumps({k:r[k] for k in ('GU_samples','NL_Wd_samples','including_lm_head_ms','excluding_lm_head_stage_ms','lm_head_stage_ms','change_percent')}))
    print('wall_seconds='+str(out['wall_seconds']))

if __name__=='__main__':main()
