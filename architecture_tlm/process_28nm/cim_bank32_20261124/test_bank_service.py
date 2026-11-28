"""Check the real parent BeatSRAM timing kernel, not a bandwidth formula."""
import argparse
import heapq
import importlib.util
import itertools
from pathlib import Path
import sys

def main():
    p = argparse.ArgumentParser(); p.add_argument('--shared-memory', type=Path, required=True)
    a = p.parse_args()
    spec = importlib.util.spec_from_file_location('bank32_timing_fixture', a.shared_memory)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    class Hub:
        now = 0.; common_period_ns = 4.
        def __init__(self): self.events = []; self.ids = itertools.count()
        def later(self, at, callback): heapq.heappush(self.events, (at, next(self.ids), callback))
    h = Hub()
    mem = module.BeatSRAM(h, capacity=8192, banks=16, word_bytes=16,
        clock_hz=250000000, fabric_GBs=64., minimum_period_ns=1.)
    region = mem.region('one_core_16banks_32words', 8192, range(16))
    completed = []
    mem.submit(region, 0, 8192, True, 'bank32_program_test', lambda: completed.append(h.now))
    while h.events:
        h.now, _, callback = heapq.heappop(h.events); callback()
    assert completed == [128.], completed
    assert mem.count['write_words'] == 512
    assert mem.count['peak_words_per_cycle'] == 16
    assert mem.count['cycles_with_grants'] == 32
    assert not mem.queue
    print('PASS:512 words,16 independent banks,32 grant cycles,128ns completion')

if __name__ == '__main__': main()
