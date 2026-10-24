"""Audit unknown VCD bits before applying a PT-connectivity-backed projection."""
import csv
import json
import re
from pathlib import Path
from scalar_vcd import digest, scalarize

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'tb_counter/dut/'
SAFE = frozenset(('MODEL_INTERNAL', 'DISCONNECTED'))


def save(path, value):
    path.write_bytes((json.dumps(value, indent=2, sort_keys=True)+'\n').encode('utf-8'))


def declarations(stream):
    scopes, codes = [], {}
    for line in stream:
        a = line.split()
        if a and a[0] == '$scope':
            scopes.append(a[2].lstrip('\\'))
        elif a and a[0] == '$upscope':
            scopes.pop()
        elif a and a[0] == '$var':
            typ, width, code, ref = a[1], int(a[2]), a[3], a[4].lstrip('\\')
            suffix = ''.join(a[5:-1])
            match = re.fullmatch(r'\[(-?\d+)(?::(-?\d+))?\]', suffix) if suffix else None
            if suffix and not match:
                raise ValueError('Unsupported range '+line)
            if match:
                left = int(match[1]); right = int(match[2]) if match[2] else left
                indices = list(range(left, right+(1 if right >= left else -1), 1 if right >= left else -1))
            else:
                indices = list(range(width-1, -1, -1))
            if len(indices) != width:
                raise ValueError('Bad VCD width')
            entry = codes.setdefault(code, dict(width=width, aliases=[[] for _ in indices]))
            if entry['width'] != width:
                raise ValueError('Alias width mismatch')
            for pos, index in enumerate(indices):
                name = '/'.join(scopes+[ref+('[{}]'.format(index) if match or width > 1 else '')])
                if not name.startswith(PREFIX) or any(c in name for c in '\t\r\n'):
                    raise ValueError('Unexpected scope/name '+name)
                entry['aliases'][pos].append(dict(name=name, type=typ))
        if '$enddefinitions' in line:
            if not codes:
                raise ValueError('Empty VCD')
            return codes
    raise ValueError('Missing VCD header')


def audit(src):
    unknown, now = {}, 0
    with src.open() as stream:
        codes = declarations(stream)
        for line in stream:
            text = line.strip()
            if not text or text.startswith('$'):
                continue
            if text.startswith('#'):
                now = int(text[1:]); continue
            if text[0] in 'bB':
                value, code = text[1:].split()
            elif text[0] in '01xXzZ':
                value, code = text[0], text[1:]
            else:
                raise ValueError('Unsupported event '+text)
            entry = codes[code]; value = value.lower()
            if len(value) > entry['width'] or re.search('[^01xz]', value):
                raise ValueError('Invalid VCD value')
            value = value.rjust(entry['width'], value[0] if value[0] in 'xz' else '0')
            for pos, bit in enumerate(value):
                if bit in 'xz':
                    record = unknown.setdefault((code, pos), dict(code=code, position=pos,
                        aliases=entry['aliases'][pos], first_tick=now, last_tick=now, events=0, kinds=[]))
                    record['events'] += 1; record['last_tick'] = now
                    if bit not in record['kinds']:
                        record['kinds'].append(bit)
    return dict(source_sha256=digest(src), unknown_bits=list(unknown.values()),
                unknown_bit_count=len(unknown), duration_ticks=now,
                policy='No X/Z replacement; exclude only all-alias PT-proven nonfunctional bits')


def decisions(records, report):
    with report.open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    actual = {r['name']: r for r in rows}
    wanted = {a['name'][len(PREFIX):] for r in records['unknown_bits'] for a in r['aliases']}
    if len(actual) != len(rows) or set(actual) != wanted:
        raise ValueError('PT X/Z classification is incomplete or duplicated')
    excluded, blocked = {}, []
    for bit in records['unknown_bits']:
        evidence = [actual[a['name'][len(PREFIX):]] for a in bit['aliases']]
        decision = dict(bit, evidence=evidence)
        if all(r['classification'] in SAFE for r in evidence):
            excluded[(bit['code'], bit['position'])] = decision
        else:
            blocked.append(decision)
    return excluded, blocked


def prepare_activity(raw, work, start, stop, output_width, net_dir, call):
    from wave import clip
    meta = clip(raw, work/'window.vcd', start, stop)
    save(work/'WAVE_CLIP.json', meta)
    records = audit(work/'window.vcd')
    save(work/'XZ_AUDIT.json', records)
    excluded, blocked = {}, []
    if records['unknown_bits']:
        names = sorted({a['name'][len(PREFIX):] for r in records['unknown_bits'] for a in r['aliases']})
        (work/'xz_requests.txt').write_bytes(('\n'.join(names)+'\n').encode('utf-8'))
        call(['pt_shell', '-f', ROOT/'flow/xz_probe.tcl'], work,
             dict(NET_DIR=str(net_dir), XZ_REQUESTS=str(work/'xz_requests.txt')))
        if not (work/'XZ_PROBE_COMPLETE').is_file():
            raise RuntimeError('PT connectivity probe incomplete; inspect XZ_AUDIT.json')
        excluded, blocked = decisions(records, work/'xz_classification.tsv')
    policy = dict(status='BLOCKED' if blocked else 'PASS', excluded_bits=list(excluded.values()),
                  blocked_bits=blocked, original_window_sha256=records['source_sha256'],
                  proof_sha256=digest(work/'xz_classification.tsv') if records['unknown_bits'] else None)
    save(work/'XZ_POLICY.json', policy)
    if blocked:
        raise RuntimeError('X/Z reaches functional or unresolved objects; inspect XZ_POLICY.json ({} bits)'.format(len(blocked)))
    stats = scalarize(work/'window.vcd', work/'activity.vcd', output_width, excluded_bits=excluded)
    save(work/'ACTIVITY_EXPECTED.json', stats)
    return stats
