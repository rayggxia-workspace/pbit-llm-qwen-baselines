"""A timed Ising sampler interface; deliberately no internal network simulator.

One reusable macro, serialized query service. All internal stochastic sources,
state, inhibition feedback and readout encoder belong to this macro's PPA.
Numerical oracle is ONLY for generating workload addresses, not simulated
hardware Softmax/CDF and not evidence of mixing/finite-precision correctness.
"""
import hashlib
import json
import math
from pathlib import Path
from attention_reference_v3 import softmax,categorical


class IsingMacro:
    def __init__(self,cfg,capacity):
        self.cfg=dict(cfg);self.capacity=capacity;self.free=0.;self.active_ns=0.
        self.energy_J=0.;self.calls=0;self.trace={}
        if not isinstance(capacity,int) or capacity<1:raise ValueError('positive integer capacity required')
        for key,value in cfg.items():
            if isinstance(value,(float,int)) and not isinstance(value,bool):
                if not math.isfinite(value) or value<0:raise ValueError(key)
        for key in ('bias_bits','config_bandwidth_GBs','sample_period_ns'):
            if cfg[key]<=0:raise ValueError(key)
        if not isinstance(cfg['bias_bits'],int):raise ValueError('bias_bits must be integer')
        if not cfg['includes_internal_rng_feedback_state_and_encoder']:
            raise ValueError('incomplete macro cost contract: RNG/feedback/readout must be included')
        if cfg['numerical_source'] not in ('ideal_iid_oracle','sample_trace'):raise ValueError('numerical source')
        self.provenance=dict(kind=cfg['numerical_source'],hardware_distribution_validated=False)
        if cfg['numerical_source']=='sample_trace':
            p=Path(cfg['sample_trace_file']);raw=p.read_bytes();d=json.loads(raw)
            for row in d['rows']:
                key=(row['token'],row['layer'],row['head'])
                if key in self.trace:raise ValueError('duplicate Ising sample trace')
                self.trace[key]=row
            self.provenance.update(sha256=hashlib.sha256(raw).hexdigest(),declared_provenance=d.get('provenance',{}))

    @property
    def area_mm2(self):
        return self.cfg['area_base_mm2']+self.capacity*self.cfg['area_mm2_per_slot']

    def request(self,ready,logits,samples,rng,identity,candidate_ids,output_ns_per_index=0.):
        n=len(logits);c=self.cfg
        if not 1<=n<=self.capacity:raise ValueError('candidate count exceeds Ising capacity; no silent truncation')
        if len(candidate_ids)!=n or len(set(candidate_ids))!=n:raise ValueError('candidate map')
        if samples<1 or int(samples)!=samples:raise ValueError('sample count')
        if not all(math.isfinite(x) for x in logits):raise ValueError('nonfinite valid logits')
        if self.trace:
            try:r=self.trace[identity]
            except KeyError:raise ValueError('missing Ising sample trace row '+str(identity))
            if r['candidate_ids']!=candidate_ids:raise ValueError('Ising trace candidate-map mismatch')
            ids=r['local_indices']
            if len(ids)!=samples or any(type(i)!=int or i<0 or i>=n for i in ids):raise ValueError('invalid/masked Ising output')
        elif c['numerical_source']=='sample_trace':raise ValueError('empty sample trace')
        else:ids=categorical(softmax(logits),samples,rng)
        # Full fixed-width programming plus validity mask, not just active slots.
        bits=self.capacity*(c['bias_bits']+1)
        size=math.ceil(bits/8);start=max(ready,self.free)
        configured=start+c['config_latency_ns']+size/c['config_bandwidth_GBs']
        if not math.isfinite(output_ns_per_index) or output_ns_per_index<0:raise ValueError('output transfer time')
        period=max(c['sample_period_ns'],output_ns_per_index)
        first=configured+c['settle_ns']+c['burn_ns']+period+c['readout_latency_ns']
        end=first+(samples-1)*period+output_ns_per_index
        active=end-start
        energy=bits*c['config_pJ_per_bit']*1e-12+active*1e-9*(c['active_base_W']+self.capacity*c['active_W_per_slot'])
        self.free=end;self.active_ns+=active;self.energy_J+=energy;self.calls+=1
        return ids,dict(start_ns=start,end_ns=end,configured_ns=configured,first_sample_ns=first,
            valid_candidates=n,capacity=self.capacity,masked_slots=self.capacity-n,
            config_bytes=size,config_bits=bits,samples=samples,energy_J=energy,
            effective_sample_period_ns=period,retained_internal_output_indices=1,
            service='stream indices to host scratch with backpressure; one reusable macro')

    def finish(self,end):
        if end+1e-6<self.free:raise ValueError('finish before sampler completion')
        idle=max(0,end-self.active_ns)*1e-9*self.cfg['idle_W']
        return dict(calls=self.calls,active_ns=self.active_ns,active_and_config_J=self.energy_J,
            idle_J=idle,area_mm2=self.area_mm2,capacity=self.capacity,
            internal_rng_separately_charged=False,numerical_source=self.provenance,cost_status=self.cfg['cost_status'])
