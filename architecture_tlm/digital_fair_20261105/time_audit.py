"""Sub-picosecond numerical tolerance for an exclusive-time ledger.

Times remain nanoseconds. This checker never changes events or durations.
The 1e-6 ns bound is 1/1000 of the host's 1ps event quantization.
"""
import math

FIELDS=('input_init_ns','weight_ready_wait_ns','operand_service_ns',
        'arithmetic_tail_ns','reduction_output_ns')
ABS_TOL_NS=1e-6

def check_exclusive_time(audit):
    actual=audit['elapsed_ns']
    exclusive=math.fsum(audit[k] for k in FIELDS)
    residual=actual-exclusive
    audit.update(exclusive_sum_ns=exclusive,time_ledger_residual_ns=residual,
                 time_ledger_tolerance_ns=ABS_TOL_NS)
    if not math.isfinite(actual) or not math.isfinite(exclusive) or abs(residual)>ABS_TOL_NS:
        raise AssertionError(dict(audit,issue='exclusive matrix-time ledger mismatch'))
    return audit
