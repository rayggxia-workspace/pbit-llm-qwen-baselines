"""Local port-level functional/infrastructure checks; no DC/PT claims."""
import argparse
import ast
import json
import pathlib
import subprocess
import tempfile
import tkinter
from vectors import generate
from wave import clip
from analyze import totals, coverage, summarize
from run import stage
from cell_report_parser import rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--iverilog', required=True)
    ap.add_argument('--vvp', required=True)
    ap.add_argument('--ivl-lib', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    out = pathlib.Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    for p in (root/'ppa').glob('*.py'):
        ast.parse(p.read_text(), feature_version=(3, 6))
    tcl = tkinter.Tcl()
    for p in (root/'ppa').glob('*.tcl'):
        assert int(tcl.call('info', 'complete', p.read_text())), p
    exe = out/'simulation.vvp'
    subprocess.check_call([str(pathlib.Path(args.iverilog)), '-B', str(pathlib.Path(args.ivl_lib)), '-g2012', '-I', str(root),
                           '-s', 'tb_epilogue_power', '-o', str(exe), str(root/'ppa/tb.sv'),
                           str(root/'swiglu_epilogue_q10.sv')])
    results = []
    for profile in ('full', 'central'):
        for mode in ('active', 'burst', 'idle'):
            for seed in (20261017, 7, 1234567):
                folder = out/'{}_{}_{}'.format(profile, mode, seed)
                meta = generate(folder, profile, mode, seed)
                cmd = [str(pathlib.Path(args.vvp)), '-M', str(pathlib.Path(args.ivl_lib)), str(exe), '+VECTORS='+(folder/'vectors.txt').as_posix(),
                       '+WAVE='+(folder/'activity.vcd').as_posix(), '+ROWS='+str(meta['rows']),
                       '+WARMUP='+str(meta['warmup_cycles']), '+EXPECTED='+str(meta['produced'])]
                result = subprocess.check_output(cmd, universal_newlines=True)
                (folder/'simulation.log').write_text(result)
                assert 'EPILOGUE_PASS ' in result
                audit = clip(folder/'activity.vcd', folder/'active.vcd', meta['start_ns'], meta['end_ns'])
                assert audit['xz_signals'] == 0, audit
                assert meta['produced'] == {'active':4096, 'burst':1024, 'idle':0}[mode]
                if profile == 'central':
                    assert meta['sigmoid_clamped_inputs'] == 0
                results.append(dict(meta, wave_audit=audit))
    with tempfile.TemporaryDirectory(dir=str(out)) as tmp:
        tmp = pathlib.Path(tmp)
        vcd = tmp/'bad.vcd'
        vcd.write_text('$timescale 1ns $end\n$scope module dut $end\n$var wire 1 ! q $end\n$upscope $end\n$enddefinitions $end\n#0\n0!\n#5\nx!\n#10\n1!\n#20\n')
        assert clip(vcd, tmp/'cut.vcd', 1, 15)['xz_signals'] == 1
        try:
            clip(vcd, tmp/'cut.vcd', 1, 25)
            raise AssertionError('Truncation accepted')
        except ValueError:
            pass
        checkpoint = tmp/'checkpoint'
        stage(checkpoint, ['data.txt'], lambda: (checkpoint/'data.txt').write_text('known'))
        stage(checkpoint, ['data.txt'], lambda: (_ for _ in ()).throw(AssertionError('Unexpected rerun')))
        (checkpoint/'data.txt').write_text('modified')
        try:
            stage(checkpoint, ['data.txt'], lambda: None)
            raise AssertionError('Tamper accepted')
        except RuntimeError:
            pass
        text = 'Dynamic Power Units = 1mW\nLeakage Power Units = 1nW\nCell Internal Power = 2\nNet Switching Power = 3\nCell Leakage Power = 1000000\nTotal Power = 6\n'
        values, scales = totals(text)
        assert abs(values[3] - .006) < 1e-12
        assert abs(values[3]*10000*1000/1000 - 60) < 1e-12
        assert coverage('Total number of nets = 10\nNumber of annotated nets = 9\nTotal number of leaf cells = 2\nNumber of fully annotated leaf cells = 1')['net_coverage_percent'] == 90
        cells = tmp/'cells.rpt'
        cells.write_text('Cell Power Power Power Power\n-------\na_reg 2 3 1000000 6 (100.0%)\nTotals (1 cells) 2 3 1000000 6\n')
        assert list(rows(cells))[0][0] == 'a_reg'
        (tmp/'dc').mkdir()
        pt = tmp/'power/fixture'
        pt.mkdir(parents=True)
        gate = tmp/'gate/fixture'
        gate.mkdir(parents=True)
        inventory = 'name\tref\tarea\tcategory\na_reg\tDFF_9TSVT\t10\tinput_registers\n'
        (tmp/'dc/inventory.tsv').write_text(inventory)
        (pt/'inventory.tsv').write_text(inventory)
        (pt/'cells.rpt').write_text(cells.read_text())
        (pt/'power.rpt').write_text(text)
        (pt/'POWER_CALCULATED').write_text('fixture, not EDA result')
        (pt/'setup_slack_ns.txt').write_text('-0.5')
        (pt/'hold_slack_ns.txt').write_text('0.1')
        (pt/'activity.rpt').write_text('Total number of nets = 10\nNumber of annotated nets = 9\nTotal number of leaf cells = 1\nNumber of fully annotated leaf cells = 1')
        (gate/'wave_audit.json').write_text('{"xz_signals":0}')
        (gate/'workload.json').write_text('{"produced":1000,"duration_ns":10000}')
        summary = summarize(tmp, ['fixture'])
        assert summary[0]['total_pJ_per_output'] == 60
        assert summary[0]['timing_status'] == 'TIMING_VIOLATION'
        assert summary[0]['area_um2'] == 10
        (gate/'wave_audit.json').write_text('{"xz_signals":1}')
        try:
            summarize(tmp, ['fixture'])
            raise AssertionError('Unknown waveform accepted by summary')
        except ValueError:
            pass
    (out/'LOCAL_TEST.json').write_text(json.dumps(dict(status='PASS', cases=results,
        scope='Icarus RTL with gate-compatible port-only TB; syntax, units, VCD and checkpoint tests; no EDA PPA'), indent=2)+'\n')
    print('LOCAL_PASS windows=18 cycles_per_window=4096')


if __name__ == '__main__':
    main()
