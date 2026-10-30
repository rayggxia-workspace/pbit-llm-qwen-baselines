"""Lossless vector-to-scalar VCD conversion; keep all bits, aliases and X/Z checks."""
import hashlib
import json
import re

def vcd_id(index):
    """Dense printable identifiers also bound legacy readers' radix-94 tables."""
    if index < 0: raise ValueError('Negative VCD identifier index')
    value=index+1; chars=[]
    while value:
        value,rem=divmod(value-1,94)
        chars.append(chr(33+rem))
    return ''.join(chars)

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def scalarize(src, dst, output_width, output_name, excluded_bits=None, required_names=None, scope_prefix='tb_counter_power/dut/'):
    if not isinstance(output_width,int) or output_width<=0:
        raise ValueError('Invalid expected output width')
    excluded_bits = excluded_bits or {}
    if required_names is not None:
        required_names = set(required_names)
        if not required_names or excluded_bits:
            raise ValueError('Empty boundary or incompatible bit exclusions')
        if any(not n.startswith(scope_prefix) for n in required_names):
            raise ValueError('Boundary outside DUT')
    scopes, header, codes, names = [], [], {}, {}
    kept = set()
    omitted = {}
    omitted_xz = set()
    next_id = 0
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
                    codes[code] = dict(width=width, ids=[vcd_id(next_id+j) for j in range(width)])
                    next_id += width
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
                    if (code, j) in excluded_bits:
                        continue
                    bitref = ref + ('[{}]'.format(index) if width>1 or m else '')
                    full = '/'.join(scopes+[bitref.lstrip('\\')])
                    if required_names is not None and full not in required_names:
                        omitted.setdefault((code,j), []).append(full)
                        continue
                    if full in names and names[full] != entry['ids'][j]:
                        raise ValueError('Duplicate conflicting name '+full)
                    names[full] = entry['ids'][j]
                    kept.add((code,j))
                    declaration = ref + (' [{}]'.format(index) if width>1 or m else '')
                    header.append('$var {} 1 {} {} $end\n'.format('wire' if typ=='integer' else typ, entry['ids'][j], declaration))
            else:
                header.append(line)
            if '$enddefinitions' in line:
                break
        else:
            raise ValueError('Missing header')
        if required_names is not None and set(names) != required_names:
            raise ValueError('Missing mapped boundary signals: '+str(sorted(required_names-set(names))[:20]))
        h = ''.join(header)
        tm = re.search(r'\$timescale\s*(\d+)\s*(s|ms|us|ns|ps|fs)\s*\$end', h)
        if not tm:
            raise ValueError('Missing timescale')
        tick = int(tm[1])*dict(s=1e9, ms=1e6, us=1e3, ns=1, ps=.001, fs=.000001)[tm[2]]
        out.write(h)
        state = {i: dict(value=None, time=0, ones=0, toggles=0, raw_value=None, raw_toggles=0)
                 for code,c in codes.items() for j,i in enumerate(c['ids']) if (code,j) in kept}
        pending = {}
        def settle(t):
            # Zero-delay delta transitions have zero physical pulse width.
            for i,bit in pending.items():
                st=state[i]
                if st['value'] is None and t != 0:
                    raise ValueError('Missing initial state')
                if st['value']=='1': st['ones'] += t-st['time']
                st['toggles'] += int(st['value'] is not None and bit!=st['value'])
                st.update(value=bit,time=t)
            pending.clear()
        now, events, origin, absolute = 0, 0, None, 0
        for line in f:
            s = line.strip()
            if not s or s.startswith('$'):
                out.write(line)
                continue
            if s.startswith('#'):
                t = int(s[1:])
                if t < absolute: raise ValueError('Backward VCD time')
                absolute = t
                if origin is None: continue
                t -= origin
                if t < now:
                    raise ValueError('Backward VCD time')
                if t > now: settle(now)
                now = t; out.write('#{}\n'.format(t)); continue
            if s[0] in 'bB':
                value, code = s[1:].split()
            elif s[0] in '01xXzZ':
                value, code = s[0], s[1:]
            else:
                raise ValueError('Unsupported VCD event '+s)
            if origin is None:
                origin = absolute
                out.write('#0\n')
            c = codes[code]
            value = value.lower()
            if len(value)>c['width'] or re.search('[^01xz]', value):
                raise ValueError('Bad value width/content')
            value = value.rjust(c['width'], value[0] if value[0] in 'xz' else '0')
            for j,(i, bit) in enumerate(zip(c['ids'], value)):
                if (code,j) not in kept:
                    if bit in 'xz': omitted_xz.add((code,j))
                    continue
                if bit in 'xz':
                    raise ValueError('X/Z in retained measured VCD; no waiver: '+str([n for n,v in names.items() if v==i][:5]))
                st = state[i]
                st['raw_toggles'] += int(st['raw_value'] is not None and bit!=st['raw_value'])
                st['raw_value']=bit
                pending[i]=bit
                out.write(bit+i+'\n')
                events += 1
        settle(now)
        if now <= 0 or any(s['value'] is None for s in state.values()):
            raise ValueError('Empty/incomplete measured VCD')
        for st in state.values():
            if st['value']=='1':
                st['ones'] += now-st['time']
        expected = {}
        wanted = [output_name+'[{}]'.format(i) for i in range(output_width)]
        if required_names is not None:
            wanted = sorted(n[len(scope_prefix):] for n in required_names)
        for name in wanted:
            full = scope_prefix+name
            if full not in names:
                raise ValueError('Missing functional output/clock '+full)
            st = state[names[full]]
            expected[name] = dict(toggle_count=st['toggles'], raw_toggle_count=st['raw_toggles'],
                                  toggle_rate_per_ns=st['toggles']/(now*tick), static_probability=st['ones']/now)
    return dict(source_sha256=digest(src), scalar_sha256=digest(dst), duration_ns=now*tick,
                scalar_ids=len(state), declarations=len(names), scalar_events=events, xz_signals=0,
                all_bits_preserved=not bool(excluded_bits) and required_names is None, all_retained_bits_preserved=True,
                full_mapped_boundary_verified=required_names is not None,
                mapped_boundary_signals=len(required_names) if required_names is not None else None,
                omitted_declarations=sum(len(v) for v in omitted.values()),
                omitted_xz_names=sorted({n for key in omitted_xz for n in omitted.get(key,[])}),
                activity_statistics='Settled values per timestamp; emitted VCD retains all original delta events',
                zero_time_delta_transitions=sum(st['raw_toggles']-st['toggles'] for st in state.values()),
                excluded_nonfunctional_bits=len(excluded_bits), expected_activity=expected)


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
