"""Actual Issue95 protocol in the complete decoder, in one core/source clock domain.

Idle event jumps and a bit-exact Bivium block evaluator accelerate the Python
simulation only. Neither changes the original RTL, recurrence or physical work.
"""
import hashlib
import json
import math
import types
from collections import Counter
from pathlib import Path

from architecture_tlm.random_service import Endpoint, RandomNetwork, SeedWords
from architecture_tlm.random_service.backends import generate
from architecture_tlm.random_service.service import FullFrameArray, RandomPort, SigmoidTable


def reverse_bits(value, n):
    return int(format(value, '0%db' % n)[::-1], 2)


def fast_generate(kind, state):
    if kind != 'bivium':
        return generate(kind, state)
    if not 0 < state < 1 << 177:
        raise ValueError('nonzero 177-bit state')
    a, b, out = state & ((1 << 93)-1), state >> 93, 0
    for offset, n in ((0,64),(64,64),(128,32)):
        mask = (1 << n)-1
        def tap(reg, k):
            return reverse_bits((reg >> (k-n+1)) & mask, n)
        t1, t2 = tap(a,65)^tap(a,92), tap(b,68)^tap(b,83)
        out |= (t1^t2) << offset
        fa = t2 ^ (tap(b,81)&tap(b,82)) ^ tap(a,68)
        fb = t1 ^ (tap(a,90)&tap(a,91)) ^ tap(b,77)
        a = ((a << n) | reverse_bits(fa,n)) & ((1 << 93)-1)
        b = ((b << n) | reverse_bits(fb,n)) & ((1 << 84)-1)
    return tuple((out >> (8*i)) & 255 for i in range(20)), a | (b << 93)


class FastEndpoint(Endpoint):
    # Identical protocol function, with a private generate binding. No mutation
    # of the shared original module/global namespace or another task's model.
    tick = types.FunctionType(Endpoint.tick.__code__,
        {**Endpoint.tick.__globals__, 'generate':fast_generate},
        name='tick', argdefs=Endpoint.tick.__defaults__)


class EventNetwork(RandomNetwork):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.jumped_edges = 0

    def advance_to(self, target):
        if type(target) is not int or target < self.cycle:
            raise ValueError('monotonic integer source time')
        while self.cycle < target:
            # Responses, warmup, a complete packet, and an available seed beat
            # are real events and must execute the original tick function.
            ps = list(self.ports.values())
            req = [p.signals(True,self.ingress[k].valid)['seed_req'] for k,p in self.ports.items()]
            must_tick = any(p.valid or p.warm for p in ps) or any(g.valid for g in self.ingress.values())
            must_tick |= any(req) and (self.target is None or self.source.next_cycle <= self.cycle)
            if must_tick:
                self.tick();continue
            span = target-self.cycle
            if any(req):
                span = min(span,self.source.next_cycle-self.cycle)
            for p in ps:
                if p.seeded and p.reseed_cycles and p.age < p.reseed_cycles:
                    span = min(span,p.reseed_cycles-p.age)
            if span < 1:
                self.tick();continue
            for k,p in self.ports.items():
                pre = p.signals(True,self.ingress[k].valid)
                p.counts['clock_edges'] += span
                p.counts['seed_wait_cycles'] += span*int(pre['seed_req'])
                # Endpoint.tick evaluates deferred status AFTER incrementing age.
                deferred=(max(0,span-max(0,p.reseed_cycles-p.age-1))
                          if p.locked and p.reseed_cycles else 0)
                p.counts['reseed_deferred_cycles'] += deferred
                if p.seeded:p.age=min(0xffffffff,p.age+span)
                p.error=False;p.cycle+=span
            self.cycle+=span;self.jumped_edges+=span


