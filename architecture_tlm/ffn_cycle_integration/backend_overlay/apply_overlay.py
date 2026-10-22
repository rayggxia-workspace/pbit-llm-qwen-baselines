"""Apply only this overlay to an explicit, independent backend snapshot.

All dependencies and payloads are checked before writes. No fetch, checkout,
dependency installation, fuzzy patching, or overwrite of an unknown state.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re

FFN = 'architecture_tlm/cycle_v1/ffn.py'
OWN = {f'architecture_tlm/cycle_v1/{name}.py' for name in
       ('ffn_contract', 'ffn_contract_reference', 'run_contract_ffn', 'test_ffn_contract')}
PUBLICATION_ROOT = Path(__file__).resolve().parents[3]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def lf(data):
    data = data.replace(b'\r\n', b'\n')
    if b'\r' in data:
        raise ValueError('bare carriage return is not supported')
    data.decode('utf-8')
    return data


def no_links(path):
    for part in (path, *path.parents):
        attributes = getattr(part.lstat(), 'st_file_attributes', 0) if part.exists() else 0
        if (part.is_symlink() or attributes & 0x400 or
                (hasattr(part, 'is_junction') and part.is_junction())):
            raise ValueError('symlink/junction is not supported: ' + str(part))


def contained(root, relative):
    if (not isinstance(relative, str) or '\\' in relative or ':' in relative or
            str(PurePosixPath(relative)) != relative or relative in ('', '.') or
            PurePosixPath(relative).is_absolute() or '..' in PurePosixPath(relative).parts):
        raise ValueError('unsafe relative path: ' + str(relative))
    target = root.joinpath(*PurePosixPath(relative).parts)
    no_links(target)
    if not target.resolve().is_relative_to(root):
        raise ValueError('path escapes target root: ' + relative)
    return target


def checked_bytes(path, expected):
    raw = path.read_bytes()
    if sha(lf(raw)) != expected:
        raise ValueError('LF-normalized SHA mismatch: ' + str(path))
    return raw


def patch_exact(before, patch, target=FFN):
    """Apply exact unified hunks, without searching for relocated context."""
    old = lf(before).decode('utf-8').splitlines(keepends=True)
    lines = lf(patch).decode('utf-8').splitlines(keepends=True)
    if lines[:2] != ['--- a/' + target + '\n', '+++ b/' + target + '\n']:
        raise ValueError('unexpected patch file headers')
    result, cursor, index, hunks = [], 0, 2, 0
    while index < len(lines):
        match = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*\n', lines[index])
        if not match:
            raise ValueError('invalid unified hunk header')
        old_start, old_count, new_start, new_count = (
            int(match[1]), int(match[2] or '1'), int(match[3]), int(match[4] or '1'))
        offset = old_start if old_count == 0 else old_start - 1
        if offset < cursor or offset > len(old):
            raise ValueError('overlapping/out-of-range unified hunk')
        result.extend(old[cursor:offset])
        cursor = offset
        expected_new_offset = new_start if new_count == 0 else new_start - 1
        if len(result) != expected_new_offset:
            raise ValueError('inconsistent new hunk offset')
        index += 1
        used_old = used_new = 0
        while index < len(lines) and not lines[index].startswith('@@ '):
            line = lines[index]
            if not line or line[0] not in ' +-':
                raise ValueError('unsupported unified hunk line')
            mark, content = line[0], line[1:]
            if mark in ' -':
                if cursor >= len(old) or old[cursor] != content:
                    raise ValueError('patch context differs from exact baseline')
                cursor += 1
                used_old += 1
            if mark in ' +':
                result.append(content)
                used_new += 1
            index += 1
        if (used_old, used_new) != (old_count, new_count):
            raise ValueError('unified hunk count mismatch')
        hunks += 1
    if not hunks:
        raise ValueError('empty patch')
    result.extend(old[cursor:])
    return ''.join(result).encode('utf-8')


def preflight(backend_root, package=None):
    requested = Path(backend_root)
    if not requested.is_absolute():
        raise ValueError('--backend-root must be an explicit absolute path')
    no_links(requested)
    root = requested.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('backend root is not a directory')
    if root.is_relative_to(PUBLICATION_ROOT) or PUBLICATION_ROOT.is_relative_to(root):
        raise ValueError('backend root must be independent of the publication checkout')
    package = Path(package or Path(__file__).parent).resolve(strict=True)
    manifest_raw = (package / 'MANIFEST.json').read_bytes()
    manifest = json.loads(manifest_raw)
    if manifest['schema'] != 'ffn.backend_overlay.1':
        raise ValueError('unsupported overlay schema')
    identity = manifest['overlay_id']
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', identity):
        raise ValueError('unsafe overlay ID')
    info = manifest['patch']
    payloads = manifest['payloads']
    targets = {p['target'] for p in payloads}
    if info['target'] != FFN or targets != OWN or len(payloads) != len(OWN):
        raise ValueError('unexpected overlay target set')
    dependencies = manifest['dependencies']
    snapshot = manifest['snapshot_files']
    if not dependencies or set(dependencies) & (targets | {FFN}):
        raise ValueError('invalid dependency set')
    if set(snapshot) != set(dependencies) | targets | {FFN}:
        raise ValueError('snapshot closure differs from declared dependencies and targets')
    for name, entry in dependencies.items():
        if entry != snapshot[name]:
            raise ValueError('dependency differs from snapshot record: ' + name)
        checked_bytes(contained(root, name), entry['sha256_lf'])
    patch = checked_bytes(contained(package, info['payload']), info['sha256_lf'])
    replacement = {}
    for entry in payloads:
        if entry['before'] != 'absent' or entry['sha256_lf'] != snapshot[entry['target']]['sha256_lf']:
            raise ValueError('inconsistent payload record')
        replacement[entry['target']] = lf(checked_bytes(
            contained(package, entry['payload']), entry['sha256_lf']))
    if info['after_sha256_lf'] != snapshot[FFN]['sha256_lf']:
        raise ValueError('patched hash differs from snapshot')
    ffn = contained(root, FFN)
    original = ffn.read_bytes()
    ffn_hash = sha(lf(original))
    existing = {name: contained(root, name).exists() for name in targets}
    if ffn_hash == info['after_sha256_lf'] and all(existing.values()):
        for entry in payloads:
            checked_bytes(contained(root, entry['target']), entry['sha256_lf'])
        status = 'already_applied'
    elif ffn_hash == info['before_sha256_lf'] and not any(existing.values()):
        after = patch_exact(original, patch)
        if sha(after) != info['after_sha256_lf']:
            raise ValueError('patch result hash mismatch')
        # Preserve uniform CRLF for the existing file; new files use LF.
        replacement[FFN] = after.replace(b'\n', b'\r\n') if b'\r\n' in original and b'\n' not in original.replace(b'\r\n', b'') else after
        status = 'ready'
    else:
        raise ValueError('unknown or partially applied state; no files were written')
    journal = contained(root, '.ffn_contract_overlay/' + identity)
    if status == 'ready' and journal.exists():
        raise ValueError('existing recovery journal requires inspection: ' + str(journal))
    if status == 'ready' and contained(root, FFN + '.' + identity + '.new').exists():
        raise ValueError('existing staged replacement requires inspection')
    # Every target parent must already exist in the separate backend checkout.
    for name in targets | {FFN}:
        if not contained(root, name).parent.is_dir():
            raise ValueError('target parent missing: ' + name)
    return dict(root=root, manifest=manifest, manifest_sha256=sha(manifest_raw),
                original=original, replacement=replacement, journal=journal, status=status)


def write_new(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')


def apply(backend_root, *, check=False, package=None):
    plan = preflight(backend_root, package)
    root, journal = plan['root'], plan['journal']
    report = dict(status=plan['status'], backend_root=str(root),
                  overlay_id=plan['manifest']['overlay_id'],
                  dependencies_verified=len(plan['manifest']['dependencies']),
                  snapshot_files=len(plan['manifest']['snapshot_files']))
    if check or plan['status'] == 'already_applied':
        return report
    # Repeat the complete closure check immediately before entering write phase.
    second = preflight(root, package)
    if (second['manifest_sha256'], second['original'], second['replacement']) != (
            plan['manifest_sha256'], plan['original'], plan['replacement']):
        raise ValueError('source changed during preflight')
    journal.parent.mkdir(exist_ok=True)
    journal.mkdir()  # exclusive: an ambiguous previous attempt is never replayed
    backup = journal / 'ffn.py.original'
    write_new(backup, plan['original'])
    write_new(journal / 'intent.json', json_bytes(dict(
        **report, manifest_sha256=plan['manifest_sha256'],
        original_sha256=sha(plan['original']), original_sha256_lf=sha(lf(plan['original'])),
        planned_sha256={name: sha(raw) for name, raw in plan['replacement'].items()})))
    written = []
    try:
        for name, raw in plan['replacement'].items():
            target = contained(root, name)
            if name == FFN:
                if target.read_bytes() != plan['original']:
                    raise ValueError('ffn.py changed after preflight; original backup retained')
                staged = contained(root, name + '.' + report['overlay_id'] + '.new')
                write_new(staged, raw)
                os.replace(staged, target)
            else:
                write_new(target, raw)
            written.append(name)
            write_new(journal / ('step-%02d.json' % len(written)), json_bytes(dict(target=name, sha256=sha(raw))))
        actual = {}
        for name, record in plan['manifest']['snapshot_files'].items():
            raw = checked_bytes(contained(root, name), record['sha256_lf'])
            actual[name] = dict(sha256=sha(raw), sha256_lf=sha(lf(raw)))
        report['status'] = 'applied'
        report['journal'] = str(journal)
        write_new(journal / 'receipt.json', json_bytes(dict(
            **report, manifest_sha256=plan['manifest_sha256'],
            backup_sha256=sha(backup.read_bytes()), files=actual)))
        return report
    except Exception as error:
        write_new(journal / 'failure.json', json_bytes(dict(
            error=str(error), written=written,
            recovery='Inspect intent, exact original backup and current files; no automatic rollback or replay.')))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-root', type=Path, required=True)
    parser.add_argument('--check', action='store_true', help='verify complete closure without writes')
    args = parser.parse_args()
    try:
        print(json.dumps(apply(args.backend_root, check=args.check), indent=2))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, 'overlay refused: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
