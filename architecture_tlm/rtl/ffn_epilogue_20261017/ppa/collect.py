"""Package diagnostic reports only. Keep VCD/netlist/checkpoints on the server."""
import hashlib
import json
import pathlib
import sys
import tarfile

work = pathlib.Path(sys.argv[1]).resolve()
paths = [p for p in work.rglob('*') if p.is_file() and
         not any(s in ('csrc', 'WORK', 'alib-52') or s.endswith('.daidir') for s in p.relative_to(work).parts) and
         (p.suffix in ('.log', '.rpt', '.json', '.txt', '.csv', '.tsv', '.sdc') or p.name in ('FLOW_COMPLETE', 'SYNTH_COMPLETE', 'POWER_CALCULATED'))]
manifest = {p.relative_to(work).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
with tarfile.open(str(work)+'.reports.tar.gz', 'w:gz') as archive:
    for p in paths:
        archive.add(str(p), arcname=work.name+'/'+p.relative_to(work).as_posix())
    payload = json.dumps(manifest, indent=2).encode('ascii')
    import io
    entry = tarfile.TarInfo(work.name+'/REPORT_SHA256.json')
    entry.size = len(payload)
    archive.addfile(entry, io.BytesIO(payload))
print('REPORT_ARCHIVE='+str(work)+'.reports.tar.gz')