def selector_parameters(logits, bias, temperature, block=64):
    """Same max4/free-block normalization; no oracle RNG is consumed."""
    if temperature <= 0:raise ValueError('positive selector temperature')
    scores=[]
    for start in range(0,len(logits),block):
        sub=[logits[t:min(t+block//4,len(logits))]
             for t in range(start,min(start+block,len(logits)),block//4)]
        scores.append(max(sum(s)/len(s) for s in sub))
    n=len(scores);forced={0,n-1,max(0,n-2)}
    free=[s for i,s in enumerate(scores) if i not in forced]
    mu=sum(free)/max(1,len(free))
    std=max(.01,math.sqrt(sum((s-mu)**2 for s in free)/max(1,len(free))))
    drives=[max(-700.,min(700.,((s-mu)/std+bias)/temperature)) for s in scores]
    return dict(block_scores=scores,drives=drives,forced=forced)


class IntegratedRandomService:
    kind='integrated_issue95_q256_same_clock'

    def __init__(self, cfg, scheduler, ledger, period, *, ffn, mode, group,
                 context, candidates, seed):
        self.cfg,self.s,self.e,self.period=cfg,scheduler,ledger,period
        if abs(1e9/cfg['clock_hz']-period)>1e-9:
            raise ValueError('source and core clocks must be identical')
        if mode=='screen_serial_ising':
            raise ValueError('historical serial oracle is not an integrated-source mode')
        endpoints={}
        cls=FastEndpoint if cfg.get('cpu_fast',True) else Endpoint
        reseed=cfg['reseed_cycles']
        if ffn=='sc':endpoints['ffn']=cls('lfsr32',reseed)
        self.biased_capacity=max(group*math.ceil(context/64) if mode.startswith('screen_') else 0,
                                 candidates if mode in ('screen_winner','screen_rejection') else 0)
        self.biased_names=['biased_%03d'%i for i in range(math.ceil(self.biased_capacity/20))]
        endpoints.update((n,cls('bivium',reseed)) for n in self.biased_names)
        if mode in ('pv','screen_pv','screen_winner','screen_rejection'):
            endpoints['fair']=cls('bivium',reseed)
        self.endpoints=endpoints
        source=SeedWords('fixture',cfg['seed_word_interval_cycles'],cfg['seed_startup_cycles'],
            fixture_seed=seed,provenance='explicit deterministic TLM seed fixture; not physical entropy')
        self.network=EventNetwork(endpoints,source,clock_ns=period) if endpoints else None
        self.ffn_port=RandomPort(self.network,'ffn') if 'ffn' in endpoints else None
        self.fair_port=RandomPort(self.network,'fair') if 'fair' in endpoints else None
        self.lut=SigmoidTable(cfg['sigmoid_step'])
        self.previous=None;self.ffn_frame=None
        self.counts=Counter();self.max_parallel=Counter();self.requests=Counter()
        self.frame_hash=hashlib.sha256()
        self.ppa=json.loads((Path(__file__).parent/'configs/rng_ppa100.json').read_text(encoding='utf-8'))

    @property
    def now(self):return self.network.cycle*self.period if self.network else 0.

    def advance_to(self, ready_ns):
        if ready_ns<0 or not math.isfinite(ready_ns):raise ValueError('finite source request time')
        if self.network:
            target=max(self.network.cycle,math.ceil(ready_ns/self.period-1e-10))
            self.network.advance_to(target)

    def reserve_control(self, name, ready, done):
        start=math.ceil(ready/self.period-1e-10)*self.period
        if done < start:raise AssertionError('source completed in the past')
        return self.s.reserve(name,ready,done-start,('rng_control',),self.period)

    def prepare_ffn(self,ready,frame,replay):
        self.advance_to(ready)
        if replay:
            if frame!=self.ffn_frame:raise ValueError('replay must retain the same input group')
            self.ffn_port.command(2);self.counts['ffn_restores']+=1
        else:
            if self.ffn_frame is not None:raise ValueError('previous checkpoint not released')
            self.ffn_port.command(1);self.ffn_frame=frame;self.counts['ffn_saves']+=1
        return self.reserve_control('rng_ffn_restore' if replay else 'rng_ffn_save',ready,self.now)

    def stream_ffn(self,ready,samples,strata,ii):
        if self.ffn_frame is None:raise ValueError('save before stream')
        self.advance_to(ready);width=256//strata;first=self.network.cycle
        for i in range(samples):
            self.advance_to((first+i*ii)*self.period)
            response=self.ffn_port.frame()
            threshold=(i//(samples//strata))*width+(response['words'][0]&(width-1))
            self.frame_hash.update(bytes([threshold]))
        # Consume the last registered word; stream/counter timing overlaps.
        self.network.tick()
        self.counts['ffn_streams']+=1;self.counts['ffn_samples_consumed']+=samples
        self.counts['ffn_threshold_bits_used']+=samples*int(math.log2(width))
        self.counts['ffn_shared64_comparisons']+=64*samples
        self.counts['stratum_counter_updates']+=samples
        return self.now

    def release_ffn(self,ready):
        self.advance_to(ready);self.ffn_port.command(3);self.ffn_frame=None
        self.counts['ffn_releases']+=1
        return self.reserve_control('rng_ffn_release',ready,self.now)

    def draw_q_at(self,ready,q,identity,lookup_count=0):
        self.advance_to(ready)
        if not 1<=len(q)<=self.biased_capacity:raise ValueError('biased response exceeds physical capacity')
        key=(identity,tuple(q))
        if key!=self.previous:
            self.counts['sigmoid_lut_lookups']+=lookup_count
            self.counts['threshold_bits_programmed']+=9*len(q)
            cycles=math.ceil(lookup_count/self.cfg['lut_lanes'])+math.ceil(len(q)/self.cfg['config_lanes'])
            self.network.advance_to(self.network.cycle+cycles)
            self.previous=key
        names=self.biased_names[:math.ceil(len(q)/20)]
        response=FullFrameArray(self.network,names,len(q)).draw_q(q)
        self.counts['biased_frames']+=1;self.counts['biased_bits_delivered']+=len(q)
        self.counts['unused_biased_native_lanes']+=20*len(names)-len(q)
        self.counts['zero_probability_lanes']+=sum(x==0 for x in q)
        self.max_parallel['biased']=max(self.max_parallel['biased'],len(q))
        self.frame_hash.update(bytes(response['bits']))
        return response['bits'],self.now

    def draw_at(self,ready,drives):
        if not drives:self.advance_to(ready);return [],self.now
        q=self.lut.lookup(drives)
        return self.draw_q_at(ready,q,('sampler',tuple(drives)),len(drives))

    def fair_at(self,ready,width):
        self.advance_to(ready)
        if not 0<=width<=160:raise ValueError('fair native width exceeded')
        if width==0:return 0,self.now
        response=self.fair_port.frame()
        value=sum(w<<(8*i) for i,w in enumerate(response['words'])) & ((1<<width)-1)
        self.counts['fair_calls']+=1;self.counts['fair_bits_delivered']+=width
        self.counts['unused_fair_native_bits']+=160-width
        self.max_parallel['fair']=max(self.max_parallel['fair'],width)
        self.frame_hash.update(value.to_bytes((width+7)//8,'little'))
        return value,self.now

    def selector(self,ready,groups):
        q=[]
        for info in groups:
            values=self.lut.lookup(info['drives'])
            q.extend(256 if i in info['forced'] else x for i,x in enumerate(values))
        bits,done=self.draw_q_at(ready,q,('selector',tuple(q)),len(q))
        self.counts['selector_calls']+=1
        return bits,self.reserve_control('rng_selector_real_response',ready,done)

    def systematic(self,ready):
        value,done=self.fair_at(ready,32)
        self.counts['pv_systematic_offsets']+=1
        return value/2**32,self.reserve_control('rng_PV_real_uniform32',ready,done)

    def report(self, end_ns=None):
        if end_ns is not None:self.advance_to(end_ns)
        energy=area=0.;profiles=[]
        if self.network:
            for name,p in self.network.ports.items():
                key='lfsr' if p.kind=='lfsr32' else 'bivium'
                cost=self.ppa['profiles'][key]
                active=p.counts['prng_updates']+p.counts['warmup_updates']
                clocks=p.counts['clock_edges'];idle=clocks-active
                # Full endpoint cost: its native compare/state/control are not
                # priced again. Seed/global bus/frontends remain unpriced.
                # Fixed reference energy/edge avoids reducing action cost when frequency rises.
                # No leakage split exists here: treating all measured power as edge-dependent
                # is a conservative high-frequency proxy, not a new 500MHz PT result.
                cost_period=1e9/self.cfg.get('energy_reference_hz',1e9/self.period)
                joules=(active*cost['stream_uW']+idle*cost['idle_uW'])*cost_period*1e-15
                energy+=joules;area+=cost['area_um2']*1e-6
                profiles.append(dict(port=name,kind=p.kind,active_cycles=active,idle_cycles=idle,
                    conditional_energy_J=joules,area_mm2=cost['area_um2']*1e-6))
        return dict(backend=self.kind,clock_ns=self.period,clock_hz=1e9/self.period,
            random_stream_SRAM_bytes=0,extra_probability_copy_bytes=0,extra_random_FIFO_bytes=0,
            actual_backend_executed=True,source_counts=dict(self.counts),max_parallel_lanes=dict(self.max_parallel),
            frame_output_sha256=self.frame_hash.hexdigest(),
            network=self.network.report() if self.network else None,
            simulated_idle_edges_jumped=self.network.jumped_edges if self.network else 0,
            calibrated_endpoint_two_state_energy_J=energy,calibrated_endpoint_area_mm2=area,
            endpoint_costs=profiles,ppa_provenance=self.ppa['provenance'],
            energy_reference_hz=self.cfg.get('energy_reference_hz',1e9/self.period),
            high_frequency_energy_policy='fixed reference energy per edge; unsplit leakage conservatively scales with clock',
            full_random_energy_J=None,full_random_area_mm2=None,
            limitations=['native Issue95 ports persist across all layers/queries; original protocol unchanged',
                '8-bit q/256 sigmoid table alters numerical response; no inherited model PPL',
                'endpoint stream/idle interpolation is conditional, not new PT or per-action calibration',
                'FFN64 frontend/stratum logic, LUT/threshold programming, global seed arbiter/material and wires unpriced',
                'fixture seed material is reproducible simulation input, not certified physical entropy',
                'FFN timing consumes actual source words but matrix/activation tensors are still macro TLM, not inference'])

    def finish(self,end_ns):
        r=self.report(end_ns)
        self.e.action('rng_calibrated_endpoint_energy_pJ',r['calibrated_endpoint_two_state_energy_J']*1e12,'RNG_endpoint_calibrated',1.)
        self.e.action('rng_FFN_shared64_compare',self.counts['ffn_shared64_comparisons'],'RNG_frontend')
        self.e.action('rng_stratum_counter_update',self.counts['stratum_counter_updates'],'RNG_frontend')
        self.e.action('rng_sigmoid_lut_lookup',self.counts['sigmoid_lut_lookups'],'RNG_frontend')
        self.e.action('rng_threshold_config_bit',self.counts['threshold_bits_programmed'],'RNG_frontend')
        beats=sum(g.counts['bus_beats'] for g in self.network.ingress.values()) if self.network else 0
        self.e.action('rng_seed_bus_beat',beats,'RNG_seed_global')
        return r
