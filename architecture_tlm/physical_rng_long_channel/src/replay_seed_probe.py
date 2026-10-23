"""Packet/recurrence smoke with the existing model, NOT elapsed-time/TLM replay.

For a real cycle timeline pass TimestampedSeedWords to RandomNetwork and tick
every control edge. This bounded probe resets before each available seed packet;
its counters must not be used for latency, power or independent-bit-rate claims.
"""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys


def run(service_root,trace,kind,allow_flagged=False):
    root=Path(service_root).resolve();trace=Path(trace).resolve()
    if not (root/'architecture_tlm/random_service/model.py').is_file():raise ValueError('Provide repository/portable package ROOT')
    sys.path.insert(0,str(root))
    module=importlib.import_module('architecture_tlm.random_service.model')
    data=json.loads(trace.read_text(encoding='utf-8'));words=data['words']
    if data.get('physical_entropy_certified') is not False:raise ValueError('Require explicit simulation provenance')
    width=177 if kind=='bivium' else 32;beats=(width+31)//32;records=[]
    for i in range(0,len(words)-beats+1,beats):
        part=words[i:i+beats]
        if not all(w['level_valid'] for w in part) and not allow_flagged:raise ValueError('Invalid readout word; use VN transport or explicit diagnostic-only opt-in')
        state=sum(w['word']<<(32*j) for j,w in enumerate(part))&((1<<width)-1)
        endpoint=module.Endpoint(kind,reseed_cycles=0)
        seeded=endpoint.tick(seed_valid=True,seed_data=state)
        frames=[]
        if state:
            for _ in range(endpoint.profile.get('warmup',5 if kind=='bivium' else 0)):
                if endpoint.warm:endpoint.tick()
            # Use actual native endpoint outputs. No resampling/selecting a seed.
            for _ in range(32):
                while endpoint.warm:endpoint.tick()
                r=endpoint.tick(req_valid=True)
                if not r['accepted']:raise ValueError('Existing model did not accept probe frame')
                frames.append(dict(words=list(r['words']),bits=list(r['bits'])))
        records.append(dict(packet=i//beats,available_s=part[-1]['available_s'],zero_state_rejected=not bool(state),
            generated_frames=len(frames),output_sha256=hashlib.sha256(json.dumps(frames,sort_keys=True).encode()).hexdigest()))
    return dict(status='PACKET_RECURRENCE_PROBE_ONLY',kind=kind,trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest(),
        source_sha256={name:hashlib.sha256((root/'architecture_tlm/random_service'/name).read_bytes()).hexdigest() for name in ['model.py','backends.py']},
        packets=records,simulation_provenance=data['provenance'],physical_entropy_certified=False,
        warning='Packets initialized independently; idle/bus/availability cycles NOT stepped. Not a throughput, quality, reseed timing or PPA result.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--service-root',required=True);p.add_argument('--trace',required=True)
    p.add_argument('--kind',choices=['lfsr32','lfsr32_shared64','bivium'],default='lfsr32')
    p.add_argument('--allow-flagged-diagnostic',action='store_true');p.add_argument('--out',required=True)
    a=p.parse_args();r=run(a.service_root,a.trace,a.kind,a.allow_flagged_diagnostic)
    with Path(a.out).open('x',encoding='utf-8',newline='\n') as f:json.dump(r,f,indent=2,ensure_ascii=False);f.write('\n')
    return 0

if __name__=='__main__':sys.exit(main())
