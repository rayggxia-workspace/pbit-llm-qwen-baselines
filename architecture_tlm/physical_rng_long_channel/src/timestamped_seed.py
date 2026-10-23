"""Source adapter for RandomNetwork: actual simulation completion times, no fallback."""
import json
import math
from pathlib import Path


class TimestampedSeedWords:
    def __init__(self,path,clock_ns=10,allow_flagged_diagnostic=False):
        self.path=Path(path);data=json.loads(self.path.read_text(encoding='utf-8'))
        if data.get('format')!='timestamped_simulation_seed_words_v1':raise ValueError('Unknown seed trace format')
        if data.get('physical_entropy_certified') is not False:raise ValueError('This adapter accepts explicitly labelled simulation traces only')
        if clock_ns<=0:raise ValueError('Positive clock required')
        self.clock_s=clock_ns*1e-9;self.words=data['words'];self.position=0;self.last_cycle=-1
        self.allow_flagged=allow_flagged_diagnostic;self.transcript=[]
        self.provenance=data['provenance']+'; timestamp-aware Spectre simulation trace, NOT physical entropy certification'
        previous=-1.
        for w in self.words:
            t=w['available_s']
            if not math.isfinite(t) or t<previous or type(w['word']) is not int or not 0<=w['word']<1<<32:raise ValueError('Invalid seed word/time')
            previous=t

    def read(self,cycle):
        if not isinstance(cycle,int) or cycle<self.last_cycle:raise ValueError('Clock must advance monotonically')
        self.last_cycle=cycle
        if self.position>=len(self.words):raise EOFError('Trace exhausted; no looping/reseed/OS fallback')
        w=self.words[self.position]
        if cycle*self.clock_s+1e-15<w['available_s']:return None
        if not w['level_valid'] and not self.allow_flagged:
            raise ValueError('Seed word includes invalid readout level; cannot silently discard or qualify')
        self.position+=1
        self.transcript.append(dict(cycle=cycle,word=w['word'],available_s=w['available_s'],
                                    level_valid=w['level_valid'],simulation_only=True))
        return w['word']
