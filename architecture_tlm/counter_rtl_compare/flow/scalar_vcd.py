"""Lossless vector-to-scalar VCD conversion; keep all bits, aliases and X/Z checks."""
import hashlib
import json
import re

OUTPUT_WIDTH = {0: 32, 2: 32, 4: 785, 5: 785, 6: 32, 7: 32, 8: 16, 21: 16}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def scalarize(src, dst, width):
    scopes, header, codes, names = [], [], {}, {}
    with src.open() as f, dst.open('w') as out:
        for line in f:
            a = line.split()
            if a and a[0] == '$scope':
                scopes.append(a[2])
            elif a and a[0] == '$upscope':
                scopes.pop()
            if a and a[0] == '$var':
                typ, width, code, ref = a[1], int(a[2]), a[3], a[4]
                if typ not in ('wire', 'reg', 'logic', 'integer'):
                    raise ValueError('Unsupported VCD type '+typ)
                if code not in codes:
                    codes[code] = dict(width=width, ids=['v{}_{}'.format(len(codes), j) for j in range(width)])
                entry = codes[code]
                if width != entry['width']:
                    raise ValueError('Alias width mismatch')
                suffix = ''.join(a[5:-1])
                m = re.fullmatch(r'\[(-?\d+)(?::(-?\d+))?\]', suffix) if suffix else None
                if suffix and not m:
                    raise ValueError('Unsupported VCD range '+line)
                if m:
                    left = int(m[1]); right = int(m[2]) if m[2] else left
                    indices = list(range(left, right+(1 if right>=left else -1), 1 if right>=left else -1))
                else:
                    indices = list(range(width-1, -1, -1))
                if len(indices) != width:
                    raise ValueError('Bad range width')
                for j, index in enumerate(indices):
                    bitref = ref + ('[{}]'.format(index) if width>1 or m else '')
                    full = '/'.join(scopes+[bitref.lstrip('\\')])
                    if full in names and names[full] != entry['ids'][j]:
                        raise ValueError('Duplicate conflicting name '+full)
                    names[full] = entry['ids'][j]
                    declaration = ref + (' [{}]'.format(index) if width>1 or m else '')
                    header.append('$var {} 1 {} {} $end\n'.format('wire' if typ=='integer' else typ, entry['ids'][j], declaration))
            else:
                header.append(line)
            if '$enddefinitions' in line:
                break
        else:
            raise ValueError('Missing header')
        h = ''.join(header)
        tm = re.search(r'\$timescale\s*(\d+)\s*(s|ms|us|ns|ps|fs)\s*\$end', h)
        if not tm:
            raise ValueError('Missing timescale')
        tick = int(tm[1])*dict(s=1e9, ms=1e6, us=1e3, ns=1, ps=.001, fs=.000001)[tm[2]]
        out.write(h)
        state = {i: dict(value=None, time=0, ones=0, toggles=0) for c in codes.values() for i in c['ids']}
        now, events = 0, 0
        for line in f:
            s = line.strip()
            if not s or s.startswith('$'):
                out.write(line)
                continue
            if s.startswith('#'):
                t = int(s[1:])
                if t < now:
                    raise ValueError('Backward VCD time')
                now = t; out.write(line); continue
            if s[0] in 'bB':
                value, code = s[1:].split()
            elif s[0] in '01xXzZ':
                value, code = s[0], s[1:]
            else:
                raise ValueError('Unsupported VCD event '+s)
            c = codes[code]
            value = value.lower()
            if len(value)>c['width'] or re.search('[^01xz]', value):
                raise ValueError('Bad value width/content')
            value = value.rjust(c['width'], value[0] if value[0] in 'xz' else '0')
            if re.search('[xz]', value):
                raise ValueError('X/Z in measured VCD; no waiver')
            for i, bit in zip(c['ids'], value):
                st = state[i]
                if st['value'] is None and now != 0:
                    raise ValueError('Missing initial state')
                if st['value'] == '1':
                    st['ones'] += now-st['time']
                st['toggles'] += int(st['value'] is not None and bit != st['value'])
                st.update(value=bit, time=now)
                out.write(bit+i+'\n')
                events += 1
        if now <= 0 or any(s['value'] is None for s in state.values()):
            raise ValueError('Empty/incomplete measured VCD')
        for st in state.values():
            if st['value']=='1':
                st['ones'] += now-st['time']
        expected = {}
        wanted = ['clk','out_valid']+['result[{}]'.format(i) for i in range(width)]
        for name in wanted:
            full = 'tb_counter/dut/'+name
            if full not in names:
                raise ValueError('Missing functional output/clock '+full)
            st = state[names[full]]
            expected[name] = dict(toggle_count=st['toggles'], toggle_rate_per_ns=st['toggles']/(now*tick), static_probability=st['ones']/now)
    return dict(source_sha256=digest(src), scalar_sha256=digest(dst), duration_ns=now*tick,
                scalar_ids=len(state), declarations=len(names), scalar_events=events, xz_signals=0,
                all_bits_preserved=True, expected_activity=expected)


def verify_pt(expected, actual):
    import csv
    with actual.open() as f:
        values = {r['name']: r for r in csv.DictReader(f, delimiter='\t')}
    differences = []
    for name, e in expected['expected_activity'].items():
        a = values.get(name, {})
        try:
            tr, sp = float(a['toggle_rate']), float(a['static_probability'])
        except (KeyError, ValueError):
            raise ValueError('PT activity unavailable: '+name)
        dt, dp = abs(tr-e['toggle_rate_per_ns']), abs(sp-e['static_probability'])
        # At most one boundary event; no percentage-based allowance for missing activity.
        if dt > 1.01/expected['duration_ns']+1e-8 or dp > 1e-5:
            raise ValueError('PT/VCD bit activity mismatch: {} {}'.format(name, (dt,dp)))
        differences.append(dict(name=name, toggle_rate_error_per_ns=dt, static_probability_error=dp))
    return dict(status='PASS', checked_bits=len(differences), differences=differences)
