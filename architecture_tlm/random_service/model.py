"""Synchronous cycle model; one registered response, no hidden queues.

tick returns pre-edge handshakes and post-edge state. Every call is ONE edge.
Counters describe functional actions, not gates, toggles, energy, or physical entropy.
"""
from collections import Counter
import hashlib
import random
import secrets
from .backends import PROFILES, generate


class Endpoint:
    def __init__(self, kind='lfsr32', reseed_cycles=100_000_000):
        if kind not in PROFILES or type(reseed_cycles) is not int or not 0 <= reseed_cycles <= 0xffffffff:
            raise ValueError('invalid backend/reseed interval')
        self.kind, self.profile = kind, PROFILES[kind]
        self.reseed_cycles = reseed_cycles
        self.counts = Counter()
        self.cycle = 0
        self.reset()

    def reset(self):
        self.state = self.saved = 0
        self.seeded = self.locked = self.valid = False
        self.age = self.warm = 0
        self.words = (0,) * self.profile['lanes']
        self.bits = (False,) * self.profile['lanes']
        self.epoch = 0
        self.error = False

    @property
    def due(self):
        return not self.seeded or bool(self.reseed_cycles and self.age >= self.reseed_cycles)

    def signals(self, rsp_ready=True, seed_valid=False, command=0):
        empty = not self.valid
        seed_req = self.due and not self.locked and self.warm == 0
        seed_ready = seed_req and empty
        cmd_ok = ((command == 1 and not self.locked and not self.due) or
                  (command in (2, 3) and self.locked))
        cmd_ready = bool(self.seeded and not self.warm and empty and not seed_valid and cmd_ok)
        req_ready = bool(self.seeded and not self.warm and (not self.due or self.locked)
                         and (empty or rsp_ready) and not seed_valid and command == 0)
        return dict(seed_req=seed_req, seed_ready=seed_ready,
                    req_ready=req_ready, cmd_ready=cmd_ready,
                    rsp_valid=self.valid, words=self.words, bits=self.bits)

    def tick(self, req_valid=False, thresholds=None, rsp_ready=True,
             seed_valid=False, seed_data=0, command=0, reset_n=True):
        q = tuple([128]*self.profile['lanes'] if thresholds is None else thresholds)
        if len(q) != self.profile['lanes'] or any(type(x) is not int or not 0 <= x <= 256 for x in q):
            raise ValueError('one unsigned q/256 threshold (0..256) per lane')
        if command not in (0, 1, 2, 3):
            raise ValueError('command: 0 none, 1 save+lock, 2 restore, 3 release')
        if type(seed_data) is not int or not 0 <= seed_data < (1 << self.profile['state_bits']):
            raise ValueError('seed word does not fit')
        pre = self.signals(rsp_ready, seed_valid, command)
        accepted = bool(reset_n and req_valid and pre['req_ready'])
        consumed = bool(reset_n and self.valid and rsp_ready)
        seeded = bool(reset_n and seed_valid and pre['seed_ready'])
        commanded = bool(reset_n and command and pre['cmd_ready'])
        self.counts['clock_edges'] += 1
        self.error = False
        if not reset_n:
            self.reset()
            self.counts['reset_edges'] += 1
        else:
            if self.seeded and self.age < 0xffffffff:
                self.age += 1
            self.counts['seed_wait_cycles'] += int(pre['seed_req'])
            self.counts['output_stall_cycles'] += int(self.valid and not rsp_ready)
            self.counts['request_stall_cycles'] += int(req_valid and not pre['req_ready'])
            self.counts['reseed_deferred_cycles'] += int(self.due and self.locked)
            if consumed:
                self.valid = False
                self.counts['responses_consumed'] += 1
            if seeded:
                if seed_data == 0:
                    self.error = True
                    self.counts['zero_seeds_rejected'] += 1
                else:
                    self.state, self.seeded = seed_data, True
                    self.age, self.warm = 0, self.profile['warmup']
                    self.epoch = (self.epoch+1) & 0xffffffff
                    self.counts['seed_loads'] += 1
                    self.counts['seed_state_bits_loaded'] += self.profile['state_bits']
            elif self.warm:
                _, self.state = generate(self.kind, self.state)
                self.warm -= 1
                self.counts['warmup_updates'] += 1
                self.counts['recurrence_steps'] += self.profile['steps']
                self.counts['warmup_bits_discarded'] += self.profile['steps']
            elif commanded:
                if command == 1:
                    self.saved, self.locked = self.state, True
                    self.counts['checkpoint_bits_written'] += self.profile['state_bits']
                elif command == 2:
                    self.state = self.saved
                    self.counts['restore_bits_loaded'] += self.profile['state_bits']
                else:
                    self.locked = False
                self.counts['commands'] += 1
            elif accepted:
                self.words, self.state = generate(self.kind, self.state)
                self.bits = tuple(w < t for w, t in zip(self.words, q))
                self.valid = True
                self.counts['frames_generated'] += 1
                self.counts['prng_updates'] += 1
                self.counts['recurrence_steps'] += self.profile['steps']
                self.counts['random_word_bits_generated'] += self.profile['lanes']*8
                self.counts['threshold_comparisons'] += self.profile['lanes']
                self.counts['output_register_bits_written'] += self.profile['lanes']*9
                self.counts['shared_mapping_evaluations'] += int(self.kind == 'lfsr32_shared64')
        out = dict(cycle=self.cycle, pre=pre, accepted=accepted, consumed=consumed,
                   seed_accepted=seeded, command_accepted=commanded,
                   valid=self.valid, words=self.words, bits=self.bits, state=self.state,
                   epoch=self.epoch, warm=self.warm, age=self.age, locked=self.locked,
                   seed_error=self.error)
        self.cycle += 1
        return out

    def report(self):
        return dict(kind=self.kind, profile=self.profile, cycles=self.cycle,
                    counts=dict(self.counts), energy_J=None, area_mm2=None,
                    status='operation counts only; calibrate with delivered RTL')


