"""Post-run audit; reads frozen outputs and writes a separate diagnostic summary."""
import argparse
import json
from pathlib import Path
import numpy as np
from .ideal_readout import digest, dump


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    result = json.loads((a.directory/'RESULTS.json').read_text(encoding='utf8'))
    config = json.loads((a.directory/'CONFIG.json').read_text(encoding='utf8'))
    n = config['frames_per_boot_endpoint']
    checks = 0
    def require(ok, label):
        nonlocal checks
        if not ok: raise AssertionError(label)
        checks += 1
    require(digest(a.directory/'CONFIG.json') == result['config_sha256'], 'config binding')
    manifest = json.loads((a.directory/'SOURCE_MANIFEST.json').read_text(encoding='utf8'))
    for name, sha in manifest.items():require(digest(root/name) == sha, name)
    compact = []
    for r in result['cases']:
        p = Path(r['artifact']['path'])
        require(digest(p) == r['artifact']['sha256'] and p.stat().st_size == r['artifact']['bytes'], str(p))
        require(r['status'] == 'complete', r['case_id'])
        with np.load(p) as z:
            x, y, cycles = z['a'], z['b'], z['accepted_cycles']
            require(x.shape == y.shape and x.shape[0] == n, 'paired output count')
            require(np.all(np.diff(cycles) == 1), 'one frame/edge within boot')
            require(abs((x[:,0]<128).mean()-r['output']['first_lane']['p1']) < 1e-15, 'p1')
            actual_and = float(np.mean((x[:,0]<64)&(y[:,0]<192)))
            require(actual_and == r['probes']['and_measured'], 'and probe')
            if r['source'] == 'duplicate':require(np.array_equal(x,y), 'same seed control')
            transcript = r['network']['seed_word_transcript']
            if r['source'] != 'duplicate':
                bits, idx = z['conditioned_bits'], z['raw_indices']
                consumed = 32*len(transcript)
                for i, t in enumerate(transcript):
                    selected = idx[32*i:32*(i+1)]
                    require(selected.tolist() == t['raw_indices'], 'seed prefix selection')
                    word = sum(int(b)<<k for k,b in enumerate(bits[32*i:32*(i+1)]))
                    require(word == t['word'], 'transport preserves bits')
                    require(t['available_cycle'] == (int(selected[-1])-r['raw_start_index'])*100+1,
                            'availability retains physical time')
                    require(t['cycle'] == t['available_cycle'], 'online service needs no historical FIFO')
                require(consumed <= len(bits), 'no repeat or padding invented from source')
            events = r['network']['seed_events']
            # All cases in this particular batch have nonzero states; zero rejection has its own unit test.
            require(len(events) == 2 and all(not e['rejected'] for e in events), 'one initial seed per port')
            offset = 0
            for e in events:
                pr = r['network']['ports'][e['port']]['profile']
                c = r['network']['ports'][e['port']]['counts']
                transport = r['network']['seed_transport'][e['port']]
                beats = (pr['state_bits']+31)//32
                packet = sum(t['word'] << (32*i) for i,t in enumerate(transcript[offset:offset+beats]))
                packet &= (1 << pr['state_bits'])-1
                require(int(e['seed_hex'],16) == packet, 'state packet reconstruction')
                require(e['cycle'] == transcript[offset+beats-1]['cycle']+1, 'registered seed delivery')
                require(c['seed_loads'] == 1 and c['frames_generated'] == c['responses_consumed'] == n,
                        'seed/frame/response accounting')
                require(c['recurrence_steps'] == (n+pr['warmup'])*pr['steps'], 'warmup and recurrence accounting')
                require(transport['bus_bits'] == beats*32 and transport['padding_bits_discarded'] == (-pr['state_bits'])%32,
                        'seed padding accounting')
                offset += beats
            if r['backend'] == 'lfsr32_shared64':
                require(not np.logical_xor.reduce(x[:,:4]<128,axis=1).any(), 'GF joint dependency')
            if r['source'] != 'duplicate':
                require(cycles[0] == events[-1]['cycle']+pr['warmup']+1, 'paired startup latency')
            compact.append(dict(case_id=r['case_id'], source=r['source'], seed=r['seed'], mode=r['mode'],
                backend=r['backend'], boot=r['boot'], artifact=r['artifact'], status=r['status'],
                first_output_us=float(cycles[0]/100), elapsed_us=r['cycles']/100,
                output=dict(first_lane=dict(n=n,p1=r['output']['first_lane']['p1'],
                    rho={'1':r['output']['first_lane']['rho']['1']},
                    windows={'128':r['output']['first_lane']['windows']['128']}),
                    tested_pairs=r['output']['tested_pairs'],max_abs_same_cycle_lane_rho=r['output']['max_abs_same_cycle_lane_rho'],
                    worst_lane_cdf_error=r['output']['worst_lane_cdf_error']),
                probes=r['probes'], joint=r['joint'], sparse_proposal=r['sparse_proposal'],
                bus_bits=sum(t['bus_bits'] for t in r['network']['seed_transport'].values()),
                loaded_seed_diagnostics=[dict(port=s['port'],cycle=s['cycle'],state_bits=s['state_bits'],bus_bits=s['bus_bits'],
                    padding_bits_discarded=s['padding_bits_discarded'],p1=s['metrics']['p1'],rho1=s['metrics']['rho']['1'])
                    for s in r['loaded_seed_diagnostics']]))
    require(len(compact) == 225, 'case matrix')
    dump(a.directory/'SUMMARY.json', dict(cases=compact, note='Per-boot metrics only; do not concatenate across resets.'))
    dump(a.directory/'AUDIT.json', dict(status='PASS', checks=checks, cases=len(compact),
        source_files=len(manifest), raw_artifacts=len(compact),
        execution_commit='bdbab3e38ff56e267783af9ac327dbba67a0e169',
        raw_results_sha256=digest(a.directory/'RESULTS.json'), summary_sha256=digest(a.directory/'SUMMARY.json'),
        scope='hashes, finite source, timings, bits, packet truncation, frame counts, arithmetic probes and GF dependency; not entropy certification'))
    print(json.dumps(dict(checks=checks, cases=len(compact), status='PASS')))


if __name__ == '__main__': main()
