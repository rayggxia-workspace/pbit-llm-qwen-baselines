"""Small evidence archive only; leave large restart data in the result directory."""
import json
from pathlib import Path
import sys
import tarfile
from package import sha


def collect(work):
    files = [p for p in sorted(work.rglob('*')) if p.is_file()
             and 'build' not in p.relative_to(work).parts
             and (p.suffix in ('.json', '.csv', '.rpt', '.log', '.txt', '.tsv', '.sdc')
                  or p.name in ('FUNCTION_PASS', 'POWER_CALCULATED', 'SYNTH_COMPLETE', 'FLOW_COMPLETE'))]
    record = {p.relative_to(work).as_posix(): dict(sha256=sha(p), bytes=p.stat().st_size) for p in files}
    record['stage_status'] = dict(flow_complete=(work/'FLOW_COMPLETE').exists(),
        dc=(work/'dc/SYNTH_COMPLETE').exists(),
        functional_passes=len(list((work/'gate').glob('*/FUNCTION_PASS'))),
        power_calculated=len(list((work/'power').glob('*/POWER_CALCULATED'))))
    buildlog = work/'build/compile.log'
    if buildlog.exists():
        files.append(buildlog)
        record['build/compile.log'] = dict(sha256=sha(buildlog), bytes=buildlog.stat().st_size)
    index = work/'RESULT_INDEX.json'
    # Never hash the previous index into its own successor.
    files = [p for p in files if p != index]
    record.pop('RESULT_INDEX.json', None)
    index.write_text(json.dumps(record, indent=2)+'\n')
    dest = work.parent/(work.name+'_reports.tar.gz')
    tmp = dest.with_suffix('.tmp')
    with tarfile.open(str(tmp), 'w:gz') as t:
        for p in files+[index]:
            t.add(str(p), arcname=work.name+'/'+p.relative_to(work).as_posix())
    tmp.replace(dest)
    print('RESULT_ARCHIVE={} SHA256={}'.format(dest, sha(dest)), flush=True)


if __name__ == '__main__':
    collect(Path(sys.argv[1]).resolve())
