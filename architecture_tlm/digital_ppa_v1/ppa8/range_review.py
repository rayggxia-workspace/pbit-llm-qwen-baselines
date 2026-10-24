"""Attribute flagged cells; their power share is not an error bound."""
import re


def review(text, cells, total_watts):
    flagged = {}
    pattern = r"^\s*(load|ramp)\s+([\deE.+-]+)\s+at pin '([^']+)' of cell '([^']+)' is out of (load|ramp) range \(([^,]+),\s*([^\)]+)\)"
    for line in text.splitlines():
        if ' is out of ' not in line:
            continue
        m = re.search(pattern, line)
        if not m:
            raise ValueError('Unparsed power range violation: '+line)
        typ, value, pin, cell, axis, low, high = m.groups()
        if cell not in cells:
            raise ValueError('Flagged power cell absent from inventory: '+cell)
        flagged.setdefault(cell, []).append(dict(type=typ,pin=pin,value=float(value),low=float(low),high=float(high)))
    watts = sum(cells[c] for c in flagged)
    return dict(flagged_cells=flagged, affected_cells_total_uW=watts*1e6,
                affected_cells_power_percent=100*watts/total_watts if total_watts else 0,
                interpretation='Sum of all power of flagged cells, NOT an error estimate or upper bound; no load/slew modification or warning waiver.')
