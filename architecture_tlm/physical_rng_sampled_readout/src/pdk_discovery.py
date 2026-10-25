"""Bounded, read-only model discovery. Never choose among ambiguous matches."""
import os
from pathlib import Path
import time

MODEL_NAME = 'icsprout_55llulp1225_v1p1_spe.lib'


def discover_model(requested):
    requested = Path(requested).resolve()
    report = dict(requested_root=str(requested), requested_exists=requested.exists(),
                  directory_entries=[], searched_roots=[], candidates=[], errors=[], search_errors=[],
                  limits=dict(depth=5, directories=2000, seconds=15), truncated=False)
    try:
        report['directory_entries'] = sorted(p.name for p in requested.iterdir())[:80]
    except OSError as exc:
        report['errors'].append(str(exc))
    exact = requested / 'model/spectre' / MODEL_NAME
    if exact.is_file() and os.access(str(exact), os.R_OK):
        report.update(status='FOUND_EXACT', selected_model=str(exact), selected_root=str(requested))
        return requested, exact, report
    roots = [requested] if requested.is_dir() else []
    # If absent, inspect only immediate directories named for this PDK release.
    # When it exists, search only the user-specified tree (e.g. double nesting).
    if not roots:
        try:
            for p in sorted(requested.parent.iterdir()):
                if p.is_dir() and requested.name.lower() in p.name.lower():
                    roots.append(p)
        except OSError as exc:
            report['search_errors'].append(str(exc))
    started = time.monotonic()
    count = 0
    matches = set()
    for root in roots:
        report['searched_roots'].append(str(root))
        for current, dirs, files in os.walk(str(root), followlinks=False,
                                            onerror=lambda exc: report['search_errors'].append(str(exc))):
            count += 1
            if count > 2000 or time.monotonic() - started > 15:
                report['truncated'] = True
                break
            depth = len(Path(current).relative_to(root).parts)
            dirs.sort()
            if depth >= 5:
                dirs[:] = []
            for name in files:
                if name.lower() == MODEL_NAME:
                    matches.add(str((Path(current) / name).resolve()))
        if report['truncated']:
            break
    report['directories_examined'] = count
    report['candidates'] = sorted(matches)
    if len(matches) == 1 and not report['truncated'] and not report['search_errors']:
        model = Path(next(iter(matches)))
        if model.parent.name.lower() == 'spectre' and model.parent.parent.name.lower() in ('model', 'models'):
            pdk = model.parent.parent.parent
            if os.access(str(model), os.R_OK):
                report.update(status='FOUND_UNIQUE', selected_model=str(model), selected_root=str(pdk))
                return pdk, model, report
            report['status'] = 'MODEL_UNREADABLE'
            return requested, None, report
        report['status'] = 'UNSUPPORTED_MODEL_LAYOUT'
        return requested, None, report
    report['status'] = 'AMBIGUOUS' if len(matches) > 1 else ('SEARCH_INCOMPLETE' if report['truncated'] or report['search_errors'] else 'MODEL_NOT_FOUND')
    return requested, None, report
