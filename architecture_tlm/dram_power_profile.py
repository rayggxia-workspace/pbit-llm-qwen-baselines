"""Preflight and source-backed DDR4 core-current scenario builder.

This is not a DRAM simulator. Existing historical inputs/results are never edited.
Scope acceptance is limited to the current profile, not complete DIMM/PHY power.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

PROFILE = Path(__file__).parent/'configs/dram_power_micron4gb_reva_1866_limits.json'


def memspec(document):
    return document.get('simulation', document).get('memspec', document)


def state_power(document):
    """Watts per rank/channel, including all devices but not other channels."""
    s = memspec(document)
    a, p = s['memarchitecturespec'], s['mempowerspec']
    n = a['nbrOfDevices']
    return {name: n*(p['vdd']*p['idd'+suffix]+p['vpp']*p['ipp'+suffix])
            for name, suffix in [('pre_standby', '2n'), ('active_standby', '3n'),
                                 ('pre_powerdown', '2p'), ('active_powerdown', '3p'),
                                 ('self_refresh', '6n')]}


def audit(document, profile):
    s = memspec(document)
    a, p = s['memarchitecturespec'], s['mempowerspec']
    errors, warnings = [], []
    if s.get('memoryType') != 'DDR4':
        errors.append('This audit only covers DDR4.')
    required = {**profile['current_limits_A'], **profile['voltages_V']}
    for key in required:
        if key not in p or not isinstance(p[key], (float, int)) or not math.isfinite(p[key]) or p[key] < 0:
            errors.append('Missing/nonfinite/negative power field: '+key)
    if errors:
        return dict(scope='invalid', errors=errors, warnings=warnings,
                    source_backed_core_scenario=False, complete_dram_energy_usable=False)
    watts = state_power(document)
    for state, standby in [('pre_powerdown','pre_standby'), ('active_powerdown','active_standby')]:
        if watts[state] > watts[standby]:
            warnings.append(state+' exceeds corresponding standby: investigate input data; not by itself a universal physics proof.')
    for low, dd in [('ipp2p','idd2p'), ('ipp3p','idd3p')]:
        if p[low] == p[dd] and p[low] > p.get('ipp3n', 0):
            warnings.append(low+' duplicates '+dd+' while VPP standby is lower; this is not the cited Micron mapping.')
    if p.get('vddq', 0) <= 0:
        warnings.append('VDDQ is zero/missing; no calibrated IO energy claim. Other interface proxy terms may still be nonzero.')
    matches = all(math.isclose(p[k], v, rel_tol=0, abs_tol=1e-12) for k, v in required.items())
    beta_ok = all(math.isclose(p.get(beta, p[base]), p[base], abs_tol=1e-12)
                  for beta, base in [('iBeta_vdd','idd0'), ('iBeta_vpp','ipp0')])
    density = (a.get('nbrOfBanks', 0)*a.get('nbrOfRows', 0)*
               a.get('nbrOfColumns', 0)*a.get('width', 0)/2**30)
    geometry_ok = (a.get('width') == 8 and a.get('RefMode', 1) == 1 and
                   math.isclose(density, 4))
    # A current profile cannot certify die selection, timing, board wiring or IO.
    accepted = matches and beta_ok and geometry_ok and s.get('memoryType') == 'DDR4'
    return dict(scope='core_current_scenario_only', errors=errors, warnings=warnings,
                state_W_per_rank_channel=watts, matches_cited_current_limits=matches,
                iBeta_consistent=beta_ok, source_backed_core_scenario=accepted,
                complete_dram_energy_usable=False, interface_verified=False,
                timing_verified=False, actual_target_device_selected=False,
                profile_id=profile['profile_id'] if accepted else None,
                note='CLI acceptance certifies this current scenario only. No measured-power or complete-system claim.')


def apply(document, profile):
    out = copy.deepcopy(document)
    s = memspec(out)
    a = s['memarchitecturespec']
    if s.get('memoryType') != 'DDR4' or a.get('width') != 8 or a.get('RefMode', 1) != 1:
        raise ValueError('Profile requires x8 DDR4 RefMode=1.')
    density = a['nbrOfBanks']*a['nbrOfRows']*a['nbrOfColumns']*a['width']/2**30
    if not math.isclose(density, 4):
        raise ValueError('Profile requires 4Gbit per device, not rank/channel capacity.')
    p = s['mempowerspec']
    p.update(profile['current_limits_A'])
    p.update(profile['voltages_V'])
    p.pop('iBeta_vdd', None)
    p.pop('iBeta_vpp', None)
    # Deliberately keep IO and timings unchanged and explicitly unverified.
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('config', type=Path)
    ap.add_argument('--profile', type=Path, default=PROFILE)
    ap.add_argument('--make-core-scenario', type=Path)
    ap.add_argument('--output', type=Path)
    ap.add_argument('--require-core-profile', action='store_true')
    args = ap.parse_args()
    raw = args.config.read_bytes()
    original = json.loads(raw.decode('utf-8-sig'))
    profile_raw = args.profile.read_bytes()
    profile = json.loads(profile_raw.decode('utf-8-sig'))
    current = original
    if args.make_core_scenario:
        if args.make_core_scenario.resolve() == args.config.resolve() or args.make_core_scenario.exists():
            raise ValueError('Refusing to overwrite input or an existing scenario.')
        current = apply(original, profile)
        args.make_core_scenario.parent.mkdir(parents=True, exist_ok=True)
        args.make_core_scenario.write_bytes((json.dumps(current, indent=2)+'\n').encode('utf-8'))
    result = audit(current, profile)
    result.update(input_sha256=hashlib.sha256(raw).hexdigest(),
                  profile_sha256=hashlib.sha256(profile_raw).hexdigest(),
                  source=profile['source'], historical_input_unchanged=True)
    text = json.dumps(result, indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(text.encode('utf-8'))
    else:
        print(text)
    if result['errors'] or (args.require_core_profile and not result['source_backed_core_scenario']):
        raise SystemExit(2)


if __name__ == '__main__':
    main()
