import unittest

from .contracts import Clock,Operation,Resource
from .kernel import Kernel
from .rng_protocol import NativeRandomService,buffers,resources
from architecture_tlm.random_service.model import Endpoint,RandomNetwork,SeedWords


def make_driver(kinds=None,**kwargs):
    kernel=Kernel(resources()+[Resource('control',Clock('core',10000),1,capacity=2)],buffers('test'))
    driver=NativeRandomService(kernel,'test',kinds or {'ffn':'lfsr32'},**kwargs)
    return kernel,driver


class NativeProtocolTests(unittest.TestCase):
    def test_cycle_event_cold_start_hold_and_warmup(self):
        results=[]
        for mode in ('cycle','event'):
            kernel,driver=make_driver({'biased':'bivium'},seed=7,seed_interval=2,seed_startup=30,hold_cycles=4)
            responses=[]
            first=driver.frame('first',{'biased':[128]*20},(),lambda r,done:responses.append(r))
            driver.frame('second',{'biased':[128]*20},(first,),lambda r,done:responses.append(r))
            result=kernel.run(mode)
            report=driver.report()
            self.assertEqual(len(responses),2)
            counters=report['ports']['biased']['counts']
            self.assertEqual(counters['frames_generated'],2)
            self.assertEqual(counters['responses_consumed'],2)
            self.assertEqual(counters['warmup_updates'],5)
            self.assertEqual(counters['output_stall_cycles'],8)
            self.assertGreater(responses[0]['wait_edges'],30)
            results.append((result.equivalence_payload(),responses,report))
        self.assertEqual(results[0],results[1])

    def test_idle_age_and_reseed_match_original_tick_network(self):
        kernel,driver=make_driver(seed=18,seed_interval=2,seed_startup=0,reseed_cycles=30)
        responses=[]
        first=driver.frame('first',{'ffn':[128]},(),lambda r,done:responses.append(r))
        kernel.add(Operation('gap','control',deps=(first,),earliest_ps=2000000))
        driver.frame('second',{'ffn':[128]},('gap',),lambda r,done:responses.append(r))
        kernel.run()
        report=driver.report()
        self.assertGreater(responses[1]['epochs']['ffn'],responses[0]['epochs']['ffn'])
        network=RandomNetwork({'ffn':Endpoint('lfsr32',30)},SeedWords('fixture',2,0,fixture_seed=18,
            provenance='explicit deterministic seed-bus fixture; not physical entropy'))
        accepts={r['valid_ps']//10000 for r in responses}
        observed=[]
        for cycle in range(report['cycles']):
            result=network.tick({'ffn':[128]} if cycle in accepts else {})
            if result['ffn']['accepted']: observed.append(result['ffn']['words'])
        self.assertEqual(observed,[r['words']['ffn'] for r in responses])
        self.assertEqual(network.report()['seed_events'],report['seed_events'])
        self.assertEqual(network.ports['ffn'].age,driver.network.ports['ffn'].age)
        self.assertEqual(network.ports['ffn'].state,driver.network.ports['ffn'].state)

    def test_save_restore_release_preserves_sequence_across_due_reseed(self):
        kernel,driver=make_driver(seed=4,seed_interval=1,seed_startup=0,reseed_cycles=10)
        responses=[]
        saved=driver.command('save','ffn',1,())
        first=driver.frame('first',{'ffn':[128]},(saved,),lambda r,done:responses.append(r))
        second=driver.frame('second',{'ffn':[128]},(first,),lambda r,done:responses.append(r))
        restored=driver.command('restore','ffn',2,(second,))
        replay=driver.frame('replay',{'ffn':[128]},(restored,),lambda r,done:responses.append(r))
        driver.command('release','ffn',3,(replay,))
        kernel.run()
        report=driver.report()
        self.assertEqual(responses[0]['words'],responses[2]['words'])
        counters=report['ports']['ffn']['counts']
        self.assertGreater(counters['reseed_deferred_cycles'],0)
        self.assertEqual(counters['checkpoint_bits_written'],32)
        self.assertEqual(counters['restore_bits_loaded'],32)
        self.assertFalse(driver.network.ports['ffn'].locked)

    def test_parallel_native_wave_waits_for_all_seed_packets(self):
        kernel,driver=make_driver({'a':'bivium','b':'bivium'},seed_interval=3,seed_startup=1)
        responses=[]
        driver.frame('parallel',{'a':[0]*20,'b':[256]*20},(),lambda r,done:responses.append(r))
        kernel.run()
        response=responses[0]
        self.assertEqual(response['bits']['a'],(False,)*20)
        self.assertEqual(response['bits']['b'],(True,)*20)
        report=driver.report()
        self.assertEqual(report['ports']['a']['counts']['frames_generated'],1)
        self.assertEqual(report['ports']['b']['counts']['frames_generated'],1)
        self.assertEqual(len(report['seed_word_transcript']),12)


if __name__=='__main__': unittest.main()
