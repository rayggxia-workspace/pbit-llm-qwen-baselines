"""Explicit APS options, bounded CPU plans and descriptive speed evidence."""
import math
import re


def plan(mode='aps',threads=2,workers=4,cpus=8):
    if mode not in ['classic','aps']:raise ValueError('Solver must be classic or aps')
    for name,value in [('threads',threads),('workers',workers),('cpus',cpus)]:
        if isinstance(value,bool) or not isinstance(value,int) or not 1<=value<=8:
            raise ValueError(name+' must be an integer in 1..8')
    if mode=='classic' and threads!=1:raise ValueError('Classic Spectre is single-threaded; use APS for +mt=N')
    if workers*threads>cpus:raise ValueError('Workers x Spectre threads exceeds CPU budget')
    return dict(mode=mode,threads=threads,workers=workers,cpus=cpus)


def options(mode,threads):
    plan(mode,threads,1,8)
    return ['-mt'] if mode=='classic' else ['+aps','+mt='+str(threads)]


def log_audit(text,mode,threads):
    reported=re.findall(r'Multithreading\s+Enabled\s*:\s*(\d+)\s+threads?',text,re.I)
    disabled=[s.strip() for s in text.splitlines() if re.search(r'multi.?thread',s,re.I) and re.search(r'disabled|too small',s,re.I)]
    return dict(requested_mode=mode,requested_threads=threads,
        reported_threads=int(reported[-1]) if reported else (1 if disabled or mode=='classic' else None),
        multithreading_disabled_lines=disabled,
        aps_log_lines=[s.strip() for s in text.splitlines() if re.search(r'\bAPS\b',s,re.I)][:20],
        note='Requested threads are not proof of actual thread use; unknown reported count stays null')


def speed_report(records,cpus):
    rows=[]
    for r in records:
        p=r['setting']['solver'];elapsed=r.get('simulator_elapsed_s')
        # A completed, noise-enabled transient is required; timeout/license failure is not a speedup.
        ok=r['status']=='COMPLETED_REVIEW_REQUIRED' and elapsed is not None and elapsed>0
        workers=cpus//p['threads']
        rows.append(dict(case=r['case'],mode=p['mode'],threads=p['threads'],workers=workers,
            status=r['status'],measured_case_wall_s=elapsed,
            projected_three_case_batch_s=math.ceil(3/workers)*elapsed if ok else None,
            projected_six_case_batch_s=math.ceil(6/workers)*elapsed if ok else None,
            solver_audit=r.get('solver_audit'),metrics=r.get('metrics')))
    valid=[r for r in rows if r['projected_six_case_batch_s'] is not None]
    best=min(valid,key=lambda r:(r['projected_six_case_batch_s'],r['threads'])) if valid else None
    return dict(status='SPEED_SCREEN_REVIEW_REQUIRED' if best else 'NO_COMPLETED_SPEED_CASE',
        cases=rows,recommended_plan=plan(best['mode'],best['threads'],best['workers'],cpus) if best else None,
        recommendation_command=('STUDY_SOLVER={mode} STUDY_THREADS={threads} STUDY_WORKERS={workers} bash submit.sh pilot'.format(**best)) if best else None,
        evidence='One 3ms run per configuration, sequential inside one allocation; batch times are projections, not measured concurrent throughput or numerical-equivalence proof',
        next='Run full pilot in the recommended mode. APS versus classic statistical screen must pass before calibration. No automatic next job.')
