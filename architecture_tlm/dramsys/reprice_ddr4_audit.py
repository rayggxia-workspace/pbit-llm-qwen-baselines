"""Reprice exported DDR4 command/state statistics with DRAMPower 6.3.1 equations.

This is a diagnostic cross-check, not a replacement simulator. Timing is held
fixed. Input must contain bridge_sg_v6_audit.cpp's per-channel bank_stats and
rank_stats. The original public DRAMSys example current coefficients are not
assumed to be physically calibrated. --zero-vpp-pd is only a sensitivity case.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def reprice(channel, memspec, zero_vpp_pd=False):
    a, t, p = (memspec[k] for k in
               ('memarchitecturespec', 'memtimingspec', 'mempowerspec'))
    B, D = a['nbrOfBanks'], a['nbrOfDevices']
    ck, ras, rp = t['tCK'], t['RAS']*t['tCK'], t['RP']*t['tCK']
    rf = {1: ('idd5B', 'ipp5B', 'RFC1'),
          2: ('idd5F2', 'ipp5F2', 'RFC2'),
          4: ('idd5F4', 'ipp5F4', 'RFC4')}[a.get('RefMode', 1)]
    rho = memspec.get('bankwisespec', {}).get('factRho', 1)
    rails = {}
    for name, prefix, voltage, beta, refresh in (
            ('VDD', 'idd', p['vdd'], p.get('iBeta_vdd', p['idd0']), rf[0]),
            ('VPP', 'ipp', p['vpp'], p.get('iBeta_vpp', p['ipp0']), rf[1])):
        cur = lambda suffix: p[prefix+suffix]
        i0, i2n, i3n = cur('0'), cur('2n'), cur('3n')
        i2p, i3p = cur('2p'), cur('3p')
        if zero_vpp_pd and name == 'VPP':
            i2p = i3p = 0
        irho = rho*(i3n-i2n)+i2n
        itheta = (i0*(rp+ras)-beta*rp)/ras
        i1 = (i3n+(B-1)*irho)/B
        e = defaultdict(float)
        for bank in channel['bank_stats']:
            c, n = bank['cycles'], bank['commands']
            e['ACT'] += voltage*(itheta-i1)*ras*n['ACT']*D
            e['PRE'] += voltage*(beta-i2n)*rp*n['PRE']*D
            e['BG_ACT_BANK'] += voltage*(i1-irho)*c['act']*ck*D
            for command, current in (('RD', cur('4r')), ('WR', cur('4w')),
                                     ('RDA', cur('4r')), ('WRA', cur('4w'))):
                e[command] += voltage*(current-i3n)*(
                    a['burstLength']/a['dataRate'])*ck*n[command]*D
            # Auto-PRE is a separate increment in DRAMPower 6.3.1.
            # Historic v6 traces had no auto-precharge; do not silently omit
            # this term for future command statistics.
            for command in ('RDA', 'WRA'):
                e['PRE_'+command] += voltage*(beta-i2n)*rp*n[command]*D
            e['REF_AB'] += voltage*(p[refresh]-i3n)*t[rf[2]]*ck*n['REF_AB']*D/B
        for rank in channel['rank_stats']:
            c = rank['cycles']
            e['BG_PRE'] += voltage*i2n*c['pre']*ck*D
            e['BG_ACT_SHARED'] += voltage*irho*c['act']*ck*D
            e['PDNA'] += voltage*i3p*c['powerDownAct']*ck*D
            e['PDNP'] += voltage*i2p*c['powerDownPre']*ck*D
            e['SREF'] += voltage*cur('6n')*c['selfRefresh']*ck*D
        rails[name] = dict(components_J=dict(e), total_J=sum(e.values()),
                           effective_current_A=dict(normal_pre=i2n, normal_act=i3n,
                                                    powerdown_pre=i2p, powerdown_act=i3p))
    total = sum(rail['total_J'] for rail in rails.values())
    return dict(rails=rails, reconstructed_core_J=total,
                reported_core_J=channel['core_J'],
                reconstructed_minus_reported_J=total-channel['core_J'])


def find_channels(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, dict) and 'rank_stats' in child and 'bank_stats' in child:
                yield key, child
            else:
                yield from find_channels(child)
    elif isinstance(value, list):
        for child in value:
            yield from find_channels(child)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audit_json')
    parser.add_argument('config_json')
    parser.add_argument('--zero-vpp-pd', action='store_true')
    parser.add_argument('--output')
    args = parser.parse_args()
    data = json.loads(Path(args.audit_json).read_text(encoding='utf-8-sig'))
    config = json.loads(Path(args.config_json).read_text(encoding='utf-8-sig'))
    memspec = config['simulation']['memspec']
    channels = {name: reprice(channel, memspec, args.zero_vpp_pd)
                for name, channel in find_channels(data)}
    if not channels:
        raise ValueError('No exported DRAMPower bank/rank audit statistics found')
    report = dict(timing_held_fixed=True, zero_vpp_pd_sensitivity=args.zero_vpp_pd,
                  current_source='Input config; official MemSpecDDR4 direct mapping checked',
                  channels=channels,
                  reconstructed_core_total_J=sum(c['reconstructed_core_J'] for c in channels.values()))
    result = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(result+'\n', encoding='utf-8')
    else:
        print(result)
