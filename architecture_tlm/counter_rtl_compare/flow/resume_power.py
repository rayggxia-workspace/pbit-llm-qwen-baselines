"""Read old successful DC/VCS artifacts; audit X/Z and calculate PT in a NEW root."""
import argparse
import json
import os
import re
import subprocess
import tarfile
import time
from pathlib import Path
from scalar_vcd import digest, verify_pt
from summarize import window_summary, write_csv
from xz_audit import prepare_activity, save

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ('flow/dc.tcl', 'flow/common.tcl', 'flow/library_conditions.tcl',
          'sim/tb.sv', 'sim/generate.py', 'rtl/sc_counter_a.sv',
          'rtl/sc_counter_b.sv', 'rtl/sc_counter_tile.sv', 'rtl/sc_sum_tree.sv')


def checked_inputs(old):
    manifest = json.loads((old/'EXECUTION.json').read_text())
    if manifest['release'] != 'counter_ppa_v2':
        raise ValueError('Recovery accepts verified v2 runs only')
    if manifest['package_manifest_sha256'] != '0debbfacb696238041830ebfe80aa0838db932e02558dcff641195f323818958':
        raise ValueError('Unexpected v2 source manifest')
    for rel in FROZEN:
        if digest(ROOT/rel) != manifest['sources'][rel]:
            raise ValueError('Frozen RTL/TB/synthesis source mismatch '+rel)
    required = ['dc/mapped.v', 'dc/mapped.sdc', 'dc/SYNTH_COMPLETE',
                'gate/functional/FUNCTION_PASS', 'COMMANDS.json', 'EXECUTION.json']
    for rel in required:
        if not (old/rel).is_file():
            raise ValueError('Missing reusable artifact '+rel)
    commands = json.loads((old/'COMMANDS.json').read_text())
    if not commands or any(c['rc'] != 0 for c in commands):
        raise ValueError('Original tool command failed')
    if not any(Path(c['command'][0]).name == 'dc_shell' for c in commands):
        raise ValueError('Missing completed DC command')
    if not any(Path(c['command'][0]).name == 'vcs' for c in commands):
        raise ValueError('Missing completed VCS compile')
    functional = list((old/'gate/functional').glob('command*.log'))
    if len(functional) != 1 or 'COUNTER_PASS' not in functional[0].read_text():
        raise ValueError('Missing functional oracle log')
    return manifest, required


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--old', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    old, out = args.old.resolve(), args.out.resolve()
    if not old.is_dir() or out == old or old in out.parents or out in old.parents:
        raise ValueError('Old/new directories must be separate')
    out.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env['PPA_SOURCE'] = str(ROOT/'flow')
    commands, rows = [], []

    def call(cmd, cwd, extra=None):
        e = env.copy(); e.update(extra or {})
        log = cwd/('command%d.log' % len(commands))
        start = time.time()
        with log.open('w') as stream:
            process = subprocess.run([str(v) for v in cmd], cwd=str(cwd), env=e,
                                     stdout=stream, stderr=subprocess.STDOUT)
        commands.append(dict(command=[str(v) for v in cmd], cwd=str(cwd), rc=process.returncode,
                             seconds=time.time()-start, log=str(log)))
        save(out/'COMMANDS.json', commands)
        if process.returncode:
            raise RuntimeError('Tool failed; inspect '+str(log))

    try:
        manifest, required = checked_inputs(old)
        override = 'SS_DB' if manifest['corner'] == 'ss' else 'TT_DB'
        library = Path(env.get(override) or manifest['library']['path'])
        if digest(library) != manifest['library']['sha256']:
            raise ValueError('Library SHA differs from original synthesis')
        env.update(STD_DB=str(library), PPA_CORNER=manifest['corner'])
        inputs = {rel: dict(path=str(old/rel), sha256=digest(old/rel), bytes=(old/rel).stat().st_size)
                  for rel in required}
        record = dict(release='counter_ppa_v4_power_resume', original=manifest,
                      old_result=str(old), inputs=inputs, package_manifest_sha256=digest(ROOT/'package_manifest.json'),
                      reuse='No DC/VCS rerun; original source, netlist and VCD are not modified',
                      limitation='Original v2 did not record mapped-netlist/VCD hashes; these bytes are hashed at recovery')
        save(out/'EXECUTION.json', record)
        period = manifest['period_ns']; m = manifest['m']; t = manifest['t']
        width = m*4*((64*t*128).bit_length()+1)
        for profile in manifest['profiles']:
            for seed in manifest['seeds']:
                tag = '%s_s%d' % (profile, seed)
                case = old/'gate'/tag
                if not (case/'FUNCTION_PASS').is_file():
                    raise ValueError('Missing power-simulation pass '+tag)
                logs = list(case.glob('command*.log'))
                if len(logs) != 1:
                    raise ValueError('Ambiguous simulation log '+tag)
                log = logs[0].read_text()
                if 'COUNTER_PASS' not in log:
                    raise ValueError('Power activity oracle not passed')
                begin = float(re.search(r'WINDOW_BEGIN time_ns=([\d.]+)', log).group(1))
                end = float(re.search(r'WINDOW_END time_ns=([\d.]+)', log).group(1))
                idle_end = float(re.search(r'IDLE_END time_ns=([\d.]+)', log).group(1))
                frames = int(re.search(r'WINDOW_END.*frames=(\d+)', log).group(1))
                cycles = int(re.search(r'active_cycles=(\d+)', log).group(1))
                if frames != manifest['power_frames'] or cycles != frames*(t+manifest['pipe']+3):
                    raise ValueError('Frame/cycle metadata mismatch')
                if abs(end-begin-cycles*period) > .002 or abs(idle_end-end-64*period) > .002:
                    raise ValueError('Simulation window mismatch')
                raw = case/'raw.vcd'
                if not raw.is_file():
                    raw = case/'raw.vcd.gz'
                if not raw.is_file():
                    raise ValueError('Missing original VCD '+str(raw))
                for path in (raw, logs[0], case/'FUNCTION_PASS'):
                    inputs[str(path.relative_to(old))] = dict(path=str(path), sha256=digest(path), bytes=path.stat().st_size)
                save(out/'EXECUTION.json', record)
                for label, start, stop in [('active', begin, end), ('idle', end, idle_end)]:
                    work = out/'power'/(tag+'_'+label); work.mkdir(parents=True)
                    stats = prepare_activity(raw, work, start, stop, width, old/'dc', call)
                    call(['pt_shell', '-f', ROOT/'flow/pt.tcl'], work,
                         dict(NET_DIR=str(old/'dc'), ACTIVITY_VCD=str(work/'activity.vcd')))
                    if not (work/'POWER_CALCULATED').is_file():
                        raise RuntimeError('PT did not finish')
                    save(work/'ACTIVITY_VERIFIED.json', verify_pt(stats, work/'output_activity.tsv'))
                    row = dict(profile=profile, seed=seed, window=label, duration_ns=stop-start,
                        frames=frames if label == 'active' else 0,
                        bin_outputs=frames*m*4 if label == 'active' else 0,
                        frame_cycles=cycles/frames if label == 'active' else None,
                        setup_slack_ns=float((work/'setup_slack_ns.txt').read_text()),
                        hold_slack_ns=float((work/'hold_slack_ns.txt').read_text()), reports=str(work),
                        excluded_nonfunctional_bits=stats['excluded_nonfunctional_bits'],
                        energy_instruction='E_frame_pJ = total_power_uW * duration_ns / (1000 * completed_frames)')
                    save(work/'WINDOW.json', row)
                    row.update(window_summary(work, row)); rows.append(row)
                    save(out/'PARTIAL_SUMMARY.json', rows); write_csv(out, rows)
        # Detect old results changing during recovery before declaring completion.
        if any(digest(Path(v['path'])) != v['sha256'] for v in inputs.values()):
            raise RuntimeError('Original artifacts changed during recovery')
        save(out/'SUMMARY.json', dict(status='POWER_CALCULATED_REVIEW_WARNINGS_AND_STA', config=record, windows=rows))
        (out/'FLOW_COMPLETE').write_text('PT finished; review STA, coverage and warnings separately.\n')
    except Exception as error:
        import traceback
        (out/'failure.txt').write_text(str(error)+'\n'+traceback.format_exc())
        raise
    finally:
        files = [p for p in out.rglob('*') if p.is_file() and
                 (p.suffix in ('.json','.log','.rpt','.txt','.tsv','.csv') or p.name in
                  ('FLOW_COMPLETE','POWER_CALCULATED','XZ_PROBE_COMPLETE'))]
        save(out/'RESULT_INDEX.json', {str(p.relative_to(out)).replace('\\','/'):dict(bytes=p.stat().st_size, sha256=digest(p)) for p in files})
        with tarfile.open(str(out)+'_reports.tar.gz', 'w:gz') as tar:
            for p in files+[out/'RESULT_INDEX.json']:
                tar.add(str(p), arcname=out.name+'/'+str(p.relative_to(out)).replace('\\','/'))


if __name__ == '__main__':
    main()
