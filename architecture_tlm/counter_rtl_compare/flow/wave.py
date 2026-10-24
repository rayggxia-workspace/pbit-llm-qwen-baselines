"""Bounded-memory VCD window extraction, with exact duration and X/Z audit."""
import re
import gzip


def clip(src, dst, start_ns, end_ns):
    widths, names, values, scopes = {}, {}, {}, []
    variable_scopes, unknown = set(), set()
    header = []
    events = 0
    opener = gzip.open if src.suffix == '.gz' else open
    with opener(str(src), 'rt') as f, dst.open('w') as out:
        for line in f:
            header.append(line)
            a = line.split()
            if a and a[0] == '$scope':
                scopes.append(a[2])
            elif a and a[0] == '$upscope':
                scopes.pop()
            elif a and a[0] == '$var':
                widths[a[3]] = int(a[2])
                names[a[3]] = '/'.join(scopes+[a[4]])
                variable_scopes.add('/'.join(scopes))
            if '$enddefinitions' in line:
                break
        else:
            raise ValueError('Missing VCD header')
        h = ''.join(header)
        m = re.search(r'\$timescale\s*(\d+)\s*(s|ms|us|ns|ps|fs)\s*\$end', h)
        if not m or not widths:
            raise ValueError('Empty VCD / unknown timescale')
        scale = int(m[1])*dict(s=1e9, ms=1e6, us=1e3, ns=1, ps=.001, fs=.000001)[m[2]]
        begin, end = int(round(start_ns/scale)), int(round(end_ns/scale))
        if not 0 < begin < end:
            raise ValueError('Window must start after reset settling')
        out.write(h)
        started = False
        last = 0
        for line in f:
            s = line.strip()
            if not s or s.startswith('$'):
                continue
            if s.startswith('#'):
                last = int(s[1:])
                if last >= begin and not started:
                    out.write('#0\n$dumpvars\n')
                    for code, width in widths.items():
                        value = values.get(code, 'x')
                        out.write((value+code if width == 1 else 'b'+value+' '+code)+'\n')
                        if re.search('[xz]', value, re.I):
                            unknown.add(code)
                    out.write('$end\n')
                    started = True
                if last >= end:
                    out.write('#{}\n'.format(end-begin))
                    break
                if started:
                    out.write('#{}\n'.format(last-begin))
            elif s[0] in 'bB01xXzZ':
                if s[0] in 'bB':
                    value, code = s[1:].split()
                else:
                    value, code = s[0], s[1:]
                values[code] = value
                if started:
                    out.write(line)
                    events += 1
                    if re.search('[xz]', value, re.I):
                        unknown.add(code)
            elif s.startswith('r'):
                raise ValueError('Unexpected real-valued signal')
        if not started or last < end:
            raise ValueError('VCD ends before window')
    return dict(start_ns=start_ns, end_ns=end_ns, duration_ns=end_ns-start_ns,
                signals=len(widths), events=events, xz_signals=len(unknown),
                xz_names=[names[c] for c in sorted(unknown)],
                variable_scopes=sorted(variable_scopes))
