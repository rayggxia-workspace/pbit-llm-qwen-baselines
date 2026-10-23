"""Synthetic FFN scheduler scaling probe, not Qwen or full-model evidence."""
import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import subprocess
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from architecture_tlm.cycle_v1.ffn import FFNConfig,build_ffn,make_kernel


def peak_memory_bytes():
    if os.name!='nt':
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[
            (name,ctypes.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize',
                'QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    counters=Counters()
    counters.cb=ctypes.sizeof(counters)
    ctypes.windll.kernel32.GetCurrentProcess.restype=wintypes.HANDLE
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    ctypes.windll.psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
    ok=ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),
                                              ctypes.byref(counters),counters.cb)
    return counters.PeakWorkingSetSize if ok else None


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--d',type=int,required=True)
    p.add_argument('--f',type=int,required=True)
    p.add_argument('--o',type=int,required=True)
    p.add_argument('--out',required=True)
    args=p.parse_args()
    start=time.perf_counter()
    def matrix(rows,cols,salt):
        return {'codes':[[((r*37+i*13+salt)%255)-127 for i in range(cols)] for r in range(rows)],
                'scales':[[1/127]*math.ceil(cols/64) for _ in range(math.ceil(rows/64))]}
    fixture={'x':[math.sin(i*.13+.1)*2.0**(-((i//16)%4)) for i in range(args.d)],
             'wg':matrix(args.f,args.d,3),'wu':matrix(args.f,args.d,7),
             'wd':matrix(args.o,args.f,11),'residual':[0.0]*args.o}
    fixture_seconds=time.perf_counter()-start
    config=FFNConfig()
    build_start=time.perf_counter()
    kernel=make_kernel(config)
    state=build_ffn(kernel,fixture,config)
    build_seconds=time.perf_counter()-build_start
    run_start=time.perf_counter()
    result=kernel.run(mode='event')
    run_seconds=time.perf_counter()-run_start
    report={'scope':'synthetic partial-shape wall-time probe; not real Qwen or full-layer result',
        'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'ffn_source_sha256':hashlib.sha256((ROOT/'architecture_tlm/cycle_v1/ffn.py').read_bytes()).hexdigest(),
        'shape':[args.d,args.f,args.o],'mode':'event','T':config.samples,'B':config.bins,
        'counter_layout':config.counter_layout,'random_backend':config.random_backend,
        'python':sys.version,'platform':platform.platform(),'cpu':platform.processor(),
        'fixture_seconds':fixture_seconds,'build_seconds':build_seconds,'run_seconds':run_seconds,
        'tiles':len(state['tile_receipts']),'operations':len(kernel.operations),
        'trace_events':len(result.trace),'steps':result.steps,'finish_ps':result.finish_ps,
        'rng_frames':state['native_random']['ports']['ffn']['counts']['frames_generated'],
        'retained_read_payload_bytes':sum(len(v) for v in result.memory_reads.values()),
        'peak_working_set_bytes':peak_memory_bytes(),'actions':result.actions,
        'output_values':len(state['output'])}
    Path(args.out).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='actions'}))


if __name__=='__main__':
    main()
