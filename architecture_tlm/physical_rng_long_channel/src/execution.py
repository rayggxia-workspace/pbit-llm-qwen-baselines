"""One shared pool for all Spectre cases; Python 3.6 standard library."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
from pathlib import Path
import threading
import time


def check_resources(workers, preview=False, environ=None):
    env=os.environ if environ is None else environ
    if isinstance(workers,bool) or not isinstance(workers,int) or not 1<=workers<=8:
        raise ValueError('Workers must be an integer from 1 to 8')
    if not preview:
        if not env.get('SLURM_JOB_ID'):
            raise ValueError('Run physical simulations inside Slurm via submit.sh')
        if int(env.get('SLURM_CPUS_PER_TASK','0'))<workers:
            raise ValueError('Worker count exceeds SLURM_CPUS_PER_TASK')
    return workers


class CasePool:
    """Controllers never run on this pool, so waiting controllers cannot deadlock it.

    A worker owns an independent case directory and at most one single-threaded
    Spectre process. Postprocessing occupies the same worker slot. Events count
    active case workers, including their output checks, rather than CPU utilization.
    """
    def __init__(self,workers,event_path=None):
        check_resources(workers,preview=True)
        self.workers=workers
        self.executor=ThreadPoolExecutor(max_workers=workers)
        self.lock=threading.Lock()
        self.active=0;self.peak=0;self.started=0;self.finished=0;self.errors=0
        self.case_wall_sum_s=0.;self.started_at=time.monotonic()
        self.stream=Path(event_path).open('x',encoding='utf-8',newline='\n') if event_path else None

    def _event(self,event,label,error=None):
        if self.stream:
            row=dict(utc=datetime.utcnow().isoformat()+'Z',event=event,case=label,
                     active_case_workers=self.active,worker_limit=self.workers)
            if error:row['error']=error
            self.stream.write(json.dumps(row,sort_keys=True)+'\n');self.stream.flush()

    def submit(self,label,fn,*args):
        return self.executor.submit(self._execute,label,fn,args)

    def _execute(self,label,fn,args):
        start=time.monotonic();error=None
        with self.lock:
            self.active+=1;self.started+=1;self.peak=max(self.peak,self.active)
            self._event('START',label)
        try:
            return fn(*args)
        except BaseException as exc:
            error=type(exc).__name__+': '+str(exc)
            raise
        finally:
            with self.lock:
                self.active-=1;self.finished+=1;self.errors+=int(error is not None)
                self.case_wall_sum_s+=time.monotonic()-start
                self._event('FINISH',label,error)

    def stats(self):
        with self.lock:
            elapsed=time.monotonic()-self.started_at
            return dict(worker_limit=self.workers,peak_active_case_workers=self.peak,
                        active_case_workers=self.active,cases_started=self.started,
                        cases_finished=self.finished,worker_exceptions=self.errors,
                        elapsed_wall_s=elapsed,sum_case_wall_s=self.case_wall_sum_s,
                        interpretation='Case wall times include output checks; not a measured CPU utilization or speedup')

    def __enter__(self):return self

    def __exit__(self,*unused):
        self.executor.shutdown(wait=True)
        if self.stream:self.stream.close()