class SeedIngress:
    """Qualified synchronous 32-bit seed bus -> full seed packet. No conditioner.

    The producer must assert qualified only for its approved seed-material path.
    This bit is a contract, NOT evidence of entropy. A bad word latches fault.
    """
    def __init__(self, state_bits):
        if state_bits not in (32, 177):
            raise ValueError('unsupported packet size')
        self.width, self.beats = state_bits, (state_bits+31)//32
        self.reset()
        self.counts = Counter()

    def reset(self):
        self.packet = self.count = 0
        self.valid = self.fault = False

    def ready(self, request):
        return bool(request and not self.valid and not self.fault)

    def tick(self, request, seed_ready, word_valid=False, word=0, qualified=True, reset_n=True):
        if type(word) is not int or not 0 <= word < (1 << 32):
            raise ValueError('32-bit seed bus required')
        accepted = bool(reset_n and self.ready(request) and word_valid)
        delivered = bool(reset_n and self.valid and seed_ready)
        if not reset_n:
            self.reset()
        else:
            if delivered:
                self.valid = False
                self.count = 0
                self.packet = 0
                self.counts['packets_delivered'] += 1
            if accepted:
                if not qualified:
                    self.fault = True
                    self.packet = self.count = 0
                    self.counts['qualification_failures'] += 1
                else:
                    self.packet |= word << (32*self.count)
                    self.count += 1
                    self.counts['bus_beats'] += 1
                    self.counts['bus_bits'] += 32
                    if self.count == self.beats:
                        self.packet &= (1 << self.width)-1
                        self.valid = True
                        self.counts['padding_bits_discarded'] += self.beats*32-self.width
        return dict(accepted=accepted, delivered=delivered, valid=self.valid,
                    packet=self.packet, fault=self.fault)


