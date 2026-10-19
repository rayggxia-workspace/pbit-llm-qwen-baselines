"""Audit the source-backed 16 GiB scenario; optionally probe a real SG bridge.

This checks geometry/current inputs and command completion, not DRAM data
integrity, JEDEC DIMM timing signoff, measured power, or calibrated PHY energy.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
UPSTREAM = {
    'DRAMSys': '5.6.0',
    'DRAMSys_commit': '9f15aaf1fe6f05ff16a2e521a20a96f3bfe29d52',
    'DRAMPower': '6.3.1',
    'DRAMUtils': '1.16.0',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(path):
    doc = json.loads(path.read_text(encoding='utf-8-sig'))
    sim = doc['simulation']
    spec = sim['memspec']
    arch = spec['memarchitecturespec']
    power = spec['mempowerspec']
    profile = json.loads((ROOT/'micron4gb_reva_1866_limits.json').read_text(encoding='utf-8-sig'))
    assert spec['memoryType'] == 'DDR4'
    assert arch['nbrOfRanks'] == 2 and arch['nbrOfChannels'] == 2
    assert arch['nbrOfDevices'] == 8 and arch['width'] == 8
    assert arch['RefMode'] == 1
    per_die = arch['nbrOfBanks']*arch['nbrOfRows']*arch['nbrOfColumns']*arch['width']//8
    capacity = per_die*arch['nbrOfDevices']*arch['nbrOfRanks']*arch['nbrOfChannels']
    assert per_die == 512*2**20 and capacity == 16*2**30
    for key, value in {**profile['current_limits_A'], **profile['voltages_V']}.items():
        assert math.isclose(power[key], value, rel_tol=0, abs_tol=1e-12), key
    assert 'iBeta_vdd' not in power and 'iBeta_vpp' not in power
    mapping = sim['addressmapping']
    expected = dict(BYTE_BIT=list(range(3)), COLUMN_BIT=[3,4,5,11,12,13,14,15,16,17],
                    CHANNEL_BIT=[6], BANK_BIT=[7,8], BANKGROUP_BIT=[9,10],
                    ROW_BIT=list(range(18,33)), RANK_BIT=[33])
    assert mapping == expected, 'Unexpected aliases or unmapped address bits'
    bits = [bit for field in mapping.values() for bit in field]
    assert sorted(bits) == list(range(34)) and len(bits) == len(set(bits))
    watts = {name: arch['nbrOfDevices']*(power['vdd']*power['idd'+suffix]+
        power['vpp']*power['ipp'+suffix]) for name, suffix in
        [('pre_standby','2n'),('active_standby','3n'),('pre_powerdown','2p'),
         ('active_powerdown','3p'),('self_refresh','6n')]}
    assert watts['pre_powerdown'] < watts['pre_standby']
    assert watts['active_powerdown'] < watts['active_standby']
    # Full same-state population is FOUR rank-channel instances, not two.
    total_state = {key: value*arch['nbrOfRanks']*arch['nbrOfChannels'] for key,value in watts.items()}
    return dict(file=path.name, sha256=sha(path), capacity_bytes=capacity,
                per_die_bytes=per_die, ranks_per_channel=2, channels=2,
                power_down_policy=sim['mcconfig']['PowerDownPolicy'],
                core_profile=profile['profile_id'], current_source=profile['source'],
                state_W_per_rank_channel=watts, all_ranks_same_state_W=total_state,
                mapping_bits=34, single_die_current_source_verified=True,
                complete_dram_energy_calibrated=False, io_phy_calibrated=False,
                rank_topology_timing_validated=False)


def probe(bridge, config, output):
    """Read/write transactions hit BOTH ranks and channels; no payload model."""
    output.mkdir(parents=True, exist_ok=True)
    log_path = output/(config.stem+'.bridge.log')
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(bridge.resolve()), str(config.resolve()), '32'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True)
        banners = []
        def read():
            while True:
                line = process.stdout.readline()
                if not line:
                    raise RuntimeError('Bridge exited; inspect '+str(log_path))
                if line.lstrip().startswith('{'):
                    return json.loads(line)
                banners.append(line.rstrip())
        requests = []
        try:
            hello = read()
            assert hello['status'] == 'ready' and hello['memory_bytes'] == 16*2**30
            assert 'scatter_gather_v1' in hello['features']
            now = 0.
            # Top rank bit and low channel bit are deliberately exercised.
            for write in (True, False):
                for rank in range(2):
                    for channel in range(2):
                        request = dict(op='access', id=len(requests)+1, ready_ns=now,
                            address=(rank<<33)+(channel<<6), bytes=64, write=write)
                        process.stdin.write(json.dumps(request)+'\n'); process.stdin.flush()
                        response = read()
                        assert response['id'] == request['id'] and response['done_ns'] >= now
                        requests.append(dict(request=request, response=response))
                        now = response['done_ns']
            # Exercise the sparse descriptor protocol as well as ordinary DMA.
            request = dict(op='access_sg', id=len(requests)+1, ready_ns=now,
                ranges=[dict(address=(r<<33)+(c<<6)+4096,bytes=64)
                        for r in range(2) for c in range(2)], write=False)
            process.stdin.write(json.dumps(request)+'\n'); process.stdin.flush()
            response = read()
            assert response['id'] == request['id'] and response['done_ns'] >= now
            requests.append(dict(request=request,response=response)); now = response['done_ns']
            process.stdin.write(json.dumps(dict(op='finish',end_ns=now+100000.))+'\n')
            process.stdin.flush(); final = read()
            assert final['status'] == 'finished' and process.wait(timeout=30) == 0
            channels = final['power_at_system_end']
            assert len(channels) == 2
            for value in channels.values():
                assert len(value['rank_stats']) == 2 and len(value['bank_stats']) == 32
                # DRAMPower exports RD/WR in per-bank command counters; its
                # rank_total entries carry state cycles, not summed commands.
                for rank in range(2):
                    banks = value['bank_stats'][rank*16:(rank+1)*16]
                    assert sum(bank['commands']['RD'] for bank in banks) > 0
                    assert sum(bank['commands']['WR'] for bank in banks) > 0
                assert abs(value['core_component_residual_J']) < 1e-12
            result = dict(status='PASS', scenario=config.name, bridge_sha256=sha(bridge),
                bridge_source_sha256=sha(ROOT/'bridge_sg_v6_audit.cpp'),
                hello=hello, requests=requests, final=final,
                binaries_report_versions=False, expected_upstream_versions=UPSTREAM,
                upstream_version_provenance='Build source/cache separately pinned; handshake alone does not authenticate library versions.',
                scope='timing/address/command-power loop only; memory payloads and data integrity NOT tested')
        finally:
            if process.poll() is None:
                process.terminate(); process.wait(timeout=10)
            process.stdin.close(); process.stdout.close()
    path=output/(config.stem+'.probe.json')
    path.write_bytes((json.dumps(result,indent=2)+'\n').encode('utf-8'))
    return dict(file=path.name,sha256=sha(path),status='PASS',bridge_sha256=sha(bridge))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bridge',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    configs=sorted((ROOT/'configs').glob('ddr4_2ch_2rank_*.json'))
    assert len(configs) == 2
    result=dict(scope='16 GiB source-backed core-current scenario; not measured complete DRAM energy',
        expected_upstream_versions=UPSTREAM, configs=[audit(path) for path in configs],
        source_sha256={name:sha(ROOT/name) for name in
            ['audit_dram.py','micron4gb_reva_1866_limits.json','bridge_sg_v6_audit.cpp','CMakeLists.txt']})
    if args.bridge:
        if args.output is None:
            parser.error('--bridge requires --output (personal project directory)')
        result['live_probes']=[probe(args.bridge,path,args.output) for path in configs]
    if args.output:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'audit.json').write_bytes((json.dumps(result,indent=2)+'\n').encode('utf-8'))
    print(json.dumps(result,indent=2))
