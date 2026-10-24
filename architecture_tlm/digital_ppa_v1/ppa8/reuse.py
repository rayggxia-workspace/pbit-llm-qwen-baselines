"""Read-only v1 checkpoint reuse: verify provenance, never mutate the parent run."""
import json
from pathlib import Path
import shutil
from package import sha

V1_MANIFEST = '0d5317a608af67af34437c36ddd03d4c1f8177b707523a068e8f3218f89a88fc'


def checkpoint(folder, required):
    rec = json.loads((folder/'STAGE_COMPLETE.json').read_text())
    if not set(required).issubset(rec):
        raise ValueError('Missing checkpoint output '+str(folder))
    for name, digest in rec.items():
        p = (folder/name).resolve()
        if folder.resolve() not in p.parents or sha(p) != digest:
            raise ValueError('Changed/unsafe checkpoint '+str(p))
    return sha(folder/'STAGE_COMPLETE.json')


def validate(parent, cfg, source, cases):
    if not (parent/'FLOW_COMPLETE').is_file():
        raise ValueError('Reuse requires completed v1 parent')
    old = json.loads((parent/'configuration.json').read_text())
    if sha(parent/'source_manifest.json') != V1_MANIFEST or old['source_manifest_sha256'] != V1_MANIFEST:
        raise ValueError('Only the verified v1 snapshot may be reused')
    for key in ('kind','corner','clock_MHz','voltage_V','temperature_C','std_db_sha256','std_model_sha256',
                'setup_uncertainty_ns','hold_uncertainty_ns','input_slew_ns','output_load_pF','method'):
        if old[key] != cfg[key]:
            raise ValueError('Reuse configuration/library mismatch: '+key)
    previous = json.loads((parent/'source_manifest.json').read_text())['files']
    current = json.loads((source/'package_manifest.json').read_text())['files']
    frozen = [n for n in previous if n.startswith(('rtl/','conversion/','vectors/','reference/')) or
              n in ('dc.tcl','common.tcl','library_conditions.tcl','tb.sv','wave.py')]
    for name in frozen:
        if current.get(name) != previous[name]:
            raise ValueError('RTL/constraints/stimulus changed; cannot reuse '+name)
    checks = {'dc': checkpoint(parent/'dc', ['mapped.v','mapped.sdc','mapped.ddc','SYNTH_COMPLETE'])}
    for m in cases:
        req = ['FUNCTION_PASS','counts.txt','workload.json','simulation.log']
        if m['mode'] != 'stress':
            req += ['window.vcd','wave_audit.json']
        sim = parent/'gate'/m['name']
        checks['gate/'+m['name']] = checkpoint(sim, req)
        if json.loads((sim/'workload.json').read_text()) != m:
            raise ValueError('Changed workload '+m['name'])
        expected = 'DIGITAL_PPA_PASS inputs={} outputs={}'.format(m['inputs'], m['outputs'])
        if expected not in (sim/'simulation.log').read_text():
            raise ValueError('Parent functional check missing')
    return dict(parent=str(parent), parent_configuration_sha256=sha(parent/'configuration.json'),
                parent_manifest_sha256=V1_MANIFEST, checked_stages=checks, frozen_source_files=len(frozen),
                mapped_v_sha256=sha(parent/'dc/mapped.v'), mapped_sdc_sha256=sha(parent/'dc/mapped.sdc'),
                dc_vcs_rerun=False)


def copy_reports(parent, work, cases, provenance):
    (work/'dc').mkdir(exist_ok=True)
    for p in (parent/'dc').iterdir():
        if p.is_file() and p.name != 'STAGE_COMPLETE.json' and (p.suffix in ('.rpt','.tsv','.sdc','.txt') or p.name=='SYNTH_COMPLETE'):
            shutil.copyfile(str(p), str(work/'dc'/p.name))
    for m in cases:
        dest = work/'gate'/m['name']
        dest.mkdir(parents=True, exist_ok=True)
        for name in ('FUNCTION_PASS','counts.txt','workload.json','simulation.log','wave_audit.json'):
            src = parent/'gate'/m['name']/name
            if src.is_file():
                shutil.copyfile(str(src),str(dest/name))
    (work/'REUSE_PROVENANCE.json').write_text(json.dumps(provenance,indent=2)+'\n')
