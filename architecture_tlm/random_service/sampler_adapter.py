"""Opt-in timed source for parallel_sampler_v5; old ideal source stays unchanged."""
import math
from collections import Counter
from .service import FullFrameArray, RandomPort, SigmoidTable


class TimedSamplerSource:
    kind='timed_local_prng_q256; not ideal IID sigmoid'

    def __init__(self, network, biased_ports, fair_port, capacity=512,
                 lut_lanes=64, config_lanes=64):
        if fair_port in biased_ports:
            raise ValueError('fair and biased services require separate stream resources')
        if lut_lanes < 1 or config_lanes < 1:
            raise ValueError('positive LUT/config throughput')
        self.network=network
        self.array=FullFrameArray(network,biased_ports,capacity)
        self.fair_port=RandomPort(network,fair_port)
        self.lut=SigmoidTable()
        self.lut_lanes,self.config_lanes=lut_lanes,config_lanes
        self.previous=None
        self.counts=Counter()

    def advance_to(self, ready_ns):
        if not math.isfinite(ready_ns) or ready_ns<0:
            raise ValueError('finite nonnegative source request time')
        target=math.ceil(ready_ns/self.network.clock_ns)
        # Sequential consumers can arrive before the source is free: explicit queue delay.
        while self.network.cycle<target:self.network.tick()

    def draw_at(self, ready_ns, drives):
        self.advance_to(ready_ns)
        if not drives:
            return [],self.network.cycle*self.network.clock_ns
        d=tuple(drives)
        if d!=self.previous:
            q=self.lut.lookup(d)
            self.counts['sigmoid_lut_lookups']+=len(d)
            self.counts['threshold_bits_programmed']+=9*len(d)
            # Explicit architecture parameters; LUT/threshold memory RTL is not delivered.
            for _ in range(math.ceil(len(d)/self.lut_lanes)+math.ceil(len(d)/self.config_lanes)):
                self.network.tick()
            self.previous=d;self.q=q
        result=self.array.draw_q(self.q)
        return result['bits'],result['valid_cycle']*self.network.clock_ns

    def fair_at(self, ready_ns, width):
        if not 0<=width<=self.fair_port.endpoint.profile['lanes']*8:
            raise ValueError('fair width exceeds native output; no silent splitting')
        self.advance_to(ready_ns)
        if width==0:return 0,self.network.cycle*self.network.clock_ns
        r=self.fair_port.frame()
        value=sum(w<<(8*i) for i,w in enumerate(r['words'])) & ((1<<width)-1)
        self.counts['fair_bits_delivered']+=width
        self.counts['fair_bits_unused']+=len(r['words'])*8-width
        return value,r['valid_cycle']*self.network.clock_ns

    def report(self):
        return dict(network=self.network.report(),conversion_actions=dict(self.counts),
                    lut_sha256=self.lut.sha256,
                    boundary='source ledger cumulative; do not add cumulative snapshots per query',
                    note='protocol RTL checked; LUT timing configured, all PPA uncharacterized')
