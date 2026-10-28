"""Verify a frozen array plan, then invoke exactly its selected case."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import uuid
from datetime import datetime, timezone
from run_case import digest, save, source_inventory


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True)
    args=p.parse_args()
    plan_path=Path(args.plan).resolve()
    receipt=dict(status='failed',array_task_id=os.environ.get('SLURM_ARRAY_TASK_ID'),
                 job_id=os.environ.get('SLURM_JOB_ID'),time_utc=datetime.now(timezone.utc).isoformat())
    code=2
    try:
        plan=json.loads(plan_path.read_text(encoding='utf-8'))
        index=int(os.environ['SLURM_ARRAY_TASK_ID'])
        if not 0<=index<len(plan['case_ids']):raise ValueError('Array index outside frozen plan')
        receipt['case_id']=plan['case_ids'][index]
        manifest=json.loads(Path(plan['source_manifest']).read_text(encoding='utf-8'))
        if source_inventory(plan['package'])!=manifest['source_sha256']:raise ValueError('Frozen source changed before job')
        if digest(plan['environment_file'])!=plan['environment_sha256']:raise ValueError('Environment setup changed after submission; prepare a new submission')
        command=['bash',str(Path(plan['package'])/'flow/run_case.sh'),'--env',plan['environment_file'],
                 '--case-id',plan['case_ids'][index],'--corner',plan['corner'],
                 '--output-root',plan['run_output_root'],'--timeout',str(plan['timeout'])]
        if plan['with_pt_sta']:command.append('--with-pt-sta')
        code=subprocess.call(command)
        receipt.update(returncode=code,status={0:'met',3:'not_met'}.get(code,'failed'))
    except Exception as exc:
        receipt['error']=str(exc)
    finally:
        receipt_path=plan_path.parent/('ARRAY_RECEIPT_'+uuid.uuid4().hex+'.json')
        save(receipt_path,receipt)
        print(json.dumps(dict(receipt=str(receipt_path),status=receipt['status'])))
    return code


if __name__=='__main__':raise SystemExit(main())
