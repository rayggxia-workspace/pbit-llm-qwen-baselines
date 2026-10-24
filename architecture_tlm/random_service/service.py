"""Blocking adapters for existing functional/TLM consumers; all time uses network edges.

Use network.tick({...}) to issue concurrent consumers. Sequential Python adapter calls
are deliberately serialized and must NOT be interpreted as concurrent hardware.
"""
import hashlib
import json
import math
from collections import Counter


class SigmoidTable:
    """Explicit Q/256 response LUT. Index is integer drive code, d=code*step.

    This is a quantized response, not ideal sigmoid; LUT implementation/latency is
    outside rng_endpoint. No existing PPL result is inherited by this approximation.
    """
    def __init__(self, step=0.125, minimum=-255, maximum=255):
        if step <= 0 or not math.isfinite(step) or minimum > maximum:
            raise ValueError('LUT bounds')
        self.step, self.minimum, self.maximum = step, minimum, maximum
        self.values = {}
        for i in range(minimum, maximum+1):
            x = i*step
            p = 1/(1+math.exp(-x)) if x >= 0 else math.exp(x)/(1+math.exp(x))
            self.values[i] = int(math.floor(256*p+0.5))
        self.sha256 = hashlib.sha256(json.dumps(self.values,sort_keys=True).encode()).hexdigest()

    def lookup(self, drives):
        if any(not math.isfinite(d) for d in drives):
            raise ValueError('finite log odds required')
        codes = [max(self.minimum,min(self.maximum,math.floor(d/self.step+0.5))) for d in drives]
        return [self.values[c] for c in codes]


class RandomPort:
    def __init__(self, network, name):
        self.network, self.name = network, name
        self.endpoint = network.ports[name]
        self.counts = Counter()

    def frame(self, thresholds=None, timeout_cycles=1_000_000):
        start = self.network.cycle
        for _ in range(timeout_cycles):
            r = self.network.tick({self.name:thresholds})[self.name]
            if r['accepted']:
                self.counts['calls'] += 1
                return dict(words=r['words'], bits=r['bits'], epoch=r['epoch'],
                    request_cycle=start, valid_cycle=self.network.cycle,
                    wait_cycles=r['cycle']-start, latency_cycles=1)
        raise TimeoutError('random service unavailable; no fallback seed/data')

    def command(self, command, timeout_cycles=1_000_000):
        for _ in range(timeout_cycles):
            r = self.network.tick(commands={self.name:command})[self.name]
            if r['command_accepted']:
                return self.network.cycle
        raise TimeoutError('command cannot reach safe boundary')

    def shared_input(self, thresholds):
        """One random word -> 64 comparisons. Legal ONLY for declared FFN policy."""
        if len(thresholds)!=64 or any(type(q) is not int or not 0 <= q <= 256 for q in thresholds):
            raise ValueError('64 q/256 thresholds')
        if self.endpoint.kind != 'lfsr32':
            raise ValueError('shared-input adapter uses the single-word profile')
        r = self.frame()
        self.counts['frontend_comparisons'] += 64
        self.counts['word_bit_sinks'] += 8*64
        r['bits'] = tuple(r['words'][0] < q for q in thresholds)
        return r

    def uniform_below(self, bound, max_attempts=1024):
        if type(bound) is not int or not 1 <= bound <= 256:
            raise ValueError('initial API supports bounds 1..256')
        if bound == 1:
            return 0
        limit = 256-256%bound
        for _ in range(max_attempts):
            x = self.frame()['words'][0]
            self.counts['range_comparisons'] += 1
            if x < limit:
                self.counts['range_modulo_ops'] += 1
                return x % bound
            self.counts['range_rejections'] += 1
        raise RuntimeError('range rejection limit; consumed work remains charged')


class FullFrameArray:
    """Dedicated native-width ports -> atomic full candidate frame.

    No IID claim. Reject shared-GF lanes by default: pairwise rank is insufficient
    for the all-candidate joint law. Unused native lanes are still generated/counted.
    """
    def __init__(self, network, names, candidate_capacity, allow_correlated=False):
        if len(set(names))!=len(names) or not names or candidate_capacity < 1:
            raise ValueError('unique nonempty dedicated ports and positive capacity')
        self.network, self.names, self.capacity = network, list(names), candidate_capacity
        self.lanes = [network.ports[n].profile['lanes'] for n in names]
        if sum(self.lanes) < candidate_capacity:
            raise ValueError('insufficient full-frame width; no silent time multiplexing')
        if not allow_correlated and any(network.ports[n].kind=='lfsr32_shared64' for n in names):
            raise ValueError('shared GF backend needs explicit correlated-experiment opt-in')
        self.counts = Counter()

    def draw_q(self, q, timeout_cycles=1_000_000):
        if not 1<=len(q)<=self.capacity or any(type(x) is not int or not 0<=x<=256 for x in q):
            raise ValueError('invalid q/256 vector')
        start = self.network.cycle
        for _ in range(timeout_cycles):
            # A pending seed packet gets priority; no partial frame acceptance.
            ready = all(self.network.ports[n].signals(True,self.network.ingress[n].valid)['req_ready']
                        for n in self.names)
            if not ready:
                self.network.tick()
                continue
            padded = list(q)+[0]*(sum(self.lanes)-len(q))
            req, offset = {}, 0
            for name, width in zip(self.names,self.lanes):
                req[name] = padded[offset:offset+width]
                offset += width
            result = self.network.tick(req)
            if not all(result[n]['accepted'] for n in self.names):
                raise AssertionError('atomic frame schedule mismatch')
            bits = [b for n in self.names for b in result[n]['bits']]
            self.counts['frames'] += 1
            self.counts['unused_native_lanes'] += len(bits)-len(q)
            return dict(bits=bits[:len(q)], request_cycle=start, valid_cycle=self.network.cycle,
                        service_cycles=self.network.cycle-start)
        raise TimeoutError('full-width source not ready')

