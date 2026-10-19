"""Source-backed currents and complete measurement-loop accounting checks."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'architecture_tlm'))
from dram_power_profile import PROFILE, apply, audit, state_power, memspec

spec = importlib.util.spec_from_file_location('reprice_ref', ROOT/'architecture_tlm/dramsys/reprice_ddr4_audit.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


class PowerProfileTests(unittest.TestCase):
    def setUp(self):
        self.old = json.loads((ROOT/'architecture_tlm/dramsys/ddr4_2ch_Staggered.json').read_text(encoding='utf-8'))
        self.profile = json.loads(PROFILE.read_text(encoding='utf-8'))
        self.new = apply(self.old, self.profile)

    def channel(self, active=0, pre=0, pdpre=0, pdact=0, sref=0):
        n = memspec(self.new)['memarchitecturespec']['nbrOfBanks']
        banks = [dict(cycles=dict(act=active if i == 0 else 0),
                      commands={k:0 for k in ('ACT','PRE','RD','WR','RDA','WRA','REF_AB')}) for i in range(n)]
        return dict(bank_stats=banks, rank_stats=[dict(cycles=dict(act=active,pre=pre,
                    powerDownPre=pdpre,powerDownAct=pdact,selfRefresh=sref))],core_J=0)

    def test_historical_input_not_accepted(self):
        r = audit(self.old, self.profile)
        self.assertFalse(r['source_backed_core_scenario'])
        self.assertFalse(r['complete_dram_energy_usable'])
        self.assertGreater(r['state_W_per_rank_channel']['active_powerdown'],
                           r['state_W_per_rank_channel']['active_standby'])
        self.assertTrue(any('duplicates' in w for w in r['warnings']))

    def test_datasheet_state_power_per_eight_devices(self):
        # Independent hand totals from Table 146, not simulator output.
        expected = dict(pre_standby=.4824, active_standby=.6456,
                        pre_powerdown=.348, active_powerdown=.4824, self_refresh=.252)
        for k, v in expected.items():self.assertAlmostEqual(state_power(self.new)[k],v)
        self.assertTrue(audit(self.new,self.profile)['source_backed_core_scenario'])

    def test_preserve_input_and_timings(self):
        old_bytes = json.dumps(self.old,sort_keys=True)
        new = apply(self.old,self.profile)
        self.assertEqual(json.dumps(self.old,sort_keys=True),old_bytes)
        self.assertEqual(memspec(new)['memtimingspec'],memspec(self.old)['memtimingspec'])
        self.assertNotIn('iBeta_vdd',memspec(new)['mempowerspec'])

    def test_incompatible_geometries_and_refresh_rejected(self):
        for key, value in [('width',16),('RefMode',2),('nbrOfRows',65536)]:
            bad = copy.deepcopy(self.old)
            memspec(bad)['memarchitecturespec'][key]=value
            with self.assertRaises(ValueError):apply(bad,self.profile)

    def test_stale_beta_not_source_consistent(self):
        memspec(self.new)['mempowerspec']['iBeta_vdd']=.05625
        self.assertFalse(audit(self.new,self.profile)['source_backed_core_scenario'])

    def test_same_currents_wrong_density_not_accepted(self):
        memspec(self.new)['memarchitecturespec']['nbrOfRows']*=2
        self.assertFalse(audit(self.new,self.profile)['source_backed_core_scenario'])

    def test_invalid_current_rejected(self):
        memspec(self.new)['mempowerspec']['ipp3n']=float('nan')
        self.assertEqual(audit(self.new,self.profile)['scope'],'invalid')

    def test_complete_activate_precharge_loop_matches_I0(self):
        s=memspec(self.new);t=s['memtimingspec'];p=s['mempowerspec'];a=s['memarchitecturespec']
        c=self.channel(active=t['RAS'],pre=t['RP'])
        c['bank_stats'][0]['commands'].update(ACT=1,PRE=1)
        result=reference.reprice(c,s)['reconstructed_core_J']
        expected=a['nbrOfDevices']*(p['vdd']*p['idd0']+p['vpp']*p['ipp0'])*(t['RAS']+t['RP'])*t['tCK']
        self.assertAlmostEqual(result,expected,places=18)
        # Some increments are relative background corrections: never clamp them.
        self.assertLess(reference.reprice(c,s)['rails']['VDD']['components_J']['ACT'],0)

    def test_read_loop_background_plus_increment(self):
        s=memspec(self.new);t=s['memtimingspec'];p=s['mempowerspec'];a=s['memarchitecturespec']
        c=self.channel(active=100);c['bank_stats'][0]['commands']['RD']=1
        duration=a['burstLength']/a['dataRate']
        expected=a['nbrOfDevices']*t['tCK']*(
            p['vdd']*(p['idd3n']*(100-duration)+p['idd4r']*duration)+
            p['vpp']*(p['ipp3n']*(100-duration)+p['ipp4r']*duration))
        self.assertAlmostEqual(reference.reprice(c,s)['reconstructed_core_J'],expected,places=18)

    def test_one_millisecond_powerdown_counts_devices_once(self):
        s=memspec(self.new);cycles=round(1e-3/s['memtimingspec']['tCK'])
        r=reference.reprice(self.channel(pdpre=cycles),s)['reconstructed_core_J']
        self.assertAlmostEqual(r,.348*cycles*s['memtimingspec']['tCK'],places=18)

    def test_core_does_not_certify_io_or_timing(self):
        r=audit(self.new,self.profile)
        self.assertFalse(r['complete_dram_energy_usable'])
        self.assertFalse(r['timing_verified'])

    def test_auto_precharge_not_missing_its_pre_increment(self):
        s=memspec(self.new)
        auto=self.channel(active=100,pre=13)
        explicit=copy.deepcopy(auto)
        auto['bank_stats'][0]['commands']['RDA']=1
        explicit['bank_stats'][0]['commands'].update(RD=1,PRE=1)
        self.assertAlmostEqual(reference.reprice(auto,s)['reconstructed_core_J'],
                               reference.reprice(explicit,s)['reconstructed_core_J'],places=18)

    def test_cli_rejects_old_and_never_overwrites(self):
        old=ROOT/'architecture_tlm/dramsys/ddr4_2ch_Staggered.json'
        cli=ROOT/'architecture_tlm/dram_power_profile.py'
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            output=Path(directory)/'scenario.json'
            self.assertEqual(subprocess.run([sys.executable,str(cli),str(old),'--require-core-profile'],capture_output=True).returncode,2)
            self.assertEqual(subprocess.run([sys.executable,str(cli),str(old),'--make-core-scenario',str(output),'--require-core-profile'],capture_output=True).returncode,0)
            before=output.read_bytes()
            self.assertNotEqual(subprocess.run([sys.executable,str(cli),str(old),'--make-core-scenario',str(output)],capture_output=True).returncode,0)
            self.assertEqual(before,output.read_bytes())


if __name__=='__main__':unittest.main()
