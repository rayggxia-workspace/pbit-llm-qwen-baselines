"""NVML device energy/power telemetry; does not claim per-unit rail power."""
import ctypes as C
import statistics
import threading
import time


class Nvml:
    def __init__(self, uuid):
        self.lib=C.CDLL('libnvidia-ml.so.1')
        self._check(self.lib.nvmlInit_v2())
        self.handle=C.c_void_p()
        self._check(self.lib.nvmlDeviceGetHandleByUUID(str(uuid).encode(),C.byref(self.handle)))
        self.uuid=str(uuid)

    @staticmethod
    def _check(code):
        if code:raise RuntimeError('NVML return code '+str(code))

    def energy_mJ(self):
        value=C.c_ulonglong()
        self._check(self.lib.nvmlDeviceGetTotalEnergyConsumption(self.handle,C.byref(value)))
        return value.value

    def power_W(self):
        value=C.c_uint()
        self._check(self.lib.nvmlDeviceGetPowerUsage(self.handle,C.byref(value)))
        return value.value/1000.

    def state(self):
        result={}
        for key,function,extra in [('temperature_C','nvmlDeviceGetTemperature',0),
            ('SM_clock_MHz','nvmlDeviceGetClockInfo',1),('memory_clock_MHz','nvmlDeviceGetClockInfo',2)]:
            value=C.c_uint()
            try:
                self._check(getattr(self.lib,function)(self.handle,extra,C.byref(value)))
                result[key]=value.value
            except Exception as e:result[key]={'error':str(e)}
        return result


def integrate(samples,start,end):
    """Piecewise-linear power integral. Refuse a window not bracketed by data."""
    if len(samples)<2 or samples[0][0]>start or samples[-1][0]<end or end<=start:
        raise ValueError('unbracketed or empty power window')
    total=0.
    for (t0,p0),(t1,p1) in zip(samples,samples[1:]):
        lo=max(t0,start);hi=min(t1,end)
        if hi<=lo:continue
        if t1<=t0:raise ValueError('nonmonotonic power sample')
        q0=p0+(p1-p0)*(lo-t0)/(t1-t0)
        q1=p0+(p1-p0)*(hi-t0)/(t1-t0)
        total+=(q0+q1)*.5*(hi-lo)
    return total


class PowerSampler:
    def __init__(self,nvml,interval=.02):
        self.nvml=nvml;self.interval=interval;self.samples=[];self.errors=[]
        self.stop_event=threading.Event()

    def start(self):
        self.thread=threading.Thread(target=self._run,daemon=True);self.thread.start()
        deadline=time.perf_counter()+2
        while len(self.samples)<2 and time.perf_counter()<deadline:time.sleep(.005)
        if len(self.samples)<2:raise RuntimeError('power telemetry unavailable: '+str(self.errors))
        return self

    def _run(self):
        while not self.stop_event.is_set():
            try:
                t0=time.perf_counter();p=self.nvml.power_W();t1=time.perf_counter()
                self.samples.append(((t0+t1)*.5,p))
            except Exception as e:self.errors.append(str(e))
            self.stop_event.wait(self.interval)

    def finish(self):
        time.sleep(self.interval*2);self.stop_event.set();self.thread.join()


def summarize(rows):
    keys=['wall_s','gpu_ms','energy_J','average_W','energy_mJ_per_item','wall_ms_per_item']
    out={}
    for key in keys:
        values=[r[key] for r in rows if r.get(key) is not None]
        if values:out[key]={'mean':statistics.mean(values),'stdev':statistics.stdev(values) if len(values)>1 else 0.,'min':min(values),'max':max(values)}
    return out
