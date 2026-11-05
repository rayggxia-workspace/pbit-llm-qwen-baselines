"""Prepare a frozen Slurm array; submission requires explicit --submit."""
import argparse
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import uuid

from run_case import digest, load_cases, save, snapshot


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite',choices=['smoke','all'],required=True)
    p.add_argument('--env',required=True,help='absolute user-owned environment setup file')
    p.add_argument('--corner',choices=['ss','tt'],required=True)
    p.add_argument('--output-root',required=True)
    p.add_argument('--submit',action='store_true',help='actually call sbatch; otherwise prepare only')
    p.add_argument('--with-pt-sta',action='store_true')
    p.add_argument('--timeout',type=int,default=3600)
    p.add_argument('--parallel',type=int,default=1,help='array concurrency; default one tool/license consumer')
    p.add_argument('--partition');p.add_argument('--account')
    p.add_argument('--cpus',type=int,default=4);p.add_argument('--memory',default='16G')
    p.add_argument('--time',default='03:15:00',help='Slurm allocation for three bounded stages')
    args=p.parse_args()
    if min(args.parallel,args.cpus,args.timeout)<1:p.error('Positive resources/timeouts required')
    package=Path(__file__).resolve().parents[1]
    root=Path(args.output_root).expanduser().resolve()
    if root==package or package in root.parents:p.error('Output root must be outside source package')
    environment=Path(args.env).expanduser().resolve()
    if not environment.is_file():p.error('Missing environment file')
    cases=load_cases(package)
    selected=[x['id'] for x in cases if args.suite=='all' or x['smoke']]
    if not selected:p.error('No selected cases')
    if args.suite=='smoke' and len(selected)>3:p.error('Smoke must contain at most three cases; edit cases.json deliberately')
    root.mkdir(parents=True,exist_ok=True)
    output=root/('submission_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+args.suite+'_'+uuid.uuid4().hex[:8])
    output.mkdir(exist_ok=False);(output/'slurm_logs').mkdir()
    inventory=snapshot(package,output/'source')
    save(output/'SOURCE_MANIFEST.json',dict(source_sha256=inventory))
    plan=dict(schema_version=1,suite=args.suite,case_ids=selected,corner=args.corner,
              environment_file=str(environment),environment_sha256=digest(environment),
              package=str(output/'source'),source_manifest=str(output/'SOURCE_MANIFEST.json'),
              run_output_root=str(root/'runs'),timeout=args.timeout,with_pt_sta=args.with_pt_sta)
    save(output/'PLAN.json',plan)
    script=output/'job.sh'
    command=[os.environ.get('PYTHON','python3'),str(output/'source/flow/array_entry.py'),'--plan',str(output/'PLAN.json')]
    script.write_bytes(('#!/usr/bin/env bash\nset -euo pipefail\nexec '+' '.join(shlex.quote(x) for x in command)+'\n').encode('utf-8'))
    # Four CPUs and no GPU request: synthesis/functional smoke only.
    cmd=['sbatch','--parsable','--job-name=ffn193_'+args.suite,
         '--array=0-'+str(len(selected)-1)+'%'+str(args.parallel),
         '--cpus-per-task='+str(args.cpus),'--mem='+args.memory,'--time='+args.time,
         '--output='+str(output/'slurm_logs/%A_%a.out'),
         '--error='+str(output/'slurm_logs/%A_%a.err')]
    if args.partition:cmd+=['--partition='+args.partition]
    if args.account:cmd+=['--account='+args.account]
    cmd.append(str(script))
    receipt=dict(status='prepared_only',command=cmd,plan_sha256=digest(output/'PLAN.json'),
                 job_script_sha256=digest(script),source_manifest_sha256=digest(output/'SOURCE_MANIFEST.json'),
                 jobs_not_started=True)
    if args.submit:
        if not shutil.which('sbatch'):
            receipt.update(status='submission_failed',error='sbatch not found')
        else:
            try:
                completed=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
                receipt.update(returncode=completed.returncode,stdout=completed.stdout,stderr=completed.stderr)
                job=completed.stdout.strip().split(';',1)[0]
                if completed.returncode==0 and re.fullmatch(r'[0-9]+',job):
                    receipt.update(status='submitted',slurm_job_id=job,jobs_not_started=None)
                else:receipt.update(status='submission_failed',jobs_not_started=None,
                                    error='Submission did not return a verified numeric Slurm job ID; inspect scheduler before retry')
            except (OSError,subprocess.TimeoutExpired) as exc:
                receipt.update(status='submission_failed',jobs_not_started=None,
                               error=str(exc),outcome_unknown=True)
    save(output/'SUBMISSION.json',receipt)
    print(json.dumps(dict(status=receipt['status'],submission=str(output),case_ids=selected),ensure_ascii=False))
    return 2 if receipt['status']=='submission_failed' else 0


if __name__=='__main__':raise SystemExit(main())
