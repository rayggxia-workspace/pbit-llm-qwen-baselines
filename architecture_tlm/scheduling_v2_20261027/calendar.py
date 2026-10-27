"""Earliest legal reservation in existing per-resource idle intervals.

Only already exposed finite tile lookahead is scheduled: this does not add
instructions, compute engines, DMA descriptors or storage. Dependencies arrive
as ready times. The single real DRAM actor retains its own monotonic issue
contract. Calendars before a completed sequential phase are discarded.
"""
import bisect
import math
from collections import Counter,defaultdict
from architecture_tlm.unified_v6.core import Scheduler
from architecture_tlm.clock500_resource_20261026.clock_gating import is_compute_resource

class ReadyCalendar(Scheduler):
    def __init__(self,keep=2000,*,core_period_ns=2.,installed_resources=()):
        super().__init__(keep)
        self.calendar=defaultdict(list);self.floor=0.;self.period=core_period_ns
        self.installed=set(installed_resources);self.stats=Counter()

    def advance(self,ready):
        # A phase boundary is an actual dependency fence of the original model.
        if ready+1e-6<self.floor:raise ValueError('phase fence moved backwards')
        self.floor=max(self.floor,ready)
        for r,events in self.calendar.items():
            cut=bisect.bisect_right(events,(self.floor,float('inf')))
            if cut and events[cut-1][1]>self.floor+1e-8:cut-=1
            if cut:del events[:cut]

    def _fit(self,resource,start,duration,period):
        events=self.calendar[resource]
        i=bisect.bisect_right(events,(start,float('inf')))
        if i and events[i-1][1]>start+1e-8:
            start=events[i-1][1]
            if period:start=math.ceil(start/period-1e-10)*period
        while i<len(events) and start+duration>events[i][0]+1e-8:
            start=max(start,events[i][1]);i+=1
            if period:start=math.ceil(start/period-1e-10)*period
        return start

    def reserve(self,stage,ready,duration,resources,period=0.,**detail):
        if min(ready,duration)<0 or not math.isfinite(ready+duration):raise ValueError('invalid time')
        resources=tuple(sorted(set(resources)))
        start=max(ready,self.floor)
        if period:start=math.ceil(start/period-1e-10)*period
        append=max([start]+[self.free[r] for r in resources])
        if period:append=math.ceil(append/period-1e-10)*period
        if duration:
            while True:
                previous=start
                for r in resources:start=self._fit(r,start,duration,period)
                if start<=previous+1e-8:break
        done=start+duration;interval=(start,done)
        for r in resources:
            if duration:
                events=self.calendar[r]
                if not events or start>=events[-1][1]-1e-8:events.append(interval)
                else:bisect.insort(events,interval)
                self.stats['peak_intervals_per_resource']=max(self.stats['peak_intervals_per_resource'],len(events))
            self.free[r]=max(self.free[r],done);self.busy[r]+=duration
            if is_compute_resource(r):self.installed.add(r)
        if start<append-1e-7:
            self.stats['gap_filled_reservations']+=1
            self.stats['avoided_append_wait_ns']+=append-start
        self.wait[stage]+=start-ready;self.by_stage[stage]+=duration
        ident=self.count;self.count+=1
        if len(self.events)<self.keep:
            self.events.append(dict(id=ident,stage=stage,ready_ns=ready,start_ns=start,end_ns=done,resources=resources,**detail))
        return done

    def report(self):
        return dict(policy='earliest legal interval for already exposed jobs',stats=dict(self.stats),
                    extra_data_buffer_bytes=0,compute_arrays_added=0,
                    DRAM_policy='original monotonic single actor; no cross-descriptor concurrency added',
                    scope='resource arbitration macro with original finite tile buffers; no clock-gate wake model')

    def clock_gating_report(self,end_ns=None):
        end=self.end() if end_ns is None else end_ns;h=math.ceil(end/self.period-1e-10)*self.period
        resources={}
        for r in sorted(self.installed):
            busy=self.busy[r]
            resources[r]=dict(last_end_ns=self.free[r],busy_ns=busy,idle_clock_on_ns=h-busy,wakeup_ns=0.,off_ns=0.,wakeups=0,reservations=None,clock_on_ns=h,lifetime_ns=h,busy_cycles=busy/self.period,clock_on_cycles=h/self.period,off_cycles=0.,wakeup_cycles=0.)
        return dict(enabled=False,core_period_ns=self.period,idle_threshold_cycles=8,wake_cycles=1,lifetime_ns=h,resources=resources,coverage='installed and observed compute domains; ungated isolation experiment')
