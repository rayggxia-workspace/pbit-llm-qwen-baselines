"""Opt-in v5 integration; v4's original black-box default is unchanged."""
import copy
import hashlib
from pathlib import Path
from screen_ising_tlm_v4 import ScreenIsingLocal, ScreenIsingDigital
from winner_hold_tlm_v5 import WinnerHoldSampler
from corrected_rejection_tlm_v5 import CorrectedRejectionSampler


def sampler(kind, options, capacity):
    cls = {'winner_hold': WinnerHoldSampler,
           'corrected_rejection': CorrectedRejectionSampler}.get(kind)
    if cls is None:
        raise ValueError('unknown parallel sampler')
    return cls(options,capacity)


class ParallelScreenMixin:
    def __init__(self,cfg,variant,evidence,shape):
        self.parallel_cfg = copy.deepcopy(cfg['parallel_sampler_v5'])
        super().__init__(cfg,variant,evidence,shape)

    def make_sampler(self,v):
        return sampler(self.parallel_cfg['kind'],self.parallel_cfg['options'],v['candidate_capacity'])

    def prepare_sampler_input(self,t,n,cap):
        # Compact logits have already been read by the parent. The module now
        # explicitly times max, subtraction/encoding and source programming.
        return t

    def sampler_work_bytes(self,cap,samples):
        # Host histogram + output scratch. No second probability table or
        # configuration-register array. Source drive state belongs to backend.
        # Captured bitmap/reduction state is separately bounded by buffer_bits.
        return cap*4+samples*4

    def run(self):
        d = super().run()
        a = d.pop('attention_v4')
        a.update(config=self.parallel_cfg, sampler=a.pop('ising'),
                 mapping='screen -> compact exact QK -> full-width explicit sampler -> histogram/remap -> V gather/repeated adds',
                 limitations=[
                     'Source technology undecided; configured LT timing is a scenario, not measured timing.',
                     'Every candidate lane uses independent fresh ideal response; no FFN shared-threshold shortcut.',
                     'Single-query blocking FSM; no claim of one completed update per clock.',
                     'Energy/area totals are null while source/digital terms are uncharacterized.',
                     'Inherited screening, V-gather mapping and non-Attention costs retain v3/v4 limitations.',
                     'No new full-model PPL or PT/DRAMSys execution is implied.'])
        a['requests'] = self.macro.requests
        for event in a['events']:
            if event['name']=='Ising_macro':
                event['name']='Sampler_'+self.macro.kind
        d['attention_v5'] = a
        metrics = d['metrics']
        incomplete_e = a['sampler']['physical_energy_J'] is None
        incomplete_a = a['sampler']['physical_area_mm2'] is None
        # Parent ledgers hold only known subtotals for compatibility. Never
        # advertise them as complete physical energy/area in this adapter.
        for key in ('scenario_mJ_per_token','attention_direct_mJ_per_token','ising_mJ_per_token'):
            if key in metrics:
                metrics['partial_'+key] = metrics[key]
                if incomplete_e:
                    metrics[key] = None
        if incomplete_a:
            metrics['partial_parameterized_area_mm2'] = metrics['parameterized_area_mm2']
            metrics['parameterized_area_mm2'] = None
            metrics['area_budget_feasible'] = None
        d['energy_coverage'] = dict(physical_total_complete=False,
            sampler_dynamic_complete=not incomplete_e,
            warning='energy_J is a partial/parameterized ledger; inherited digital costs also lack full characterization')
        d['implementation'] = 'explicit full-width sampler v5 + inherited Python LT decode/optional DRAMSys'
        d['quality_reference_ppl'] = None
        for name in ('parallel_sampler_v5.py','winner_hold_tlm_v5.py',
                     'corrected_rejection_tlm_v5.py','screen_parallel_tlm_v5.py'):
            d['source_hashes'][name] = hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
        return d


class ScreenParallelLocal(ParallelScreenMixin,ScreenIsingLocal):
    pass


class ScreenParallelDigital(ParallelScreenMixin,ScreenIsingDigital):
    pass
