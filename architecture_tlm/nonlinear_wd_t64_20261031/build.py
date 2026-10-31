"""T64 g/u->nonlinearity->fixed Wd; preserve frozen T32 inputs and flow."""
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import shutil
import zipfile

P = Path(__file__).resolve().parent
OLD = P.parent / 'nonlinear_wd_shared32_20261031'
SEEDS = (17, 503, 1009)
SOURCE_BASE = '7b29980899059d0b398465e6753d51a49b3f7285'


def save(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def replace_one(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def main():
    if (P / 'EXECUTION_MANIFEST.json').exists():
        raise RuntimeError('Frozen execution snapshot; create another version')
    for name in ('rtl', 'flow', 'benches'):
        (P / name).mkdir(exist_ok=True)
    for name in ('codecs.sv', 'compare.sv', 'sigmoid.sv', 'primitives.sv', 'icg.sv'):
        shutil.copyfile(OLD / 'rtl' / name, P / 'rtl' / name)
    for src in (OLD / 'flow').iterdir():
        if src.is_file() and src.suffix in ('.py', '.tcl'):
            shutil.copyfile(src, P / 'flow' / src.name)
    shutil.copyfile(OLD / 'job.sh', P / 'job.sh')
    rtl = (OLD / 'rtl/integrated.sv').read_text()
    rtl = replace_one(rtl, 'module ns_integrated #(', 'module nt_integrated #(')
    rtl = replace_one(rtl, 'WEIGHTED=0,SHARE=0,GATE=0)', 'WEIGHTED=0,SHARE=0,GATE=0,T=64)')
    rtl = replace_one(rtl, 'localparam S=2*B+24,WO=64*S,TAIL=WO+M*512;',
                      'localparam S=2*B+24,WO=64*S,TAIL=WO+M*512,LOGT=$clog2(T),AW=14+LOGT;')
    rtl = replace_one(rtl, "eg+eu+ew-8'sd5", 'eg+eu+ew-LOGT')
    rtl = replace_one(rtl, 'reg [4:0] accepted;reg done;', 'reg [LOGT-1:0] accepted;reg done;')
    rtl = replace_one(rtl, 'if(accepted==31)', 'if(accepted==T-1)')
    rtl = replace_one(rtl, 'wire signed[18:0] count;', 'wire signed[AW-1:0] count;')
    rtl = replace_one(rtl, 'aw_acc #(.B(19),.D(14),.SAT(0))', 'aw_acc #(.B(AW),.D(14),.SAT(0))')
    rtl = replace_one(rtl, '{{13{count[18]}},count}', '{{(32-AW){count[AW-1]}},count}')
    (P / 'rtl/integrated.sv').write_bytes(rtl.encode())
    # The small delivered source ZIP contains the self-contained old integer oracle.
    with zipfile.ZipFile(OLD / 'results/SOURCE_CODE.zip') as z:
        legacy = z.read('legacy_vectors.py').decode().split('\ndef main():', 1)[0]
    (P / 'reference_t32_vectors.py').write_bytes(legacy.encode())
    vectors = legacy.replace('range(32)', 'range(64)')
    vectors = vectors.replace('done=accepted==32', 'done=accepted==64')
    vectors = vectors.replace("frame['ew']-5", "frame['ew']-6")
    vectors = vectors.replace('add(f,dw,31,0)', 'add(f,dw,63,1)')
    vectors = vectors.replace('add(f,w,31,0,', 'add(f,w,63,0,')
    vectors = vectors.replace("mode='replay32'", "mode='replay64'")
    vectors = vectors.replace('samples=256', 'samples=512').replace('cycles_per_frame=34', 'cycles_per_frame=66')
    # 64 Cartesian cells:4 g strata x4 Sigmoid strata x4 u strata.
    vectors = vectors.replace('rg=((t//8)%4)*64', 'rg=((t//16)%4)*64')
    vectors = vectors.replace('rs=((t//4)%2)*128+rng.randrange(128)', 'rs=((t//4)%4)*64+rng.randrange(64)')
    vectors = vectors.replace('across32 samples', 'across64 samples').replace('Cartesian4x2x4', 'Cartesian4x4x4')
    (P / 'vectors.py').write_bytes(vectors.encode())
    spec = importlib.util.spec_from_file_location('t64_vectors', P / 'vectors.py')
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    v.ROOT = P
    cases, tops, equivalence = [], [], []
    old_zip = P.parents[3] / 'project_archives/shared_sigmoid204_20261031/nsig204_v1_20261031.zip'
    with zipfile.ZipFile(old_zip) as frozen:
        for backend, weighted, cw in [('weighted', 1, 14), ('or4s10', 0, 10), ('or4s9', 0, 9)]:
            for kind, shared, icg in [('full', 0, 0), ('share_ce', 1, 0), ('share_icg', 1, 1)]:
                if backend == 'or4s9' and kind == 'share_ce':
                    continue
                name = 'g8_' + backend + '_' + kind
                c = dict(name=name, top='nt_' + name, bits=8, or4=0 if weighted else 1,
                         cw=cw, sat=0 if weighted else 1, M=8, din_bits=6669, dout_bits=265,
                         weighted_sum=bool(weighted), shared=shared, icg=icg,
                         probability_register_bits=512 if shared else 0, comparator_width=8,
                         T=64, temporal_counter_bits=20 if weighted else cw,
                         cycles_per_frame=98 if shared else 66, family='nonlinear_Wd_T64')
                ns = []
                for seed in SEEDS:
                    v.fixtures(c, seed)
                    folder = P / 'fixtures' / name / str(seed)
                    old_rows = (folder / 'stim.hex').read_text().splitlines()
                    old_expected = (folder / 'expect.hex').read_text().splitlines()
                    w = json.loads((folder / 'WINDOWS.json').read_text())
                    # g/u/scale and fixed W must match all8 old power frames.
                    ow = json.loads(frozen.read('nsig204_v1_20261031/fixtures/g8_weighted_full/' + str(seed) + '/WINDOWS.json'))
                    old_lines = frozen.read('nsig204_v1_20261031/fixtures/g8_weighted_full/' + str(seed) + '/stim.hex').decode().splitlines()
                    base_start = round((next(a for a in ow['windows'] if a['mode'] == 'replay32')['start_ns'] - 10) / 10)
                    new_start = round((next(a for a in w['windows'] if a['mode'] == 'replay64')['start_ns'] - 10) / 10)
                    static_mask = sum(65535 << (40 * n) for n in range(64))
                    static_mask |= ((1 << 4109) - 1) << 2560
                    for frame in range(8):
                        a = int(old_lines[base_start + frame * 34], 16) & static_mask
                        b = int(old_rows[new_start + frame * 66], 16) & static_mask
                        assert a == b, (name, seed, frame)
                    equivalence.append(dict(case=name, seed=seed, matched_power_frames=8))
                    rows, expected, index_map = [], [], {0: 0}
                    clear_bit, di = 6668, 6669
                    for i, (line, ex) in enumerate(zip(old_rows, old_expected)):
                        value = int(line, 16)
                        rows.append(line)
                        expected.append(ex)
                        if shared and value >> (di + 1) & 1 and value >> clear_bit & 1:
                            prep = value & ~(1 << clear_bit) & ~(1 << di)
                            rows.extend([format(prep, '01668x')] * 32)
                            expected.extend(['0' * 67] * 32)
                        index_map[i + 1] = len(rows)
                    active_start = None
                    for window in w['windows']:
                        start = round((window['start_ns'] - 10) / 10)
                        end = round((window['end_ns'] - 10) / 10)
                        window.update(start_ns=10 + 10 * index_map[start], end_ns=10 + 10 * index_map[end])
                        if window['mode'] == 'replay64':
                            active_start = index_map[start]
                            window['cycles_per_frame'] = c['cycles_per_frame']
                    if shared:
                        w['windows'].append(dict(mode='prepare_first', start_ns=10 + 10 * (active_start + 1),
                            end_ns=10 + 10 * (active_start + 33), operations=1, samples=0, outputs=0))
                    start_sample = active_start + (33 if shared else 1)
                    w['windows'].append(dict(mode='sample_first', start_ns=10 + 10 * start_sample,
                        end_ns=10 + 10 * (start_sample + 64), operations=1, samples=64, outputs=8))
                    w.update(transactions=len(rows), T=64, shared_LUT=bool(shared), real_word_ICG=bool(icg),
                        probability_register_bits=c['probability_register_bits'],
                        contract='Same g/u/W as frozenT32 power frames;64synthetic4x4x4 samples;shared adds32cold lookup cycles;no PRNG/model quality claim')
                    (folder / 'stim.hex').write_bytes(('\n'.join(rows) + '\n').encode())
                    (folder / 'expect.hex').write_bytes(('\n'.join(expected) + '\n').encode())
                    save(folder / 'WINDOWS.json', w)
                    ns.append(len(rows))
                assert len(set(ns)) == 1
                c['transactions'] = ns[0]
                cases.append(c)
                tops.append('module ' + c['top'] + '(input wire clk,rst_n,en,input wire[6668:0]din,output wire[264:0]dout);'
                    'nt_integrated #(.B(8),.M(8),.OR4(' + str(c['or4']) + '),.CW(' + str(cw) + '),.SAT(' + str(c['sat'])
                    + '),.WEIGHTED(' + str(weighted) + '),.SHARE(' + str(shared) + '),.GATE(' + str(icg) + '),.T(64))u(.*);endmodule\n')
                bench = (OLD / 'benches/g8_weighted_full.sv').read_text()
                bench = bench.replace('ns_g8_weighted_full', c['top'])
                bench = re.sub(r'\b479\b', str(ns[0]), bench)
                (P / 'benches' / (name + '.sv')).write_bytes(bench.encode())
    (P / 'rtl/tops.sv').write_bytes(('`timescale 1ns/1ps\n' + ''.join(tops)).encode())
    save(P / 'CASES.json', cases)
    flow = (P / 'flow/run_integrated.py').read_text().replace('34full or66shared', '66full or98shared;T64')
    flow = flow.replace('weighted orOR4s9', 'weighted20 orOR4signed9/10')
    (P / 'flow/run_integrated.py').write_bytes(flow.encode())
    save(P / 'INPUT_EQUIVALENCE.json', dict(source_archive_file=old_zip.name,
        source_archive_sha256=sha(old_zip), same_g_u_W_for_power_frames=True, entries=equivalence,
        activity_change='T32 Cartesian4x2x4 toT64 Cartesian4x4x4;synthetic external random thresholds,no quality inference'))
    save(P / 'CONFIG.json', dict(date='2026-10-31', issue=204, owner='rayggxia', source_base=SOURCE_BASE,
        N=64, M=8, T=64, seeds=list(SEEDS), PVT='SS1.08V125C', clock_MHz=100, load_pF=.001,
        area_factor=.81, cases=len(cases), weighted_counter_bits=20, or4_counter_candidates=[9,10],
        main_or4_bits=10, shared_LUTs=2, comparator_bits=8,
        cycles_full=66, cycles_shared=98,
        functional_transactions=sum(3*c['transactions'] for c in cases),
        PT_windows=sum(3*(4 if c['shared'] else 3) for c in cases),
        boundary='Alreadyencoded g/u through nonlinear and fixed Wd;no GU,PRNG,SRAM,FP,crossK,CTS/SDF/SPEF',
        policy='Keep old LUT,CE/realICG organization and Wd clocks;T64/normalization/necessary state width only;OR4s9 extra approximation'))
    print(json.dumps(json.loads((P / 'CONFIG.json').read_text())))


if __name__ == '__main__':
    main()
