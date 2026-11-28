"""Add only the x S/S2 flag to the frozen g/u S/S2 numerical path."""
import dynamic
from half import FractionOverride, encode

FROZEN_X_ENCODE = dynamic.encode

def encode_x(value, enabled=True):
    return encode(value, 512., correction=enabled, step_bits=1)

class XOnebitOverride(FractionOverride):
    def __init__(self, enabled=True):
        super().__init__('all64_onebit', 1)
        self.x_enabled = enabled

    def __enter__(self):
        self.saved_x = dynamic.encode
        def x_encode(value, group, cap):
            assert group == 64 and cap == 512.
            enc = encode_x(value, self.x_enabled)
            self.observe('x', value, enc)
            return tuple(enc[k] for k in ['q','sign','exponent','shift','scale'])
        dynamic.encode = x_encode
        try:
            result = super().__enter__()
            hard = self.sf.upstream.hard_forward
            def tagged(x, wg, wu, wd, module, key):
                value = hard(x, wg, wu, wd, module, key)
                if isinstance(module.config, self.sf.Config):
                    module.last_arithmetic['x_policy'] = 'dynamic64_S_S2' if self.x_enabled else 'dynamic64_single'
                return value
            self.sf.upstream.hard_forward = tagged
            return result
        except BaseException:
            dynamic.encode = self.saved_x
            raise

    def __exit__(self, *exc):
        try:
            return super().__exit__(*exc)
        finally:
            dynamic.encode = self.saved_x

    def report(self):
        r = super().report()
        return dict(r['probability_codes'], group_scales=r['group_scales'],
                    integer_backend=r['integer_backend'], step_bits=1,
                    x_onebit_enabled=self.x_enabled)
