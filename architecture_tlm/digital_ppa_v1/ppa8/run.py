"""DC -> zero-delay VCS scoreboard -> per-window PT, hash-checked restart."""
import argparse
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from package import verify, sha, RELEASE, KINDS
from wave import clip
from analyze import summarize
from scalar_vcd import scalarize, verify_pt
from reuse import validate as validate_reuse, copy_reports

SOURCE = Path(__file__).resolve().parent


def command(args, cwd, log, env):
    print('RUN '+str(cwd)+' '+str(args[0]), flush=True)
    with (cwd/log).open('w') as f:
        f.write('COMMAND '+json.dumps([str(x) for x in args])+'\n')
        f.flush()
        rc = subprocess.call([str(x) for x in args], cwd=str(cwd), env=env, stdout=f, stderr=subprocess.STDOUT)
    text = (cwd/log).read_text(errors='replace')
    if rc or re.search(r'^\s*(Error:|Error-|Fatal:)', text, re.M):
        print('\n'.join(text.splitlines()[-60:]), flush=True)
        raise RuntimeError('Command failure: '+str(cwd/log))


def stage(folder, required, action):
    marker = folder/'STAGE_COMPLETE.json'
    if marker.is_file():
        record = json.loads(marker.read_text())
        if not set(required).issubset(record):
            raise ValueError('Incomplete checkpoint '+str(folder))
        for n, h in record.items():
            if sha(folder/n) != h:
                raise ValueError('Changed checkpoint '+str(folder/n))
        print('REUSE '+str(folder), flush=True)
        return
    if folder.exists():
        folder.rename(folder.with_name(folder.name+'.failed-'+str(int(time.time()*1e6))))
    folder.mkdir(parents=True)
    action()
    for n in required:
        if not (folder/n).is_file():
            raise ValueError('Missing stage output '+str(folder/n))
    # Compiled executable needs its sidecar directory; hash it too.
    record = {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob('*') if p.is_file()}
    marker.write_text(json.dumps(record, indent=2)+'\n')


