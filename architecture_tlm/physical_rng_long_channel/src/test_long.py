"""Synthetic fixtures verify scripts; none of these tests is physical evidence."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import channel
import common
from execution import CasePool
import long_metrics as m
import run_long as driver
from timestamped_seed import TimestampedSeedWords

SOURCE=Path(__file__).resolve().parent
C=json.loads((SOURCE/'config.json').read_text(encoding='utf-8'))
B=json.loads((SOURCE/'base_config.json').read_text(encoding='utf-8'))


def fixture(path,q,bad_index=None):
    start=round(q['discard_s']/q['strobe_s']);stride=round(C['sample_interval_s']/q['strobe_s'])
    pattern=[0,1,1,0]
    with path.open('w',encoding='utf-8',newline='\n') as f:
        f.write('HEADER\nVALUE\n')
        for j in range(round(q['stop_s']/q['strobe_s'])+1):
            k=(j-start)//stride;bit=.8*pattern[k%4]
            if bad_index is not None and j==start+bad_index*stride:bit=.4
            f.write('"time" {:.16g}\n"out" {:.16g}\n"bit" {:.16g}\n'.format(j*q['strobe_s'],.6+(j%7-3)*.0001,bit))
        f.write('END\n')


class ProtocolTests(unittest.TestCase):
    def test_complete_old_channel_same_transistors_bias_and_load(self):
        v=channel.validate(C,B);q=channel.transient_parameters(1.02,.02,1e-5,10,seed=41011)
        deck=channel.noise_deck(Path('/model.lib'),B,v,.608,q)
        import zero_core as z
        old=z.build(Path('/model.lib'),B,v,'validation',.608,q=q)
        devices=lambda s:[line for line in s.splitlines() if line.startswith(('X','VDD ','VGN ','VGP ','VDC ','IREF ','Cbit '))]
        self.assertEqual(devices(deck),devices(old))
        self.assertEqual(sum(line.startswith('X') for line in deck.splitlines()),17)
        self.assertIn('Cbit (bit 0) capacitor c=5e-15',deck)
        self.assertNotIn('Ccore ',deck);self.assertNotIn('VIN (out',deck)
        self.assertNotIn('noiseoff=',deck);self.assertIn('noisescale=1',deck)
        self.assertIn('strobeperiod=1e-05',deck);self.assertIn('maxstep=2.5e-09',deck)

    def test_low_fmin_requires_long_enough_actual_tran(self):
        with self.assertRaises(ValueError):channel.transient_parameters(.02,.002,1e-5,10)
        q=channel.transient_parameters(.12,.02,1e-5,10)
        self.assertEqual(q['noisefmin_Hz'],10)
        with self.assertRaises(ValueError):channel.transient_parameters(.120001,.02,1e-5,10)

    def test_noise_audit_masks_real_core_and_comparator(self):
        q=channel.transient_parameters(.003,.001,2e-7)
        v=channel.candidate(C,B)
        core=channel.noise_deck(Path('/m.lib'),B,v,.608,q,'core_only')
        cmp=channel.noise_deck(Path('/m.lib'),B,v,.608,q,'comparator_only')
        self.assertIn('noiseoff=[XN XP]',cmp)
        self.assertIn('noiseoff=[XPBIAS XBIAS',core)
        self.assertNotIn('noiseoff=[XN XP]',core)

    def test_new_calibration_screen_validation_and_extension_seeds_disjoint(self):
        channel.validate(C,B)
        c=copy.deepcopy(C);c['validation_seeds'][0]=c['calibration_seeds'][0]
        with self.assertRaises(AssertionError):channel.validate(c,B)

    def test_actual_long_sample_count_and_internal_step_budget(self):
        q=channel.transient_parameters(1.02,.02,1e-5,10)
        self.assertEqual(round((q['stop_s']-q['discard_s'])/C['sample_interval_s']),10000)
        self.assertEqual(round(q['stop_s']/q['maxstep_s']),408000000)

    def test_cost_uses_measured_runtime_and_keeps_extrapolation_label(self):
        r=[dict(simulator_elapsed_s=30,setting={'q':dict(stop_s=.003)})]
        estimate=driver.cost_projection(r,C)
        self.assertEqual(estimate['status'],'EXTRAPOLATION_NOT_MEASUREMENT')
        self.assertAlmostEqual(estimate['wall_seconds_per_record_with_safety_factor'],20400)


class QualityTests(unittest.TestCase):
    def test_one_second_exact_timestamps_blocks_vn_and_packets(self):
        with tempfile.TemporaryDirectory(dir=str(SOURCE)) as tmp:
            root=Path(tmp);q=channel.transient_parameters(1.02,.02,1e-5,10)
            psf=root/'trace.tran';fixture(psf,q)
            r=m.long_record(psf,root,q,.8,C,'SYNTHETIC TEST ONLY')
            self.assertEqual(r['raw']['bits'],10000)
            self.assertEqual(len(r['raw']['blocks']['0.01']),100)
            self.assertTrue(all(b['n']==100 for b in r['raw']['blocks']['0.01']))
            self.assertTrue(all(b['n']==1000 for b in r['raw']['blocks']['0.1']))
            self.assertEqual(r['vn_valid_level_outputs']['bits'],5000)
            self.assertEqual(r['vn_retained_bits_per_raw_bit'],.5)
            self.assertEqual(r['vn_valid_level_outputs']['physical_time_lag_acf']['0.0001']['pairs'],0)
            self.assertEqual(r['vn_valid_level_outputs']['physical_time_lag_acf']['0.0002']['pairs'],4999)
            self.assertEqual(r['seed_packets']['raw']['lfsr32']['complete_packets'],312)
            self.assertEqual(r['seed_packets']['vn']['lfsr32']['adjacent_repeat_count'],155)
            self.assertEqual(r['seed_packets']['vn']['bivium177']['complete_packets'],26)
            trace=json.loads((root/'raw_seed_trace.json').read_text())
            self.assertAlmostEqual(trace['words'][0]['available_s'],.0231)
            self.assertFalse(trace['physical_entropy_certified'])
            self.assertIsNone(trace['entropy_per_word_bits'])

    def test_invalid_levels_are_preserved_and_vn_exclusion_explicit(self):
        raw=[dict(raw_index=i,time_s=i*1e-4,bit=b,level_valid=i!=1) for i,b in enumerate([0,1,1,0,0])]
        emitted,pairs=m.von_neumann(raw)
        self.assertEqual(len(emitted),2);self.assertFalse(emitted[0]['level_valid'])
        self.assertEqual(pairs[0]['reason'],'INVALID_LEVEL')
        self.assertEqual(len(raw),5)
        self.assertEqual([r['bit'] for r in emitted],[0,1])

    def test_midrail_thresholding_is_separate_from_level_validation(self):
        self.assertEqual(m.logic_level(.4,.8,C),'MID')
        self.assertEqual(m.logic_level(.16,.8,C),'LOW')
        self.assertEqual(m.logic_level(.64,.8,C),'HIGH')
        self.assertEqual(m.logic_level(.9,.8,C),'OUT_OF_RAIL')

    def test_constant_or_insufficient_samples_have_null_correlation(self):
        self.assertIsNone(m.corr([1,1],[1,1])['correlation'])
        self.assertIsNone(m.lagged([1],1)['correlation'])

    def test_lsb_first_word_and_bivium_padding(self):
        rows=[dict(bit=int(i==0 or i==31),time_s=i*.0001,raw_index=i,level_valid=True) for i in range(32)]
        words=m.words32(rows)
        self.assertEqual(words[0]['word'],0x80000001)
        stats=m.packet_statistics([dict(word=0xffffffff,available_s=i,level_valid=True) for i in range(6)],177,6)
        self.assertEqual(stats['padding_bits_discarded'],15)
        self.assertEqual(stats['complete_packets'],1)

    def test_no_cross_seed_stitching_api(self):
        # Metrics consume exactly one PSF. Time must start at zero and reach stop.
        with tempfile.TemporaryDirectory(dir=str(SOURCE)) as tmp:
            p=Path(tmp)/'bad.tran';p.write_text('HEADER\nVALUE\n"time" 0\n"out" .6\n"bit" .8\nEND\n')
            with self.assertRaises(ValueError):m.long_record(p,Path(tmp),channel.transient_parameters(1.02,.02,1e-5,10),.8,C,'fixture')


class StageTests(unittest.TestCase):
    def test_preview_freeze_and_long_are_explicitly_not_run(self):
        with tempfile.TemporaryDirectory(dir=str(SOURCE)) as tmp:
            root=Path(tmp);cal=root/'calibrate';cal.mkdir()
            with CasePool(8) as pool:
                s=driver.Runner(cal,Path('/model.lib'),C,B,None,pool,True,'calibrate',1)
                self.assertEqual(s.calibrate(),0);self.assertEqual(len(s.records),27)
            freeze=json.loads((cal/'frozen_reference.json').read_text());self.assertTrue(freeze['generated_only'])
            before=common.digest(cal/'frozen_reference.json')
            long=root/'long';long.mkdir()
            with CasePool(8) as pool:
                s=driver.Runner(long,Path('/model.lib'),C,B,None,pool,True,'long',1)
                self.assertEqual(s.long(cal),0);self.assertEqual(len(s.records),6)
                self.assertEqual({r['setting']['q']['noisefmin_Hz'] for r in s.records},{10,500})
                self.assertTrue(all(r['setting']['frozen_reference_sha256']==before for r in s.records))
            self.assertEqual(common.digest(cal/'frozen_reference.json'),before)

    def test_preview_cannot_unlock_real_next_stage(self):
        with tempfile.TemporaryDirectory(dir=str(SOURCE)) as tmp:
            root=Path(tmp)
            common.save(root/'summary.json',dict(stage='pilot',generated_only=True,eligible_for_next_stage=True,
                source_manifest_sha256=common.digest(SOURCE/'package_manifest.json'),config_sha256=common.digest(SOURCE/'config.json')))
            (root/'job_exit_status.txt').write_text('0\n')
            with self.assertRaises(ValueError):driver.parent_gate(root,'pilot',False)

    def test_failed_case_drains_batch_and_records_successful_sibling(self):
        with tempfile.TemporaryDirectory(dir=str(SOURCE)) as tmp,CasePool(2) as pool:
            s=driver.Runner(Path(tmp),Path('/model.lib'),C,B,None,pool,True,'pilot',1)
            actual=s.execute
            def execute(name,*args):
                if name=='bad':raise RuntimeError('injected')
                return actual(name,*args)
            s.execute=execute
            jobs=[(name,'',[],{},None,1) for name in ['bad','good']]
            rows=s.batch(jobs)
            self.assertEqual(rows[0]['status'],'FAILED_INTERNAL')
            self.assertEqual(rows[1]['status'],'GENERATED_NOT_SIMULATED')
            with self.assertRaises(ValueError):s.require_cases(rows)
            self.assertEqual(pool.stats()['active_case_workers'],0)

    def test_numeric_screen_can_fail_without_changing_reference(self):
        records=[]
        for key in ['base','fine_step','wide_band']:
            for seed in C['pilot_seeds']:
                value=.5 if key!='wide_band' else .7
                d=dict(std_V=.01,cdf=[0,.5,1])
                records.append(dict(setting=dict(matrix_key=key,q=dict(seed=seed)),metrics=dict(p1=value,midrail_fraction=0,
                    core_distribution=d,comparator_distribution=d,dense_bit_acf={'1e-6':dict(correlation=.1)})))
        r=driver.numerical_screen(records,C['pilot_seeds'],C['numerical_screen'])
        self.assertEqual(r['status'],'SHORT_NUMERICAL_SCREEN_NEEDS_REVIEW')

    def test_byte_snapshot_and_result_archive(self):
        with tempfile.TemporaryDirectory(dir=str(SOURCE)) as tmp:
            root=Path(tmp);copy=root/'copy';common.copy_source(copy)
            self.assertEqual((copy/'channel.py').read_bytes(),(SOURCE/'channel.py').read_bytes())
            out=root/'results/123_long';out.mkdir(parents=True);common.save(out/'summary.json',dict(status='SYNTHETIC'))
            archive=common.pack(out)
            self.assertEqual(archive.name,'long_channel_123_long.tar.gz')
            with self.assertRaises(ValueError):common.pack(out)


class AdapterTests(unittest.TestCase):
    def make_trace(self,path,valid=True):
        common.save(path,dict(format='timestamped_simulation_seed_words_v1',physical_entropy_certified=False,provenance='fixture',
            words=[dict(word=123,available_s=.0001,level_valid=valid)]))

    def test_seed_not_available_before_true_completion_and_no_fallback(self):
        with tempfile.TemporaryDirectory(dir=str(SOURCE)) as tmp:
            p=Path(tmp)/'trace.json';self.make_trace(p);source=TimestampedSeedWords(p)
            self.assertIsNone(source.read(9999));self.assertEqual(source.read(10000),123)
            with self.assertRaises(EOFError):source.read(10001)

    def test_invalid_word_rejected_not_silently_removed(self):
        with tempfile.TemporaryDirectory(dir=str(SOURCE)) as tmp:
            p=Path(tmp)/'trace.json';self.make_trace(p,False);source=TimestampedSeedWords(p)
            with self.assertRaises(ValueError):source.read(10000)
            self.assertEqual(source.position,0)

    def test_monotonic_clock_and_simulation_provenance(self):
        with tempfile.TemporaryDirectory(dir=str(SOURCE)) as tmp:
            p=Path(tmp)/'trace.json';self.make_trace(p);source=TimestampedSeedWords(p)
            source.read(5000)
            with self.assertRaises(ValueError):source.read(4999)
            d=json.loads(p.read_text());d['physical_entropy_certified']=True;common.save(p,d)
            with self.assertRaises(ValueError):TimestampedSeedWords(p)

if __name__=='__main__':unittest.main()
