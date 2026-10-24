"""Dump design nets at each hierarchy, without library-model internal variables."""
import csv
import re


def generate(inventory, destination, branch):
    scopes = {''}
    with inventory.open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    if not rows:
        raise ValueError('Empty leaf inventory')
    for row in rows:
        parts = row['name'].split('/')
        if not row['ref'].endswith('_9TSVT') or any(not p for p in parts):
            raise ValueError('Invalid leaf inventory')
        for count in range(1, len(parts)):
            scopes.add('/'.join(parts[:count]))
    def sv_path(name):
        return '.'.join(p if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*', p)
                        else '\\'+p+' ' for p in name.split('/'))
    text = '\n'.join('$dumpvars(1,tb.'+branch+'.dut'+('.'+sv_path(s) if s else '')+');'
                     for s in sorted(scopes))+'\n'
    destination.write_bytes(text.encode('ascii'))
    return sorted(scopes)


def normalize_header(raw, normalized, branch):
    """VCS may collapse the generate scope and DUT into one scope token."""
    target = branch+'.dut'
    header = True
    count = 0
    with raw.open() as src, normalized.open('w') as dst:
        for line in src:
            fields = line.split()
            if header and len(fields) == 4 and fields[:2] == ['$scope', 'module'] and fields[2] == target:
                dst.write('$scope module '+branch+' $end\n$scope module dut $end\n')
                count += 1
                # Closing this compound scope needs one extra upscope.
                depth = 1
                for line in src:
                    fields = line.split()
                    if fields and fields[0] == '$scope': depth += 1
                    if fields and fields[0] == '$upscope': depth -= 1
                    dst.write(line)
                    if depth == 0:
                        dst.write('$upscope $end\n')
                        break
                else:
                    raise ValueError('Unclosed compound scope')
                continue
            dst.write(line)
            if '$enddefinitions' in line: header = False
    if count > 1:
        raise ValueError('Ambiguous compound DUT scope')
    return count
