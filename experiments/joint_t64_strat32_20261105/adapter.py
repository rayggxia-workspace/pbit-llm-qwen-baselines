"""Only swap sampling functions in a verified original seven-case runtime.

Arithmetic functions, stored weights/exponents/tables and source files remain
unchanged. Hybrid Tx/Tand intentionally relaxes the *training-plan* equality
for this inference ablation; each denominator is already separate upstream.
"""
from contextlib import AbstractContextManager
from sampling import shared_input_counts, joint_counts


class SamplingOverride(AbstractContextManager):
    def __init__(self, case):
        import seven_forward as sf
        self.sf, self.case = sf, case
        self.original_input, self.original_and = sf.iid_shared64_counts, sf.count_events

    def configure(self, modules):
        for m in modules:
            if not isinstance(m.config, self.sf.Config):
                raise TypeError('verified seven-case config required')
            m.config.mode = 'sampled'
            m.config.input_samples = self.case['T_x']
            m.config.nonlinear_samples = self.case['T_and']
            m.reset_runtime_audit()

    def __enter__(self):
        if self.case['input_law'] == 'stratified_T':
            def sample_input(codes, samples, generator=None, thresholds=None):
                if thresholds is not None:
                    raise ValueError('literal IID replay is not a stratified candidate')
                return shared_input_counts(codes, samples, generator)
            self.sf.iid_shared64_counts = sample_input
        elif self.case['input_law'] != 'original_IID':
            raise ValueError('unknown input law')
        if self.case['and_law'] == 'joint_grid':
            def sample_and(codes, samples, generator):
                count = joint_counts(codes, samples, tuple(self.case['grid_g_sig_u']), generator)
                return count, (codes[0] * codes[1] * codes[2]).double() / 256 ** 3
            self.sf.count_events = sample_and
        elif self.case['and_law'] != 'original_IID':
            raise ValueError('unknown AND law')
        return self

    def __exit__(self, *exc):
        self.sf.iid_shared64_counts = self.original_input
        self.sf.count_events = self.original_and
        return False