def compile_gate(dc, build, env):
    def sv_path(x):
        return '.'.join(p if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*', p) else '\\'+p+' ' for p in x.split('/'))
    scopes = ['']+(dc/'hierarchy.txt').read_text().splitlines()
    (build/'dump_scopes.svh').write_text('\n'.join('$dumpvars(1,dut'+('.'+sv_path(x) if x else '')+');' for x in scopes)+'\n')
    command(['vcs', '-full64', '-sverilog', '-top', 'tb_ppa', '+define+GATE',
        '+define+functional', '+notimingcheck', '+delay_mode_zero', '-timescale=1ns/1ps',
        '+incdir+'+str(build), SOURCE/'tb.sv', dc/'mapped.v', env['STD_MODEL'], '-o', 'simv'], build, 'compile.log', env)


def simulate(meta, sim, build, env, dc):
    with gzip.open(str(SOURCE/'vectors'/(meta['name']+'.hex.gz')), 'rb') as f:
        (sim/'vectors.hex').write_bytes(f.read())
    gold = SOURCE/'vectors'/(meta['name']+'.gold')
    if sha(gold) != meta['gold_sha256']:
        raise ValueError('Expected-output SHA mismatch')
    command([build/'simv', '+VECTORS='+str(sim/'vectors.hex'), '+GOLD='+str(gold),
        '+ROWS='+str(meta['rows']), '+OUTPUTS='+str(meta['outputs']), '+VCD='+str(sim/'full.vcd')], sim, 'simulation.log', env)
    expected = 'DIGITAL_PPA_PASS inputs={} outputs={}'.format(meta['inputs'], meta['outputs'])
    if expected not in (sim/'simulation.log').read_text():
        raise ValueError('No scoreboard PASS')
    measured = dict(x.split('=') for x in (sim/'counts.txt').read_text().splitlines())
    if any(int(measured[k]) != meta[k] for k in ('inputs', 'outputs')):
        raise ValueError('Operation counts mismatch')
    (sim/'workload.json').write_text(json.dumps(meta, indent=2)+'\n')
    if meta['mode'] != 'stress':
        start = 50 if meta['mode'] != 'idle' else 50+10*meta['idle_start_row']
        end = 50+10*(meta['rows']+16)
        audit = clip(sim/'full.vcd', sim/'window.vcd', start, end)
        (sim/'wave_audit.json').write_text(json.dumps(audit, indent=2)+'\n')
        expected_scopes = 1+len((dc/'hierarchy.txt').read_text().splitlines())
        if audit['xz_signals'] or 'tb_ppa/dut' not in audit['variable_scopes'] or len(audit['variable_scopes']) < expected_scopes:
            raise ValueError('X/Z or incomplete hierarchy: '+str(sim/'wave_audit.json'))
    (sim/'FUNCTION_PASS').write_text(expected+'\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--kind', type=int, choices=KINDS, required=True)
    ap.add_argument('--corner', choices=('ss', 'tt'), required=True)
    ap.add_argument('--reuse-from', type=Path)
    a = ap.parse_args()
    verify()
    work = a.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PPA_SOURCE=str(SOURCE), PPA_KIND=str(a.kind), PPA_CORNER=a.corner)
    cfg = dict(release=RELEASE, kind=a.kind, corner=a.corner, clock_MHz=100,
        voltage_V=1.08 if a.corner == 'ss' else 1.2, temperature_C=125 if a.corner == 'ss' else 25,
        source_manifest_sha256=sha(SOURCE/'package_manifest.json'),
        std_db=env['STD_DB'], std_db_sha256=sha(Path(env['STD_DB'])),
        std_model=env['STD_MODEL'], std_model_sha256=sha(Path(env['STD_MODEL'])),
        method='PRELAYOUT_ZERO_DELAY_GATE_VCD_AVERAGED_PT_NO_SDF_NO_SPEF_NO_CTS',
        setup_uncertainty_ns=2., hold_uncertainty_ns=.1, input_slew_ns=.1, output_load_pF=.02,
        activity_mode='scalar_vcd_bit_checked_v2',
        tool_paths={t: shutil.which(t) for t in ('dc_shell', 'vcs', 'pt_shell')})
    cases = [m for m in json.loads((SOURCE/'vectors/cases.json').read_text()) if m['kind'] == a.kind]
    cases.sort(key=lambda m: (m['mode'] != 'stress', m['name']))
    parent = a.reuse_from.resolve() if a.reuse_from else None
    if parent:
        if parent == work or parent in work.parents or work in parent.parents:
            raise ValueError('Recheck output must be separate from parent')
        provenance = validate_reuse(parent, cfg, SOURCE, cases)
        cfg['reuse_parent'] = str(parent)
        cfg['reuse_provenance'] = provenance
    cp = work/'configuration.json'
    if cp.exists() and json.loads(cp.read_text()) != cfg:
        raise ValueError('Source/library/config changed: start a NEW run directory')
    cp.write_text(json.dumps(cfg, indent=2)+'\n')
    shutil.copyfile(str(SOURCE/'package_manifest.json'), str(work/'source_manifest.json'))
    dc, build = work/'dc', work/'build'
    if parent:
        copy_reports(parent, work, cases, provenance)
        dc = parent/'dc'
        print('REUSE VERIFIED DC/VCS '+str(parent), flush=True)
    else:
        stage(dc, ['mapped.v', 'mapped.sdc', 'mapped.ddc', 'inventory.tsv', 'hierarchy.txt', 'SYNTH_COMPLETE'],
              lambda: command(['dc_shell', '-f', SOURCE/'dc.tcl'], dc, 'dc.log', env))
        stage(build, ['simv', 'dump_scopes.svh'], lambda: compile_gate(dc, build, env))
    for meta in cases:
        sim = work/'gate'/meta['name']
        required = ['FUNCTION_PASS', 'counts.txt', 'workload.json', 'simulation.log']
        if meta['mode'] != 'stress':
            required += ['window.vcd', 'wave_audit.json']
        if not parent:
            stage(sim, required, lambda: simulate(meta, sim, build, env, dc))
        if meta['mode'] == 'stress':
            continue
        raw = (parent/'gate'/meta['name'] if parent else sim)/'window.vcd'
        activity = work/'activity'/meta['name']
        def prepare():
            audit = scalarize(raw, activity/'scalar.vcd', a.kind)
            if abs(audit['duration_ns']-json.loads((sim/'wave_audit.json').read_text())['duration_ns'])>1e-6:
                raise ValueError('Changed window duration')
            (activity/'scalar_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
        stage(activity, ['scalar.vcd','scalar_audit.json'], prepare)
        env.update(NET_DIR=str(dc), ACTIVITY_VCD=str(activity/'scalar.vcd'))
        pt = work/'power'/meta['name']
        def power():
            command(['pt_shell', '-f', SOURCE/'pt.tcl'], pt, 'pt.log', env)
            audit = verify_pt(json.loads((activity/'scalar_audit.json').read_text()), pt/'output_activity.tsv')
            (pt/'BIT_ACTIVITY_PASS.json').write_text(json.dumps(audit,indent=2)+'\n')
        stage(pt, ['POWER_CALCULATED', 'power.rpt', 'cells.rpt', 'inventory.tsv', 'activity.rpt',
                   'ranges.rpt','output_activity.tsv','BIT_ACTIVITY_PASS.json'], power)
        summarize(work)
    if len(summarize(work)) != 9:
        raise ValueError('Expected nine power windows')
    (work/'FLOW_COMPLETE').write_text('All steps done. Review timing/coverage flags, not silicon signoff.\n')


if __name__ == '__main__':
    main()
