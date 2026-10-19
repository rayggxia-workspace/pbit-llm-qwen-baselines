"""DC -> checked zero-delay VCS -> PT PX. Python 3.6, no third-party modules."""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import time
from vectors import generate
from wave import clip
from analyze import summarize
from package import verify

SOURCE = pathlib.Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def command(args, cwd, log, env):
    with (cwd / log).open('w') as f:
        f.write('COMMAND ' + json.dumps([str(x) for x in args]) + '\n')
        f.flush()
        rc = subprocess.call([str(x) for x in args], cwd=str(cwd), env=env, stdout=f, stderr=subprocess.STDOUT)
    if rc:
        raise RuntimeError('Exit {}: {}'.format(rc, cwd / log))


def stage(folder, required, action):
    """Never reuse unverified partial output or silently replace a previous run."""
    marker = folder / 'STAGE_COMPLETE.json'
    if marker.exists():
        recorded = json.loads(marker.read_text())
        if any(not (folder / p).is_file() or sha(folder / p) != value for p, value in recorded.items()):
            raise RuntimeError('Checkpoint changed: ' + str(folder))
        if not set(required).issubset(recorded):
            raise RuntimeError('Checkpoint lacks required outputs')
        print('REUSE ' + str(folder), flush=True)
        return
    if folder.exists():
        folder.rename(folder.with_name(folder.name + '.failed-' + str(time.time_ns() if hasattr(time, 'time_ns') else int(time.time()*1e6))))
    folder.mkdir(parents=True)
    action()
    for item in required:
        if not (folder / item).is_file():
            raise RuntimeError('Missing output: ' + str(folder / item))
    hashes = {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob('*') if p.is_file()}
    marker.write_text(json.dumps(hashes, indent=2) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--cycles', type=int, default=4096)
    args = ap.parse_args()
    verify(SOURCE)
    work = pathlib.Path(args.work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, EP_SOURCE=str(SOURCE), EDA_CORES=os.environ.get('SLURM_CPUS_PER_TASK', '4'))
    for tool in ('dc_shell', 'vcs', 'pt_shell'):
        if not shutil.which(tool):
            raise RuntimeError('Missing tool: ' + tool)
    cases = [(p, m, s) for p in ('full', 'central') for m in ('active', 'burst', 'idle') for s in (20261017, 7, 1234567)]
    names = ['{}_{}_{}'.format(*c) for c in cases]
    config = dict(release='epilogue_ppa100_v1', source_manifest_sha256=sha(SOURCE/'package_manifest.json'),
                  pvt=env['PVT'], std_db=env['STD_DB'], std_db_sha256=sha(env['STD_DB']),
                  std_model=env['STD_MODEL'], std_model_sha256=sha(env['STD_MODEL']),
                  cycles=args.cycles, cases=names, clock_MHz=100, setup_uncertainty_ns=2.0,
                  hold_uncertainty_ns=.1, load_pf=.02, mode='prelayout_zero_delay_no_clock_tree',
                  tools={t: shutil.which(t) for t in ('dc_shell', 'vcs', 'pt_shell')})
    cp = work / 'configuration.json'
    if cp.exists() and json.loads(cp.read_text()) != config:
        raise RuntimeError('Configuration/source/library changed. Use a new work directory.')
    cp.write_text(json.dumps(config, indent=2) + '\n')
    command([os.sys.executable, SOURCE/'generate_lut.py', '--check'], work, 'lut_check.log', env)
    dc = work / 'dc'
    stage(dc, ['mapped.v', 'mapped.sdc', 'mapped.ddc', 'SYNTH_COMPLETE', 'inventory.tsv'],
          lambda: command(['dc_shell', '-f', SOURCE/'ppa/dc.tcl'], dc, 'dc.log', env))
    env['NET_DIR'] = str(dc)
    build = work / 'build'
    stage(build, ['simv'], lambda: command(['vcs', '-full64', '-sverilog', '-top', 'tb_epilogue_power',
          '+define+functional', '+notimingcheck', '+delay_mode_zero', '-timescale=1ns/1ps',
          SOURCE/'ppa/tb.sv', dc/'mapped.v', env['STD_MODEL'], '-o', 'simv'], build, 'compile.log', env))
    for index, ((profile, mode, seed), name) in enumerate(zip(cases, names)):
        sim = work / 'gate' / name
        def simulate():
            meta = generate(sim, profile, mode, seed, args.cycles)
            command([build/'simv', '+VECTORS='+str(sim/'vectors.txt'), '+WAVE='+str(sim/'activity.vcd'),
                     '+ROWS='+str(meta['rows']), '+WARMUP='+str(meta['warmup_cycles']),
                     '+EXPECTED='+str(meta['produced'])], sim, 'simulation.log', env)
            if 'EPILOGUE_PASS ' not in (sim/'simulation.log').read_text():
                raise RuntimeError('Missing simulation PASS: ' + name)
            audit = clip(sim/'activity.vcd', sim/'active.vcd', meta['start_ns'], meta['end_ns'])
            (sim/'wave_audit.json').write_text(json.dumps(audit, indent=2)+'\n')
            if audit['xz_signals']:
                raise RuntimeError('X/Z found in measurement window: ' + name)
        stage(sim, ['active.vcd', 'simulation.log', 'workload.json', 'wave_audit.json'], simulate)
        env['SIM_DIR'] = str(sim)
        pt = work / 'power' / name
        stage(pt, ['POWER_CALCULATED', 'power.rpt', 'cells.rpt', 'activity.rpt', 'inventory.tsv'],
              lambda: command(['pt_shell', '-f', SOURCE/'ppa/pt.tcl'], pt, 'pt.log', env))
        summarize(work, names[:index+1])
    summarize(work, names)
    (work/'FLOW_COMPLETE').write_text('Calculated 18 windows. Review timing, coverage and power checks; not signoff.\n')
    print('FLOW_COMPLETE ' + str(work), flush=True)


if __name__ == '__main__':
    main()
