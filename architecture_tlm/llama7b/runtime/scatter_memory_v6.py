"""Bounded scatter DMA, retaining actual burst addresses and completion waits."""
import heapq
import json
import math
from dramsys_backend import DRAMSysExternal


def coalesced_bursts(ranges, burst=64):
    lines = set()
    for address, size in ranges:
        if address < 0 or size <= 0:
            raise ValueError('invalid scatter span')
        lines.update(range(address // burst, (address + size - 1) // burst + 1))
    spans = []
    for line in sorted(lines):
        address = line * burst
        if spans and spans[-1][0] + spans[-1][1] == address:
            spans[-1] = (spans[-1][0], spans[-1][1] + burst)
        else:
            spans.append((address, burst))
    return spans


class ScatterDRAMSysExternal(DRAMSysExternal):
    def _read(self):
        response = super()._read()
        if response.get('status') == 'ready':
            self.scatter_supported = 'scatter_gather_v1' in response.get('features', [])
        return response

    def access_ranges(self, ready, ranges, kind, write=False):
        if not self.scatter_supported:
            raise ValueError('this run requires the v6 scatter-aware DRAMSys bridge')
        spans = coalesced_bursts(ranges)
        if not spans:
            return ready
        n = sum(size for _, size in spans)
        if any(address + size > self.capacity for address, size in spans):
            raise ValueError('scatter DMA outside DRAM')
        self.counter += 1
        request = dict(op='access_sg', id=self.counter, ready_ns=ready,
                       ranges=[dict(address=a, bytes=s) for a, s in spans], write=write)
        self.process.stdin.write(json.dumps(request) + '\n')
        self.process.stdin.flush()
        response = self._read()
        if response.get('id') != self.counter or response['done_ns'] < ready:
            raise RuntimeError('invalid scatter completion')
        direction = 'write' if write else 'read'
        self.traffic[f'external_{kind}_{direction}_logical_bytes'] += n
        self.traffic[f'external_{kind}_{direction}_burst_bytes'] += n
        self.traffic[f'external_{kind}_{direction}_requests'] += 1
        done = response['done_ns']
        self.service_ns += done - ready
        self.max_service_ns = max(self.max_service_ns, done - ready)
        self.trace.write(json.dumps({**request, 'kind': kind, 'logical_bytes': n, **response}) + '\n')
        return done


def link_access_ranges(ext, ready, ranges, kind, write=False, pending=32, issue_ns=1.):
    """A finite 64B-burst queue; latency is paid, overlapped only with credits.

    Shares ext.link with all normal traffic. No cache or row-hit discount is
    assumed. This is a Link estimate, never a substitute for DRAMSys results.
    """
    if ext.cfg['burst_bytes'] != 64 or pending < 1 or issue_ns <= 0:
        raise ValueError('v6 comparison uses 64B bursts and a finite issue queue')
    completions = []
    issuer = ready
    last = ready
    peak = 0
    for address, size in coalesced_bursts(ranges):
        for offset in range(0, size, 64):
            while completions and completions[0] <= issuer:
                heapq.heappop(completions)
            if len(completions) >= pending:
                issuer = max(issuer, heapq.heappop(completions))
                while completions and completions[0] <= issuer:
                    heapq.heappop(completions)
            done = ext.access(issuer, 64, kind, write, address=address + offset)
            heapq.heappush(completions, done)
            peak = max(peak, len(completions))
            last = max(last, done)
            issuer += issue_ns
    ext.traffic['scatter_peak_inflight_bursts'] = max(
        ext.traffic['scatter_peak_inflight_bursts'], peak)
    return last