class SeedWords:
    """Explicit seed source with timing and audit transcript. Never invents TRNG proof."""
    def __init__(self, mode='os', interval_cycles=100, startup_cycles=10,
                 fixture_seed=None, words=None, provenance=None):
        if mode not in ('os', 'fixture', 'trace') or interval_cycles < 1 or startup_cycles < 0:
            raise ValueError('seed source mode/timing')
        if mode == 'fixture' and fixture_seed is None:
            raise ValueError('fixture mode requires an explicit seed')
        if mode == 'trace' and (words is None or not provenance):
            raise ValueError('trace requires words and provenance; no silent fallback')
        self.mode, self.interval, self.next_cycle = mode, interval_cycles, startup_cycles
        self.rng = random.Random(fixture_seed) if mode == 'fixture' else None
        self.words = iter(words or [])
        self.provenance = provenance or ('OS CSPRNG; not verified physical entropy' if mode == 'os'
                                        else 'deterministic test fixture; not physical entropy')
        self.transcript = []

    def read(self, cycle):
        if cycle < self.next_cycle:
            return None
        if self.mode == 'trace':
            try:
                value = next(self.words)
            except StopIteration:
                raise RuntimeError('seed trace exhausted; refused deterministic fallback')
        else:
            value = secrets.randbits(32) if self.mode == 'os' else self.rng.getrandbits(32)
        if type(value) is not int or not 0 <= value < 1 << 32:
            raise ValueError('invalid seed trace word')
        self.next_cycle = cycle+self.interval
        self.transcript.append(dict(cycle=cycle, word=value))
        return value


class RandomNetwork:
    """Local ports run concurrently; one shared packet-serial round-robin seed bus.

    A single clock domain. CDC/analog collection/conditioning belong upstream.
    Word availability models the *qualified* source, not raw samples. No expansion:
    every endpoint receives distinct fresh bus material on startup/each epoch.
    """
    def __init__(self, endpoints, source, clock_ns=10):
        if not endpoints or clock_ns <= 0:
            raise ValueError('nonempty endpoints/positive clock required')
        self.ports = dict(endpoints)
        if len({id(e) for e in self.ports.values()}) != len(self.ports):
            raise ValueError('hardware instances must not be aliased under two names')
        self.ingress = {k: SeedIngress(p.profile['state_bits']) for k,p in self.ports.items()}
        self.keys = sorted(self.ports)
        self.source, self.clock_ns, self.cycle = source, clock_ns, 0
        self.target, self.rr = None, 0
        self.seed_events = []

    def tick(self, requests=None, readies=None, commands=None):
        requests, readies, commands = requests or {}, readies or {}, commands or {}
        if (set(requests)|set(readies)|set(commands))-set(self.ports):
            raise KeyError('unknown port')
        pre = {k:p.signals(readies.get(k,True), self.ingress[k].valid, commands.get(k,0))
               for k,p in self.ports.items()}
        if self.target is None:
            for i in range(len(self.keys)):
                k = self.keys[(self.rr+i)%len(self.keys)]
                if self.ingress[k].ready(pre[k]['seed_req']):
                    self.target = k
                    break
        word = None
        if self.target is not None and self.ingress[self.target].ready(pre[self.target]['seed_req']):
            word = self.source.read(self.cycle)
        out = {}
        for k,p in self.ports.items():
            g = self.ingress[k]
            out[k] = p.tick(req_valid=k in requests, thresholds=requests.get(k),
                            rsp_ready=readies.get(k,True), seed_valid=g.valid,
                            seed_data=g.packet, command=commands.get(k,0))
            if out[k]['seed_accepted']:
                self.seed_events.append(dict(cycle=self.cycle, port=k, epoch=p.epoch,
                    seed_hex=hex(g.packet), rejected=out[k]['seed_error'], provenance=self.source.provenance))
            g.tick(pre[k]['seed_req'], pre[k]['seed_ready'],
                   word_valid=k == self.target and word is not None,
                   word=word if k == self.target and word is not None else 0)
        if self.target is not None and self.ingress[self.target].valid:
            self.rr = (self.keys.index(self.target)+1)%len(self.keys)
            self.target = None
        self.cycle += 1
        return out

    def report(self):
        return dict(clock_ns=self.clock_ns, cycles=self.cycle,
                    elapsed_ns=self.cycle*self.clock_ns,
                    ports={k:p.report() for k,p in self.ports.items()},
                    seed_transport={k:dict(g.counts) for k,g in self.ingress.items()},
                    seed_events=self.seed_events, seed_source=self.source.provenance,
                    seed_word_transcript=self.source.transcript,
                    energy_J=None, area_mm2=None)
