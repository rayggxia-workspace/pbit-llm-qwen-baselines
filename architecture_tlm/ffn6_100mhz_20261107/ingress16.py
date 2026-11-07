"""Current100 ingress selection; retain the original24KiB factory as reference.

Only data-holding capacity/credit reservation changes. No SRAM bank, return
port, clock, DRAM service, compute resource or buffer implementation is freed.
"""
from collections import deque
from pathlib import Path
from types import MethodType
import argparse, hashlib, json, math, time

DEFAULT_INGRESS_KIB = 16


def make_model(backend, *, ingress_kib=DEFAULT_INGRESS_KIB, **kwargs):
    from .model import make_model as reference_factory
    if ingress_kib not in (16, 24):
        raise ValueError('current16 or historical24KiB ingress only')
    h, m = reference_factory(backend, **kwargs)
    assert not h.now and not h.events and not h.pending and not h.mem.queue
    assert not h.return_occupied and all(not q for q in h.ingress)
    assert h.response_bytes == 24576 and len(h.free_slots) == 384
    h.response_bytes = ingress_kib * 1024
    h.free_slots = deque(range(h.response_bytes // 64))
    contract = dict(clock_MHz=100, holding_KiB=ingress_kib,
        slots64B=len(h.free_slots), max_pending_requests=h.credit,
        return_lanes_per_channel=h.per_channel,
        reservation='pending64B+returned_not_landed<=holding_bytes',
        SRAM_KiB=h.mem.capacity//1024, SRAM_banks=h.mem.nbank,
        unused_return_SRAM_reclaimed=h.response is None,
        physical_implementation='existing gated-register data-holding proxy',
        new_DMA_RTL_or_PPA=False, TT250_changed=False)
    m.ingress_capacity_contract = contract
    parent = m.run
    def run(self):
        result = parent()
        result['ingress_capacity_contract'] = dict(contract)
        return result
    m.run = MethodType(run, m)
    return h, m


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_bytes((json.dumps(value, ensure_ascii=False, indent=2,
                                     allow_nan=False)+'\n').encode('utf-8'))


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    checkout = Path(__file__).resolve().parents[2]
    # Existing bootstrap verifies the exact runtime, dependencies and inputs.
    import replay
    _, owner, identity = replay.setup(a.project, checkout)
    from architecture_tlm.ffn6_100mhz_20261107.ingress16 import make_model as factory
    from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
    inputs = a.project/'tmp/attention-compare-issue198-20261027/work/rayggxia/198/attention_tlm_20261105/runtime'
    a.out.mkdir(parents=True, exist_ok=False)
    results = {}
    for kib in (24, 16):
        start = time.time()
        h, m = factory(AnalyticDRAM(latency_ns=30, bandwidth_GBs=136.4606),
            owner_install=owner.install, ingress_kib=kib, cores=6,
            samples=read(inputs/'SAMPLES.json'), layers=36, include_lm=False,
            seed=17, attention_input=read(inputs/'representative.json'))
        # Allocation remains36-layer; run one complete cold layer plus embedding.
        m.model['layers'] = 1
        parent_phase = m.phase
        def phase(stage, jobs, layer):
            value = parent_phase(stage, jobs, layer)
            print(json.dumps(dict(KiB=kib, stage=stage, simulated_us=h.now/1000,
                                  wall_seconds=time.time()-start)), flush=True)
            return value
        m.phase = phase
        result = m.run()
        memory = h.report()
        assert not memory['final_pending'] and not memory['final_response_occupied']
        assert not h.mem.queue and not h.events and not m.common_prefetched
        assert len(h.free_slots) == kib*16
        assert memory['counts'].get('peak_response_bytes', 0) <= kib*1024
        result.update(status='completed', holding_KiB=kib, time_us=h.now/1000,
            memory=memory, SRAM=h.mem.report(h.now), source_identity=identity,
            scope='complete cold first layer plus embedding;36-layer allocation;no lm_head',
            backend='analytic136.4606GB/s30ns, not native LPDDR', seed=17,
            new_PPA=False, new_PPL=False, wall_seconds=time.time()-start,
            source_sha256={x.name:sha(x) for x in Path(__file__).parent.glob('*.py')})
        name='LAYER_%dKiB.json'%kib
        save(a.out/name, result)
        save(a.out/('SEAL_%dKiB.json'%kib), dict(result_sha256=sha(a.out/name),
                                               source_sha256=result['source_sha256']))
        results[kib] = result
    old, new = results[24], results[16]
    assert old['kernel_active'] == new['kernel_active']
    numerical = ('attention_QK_MAC','samples','unique_V','PV_ADD','BF16_MAC',
                 'GU_logical_R8_ports','NL_logical_R8_ports','common_R8_words')
    for key in numerical:
        assert old['actions'].get(key,0) == new['actions'].get(key,0), key
    for kind, row in old['memory']['by_kind'].items():
        for key in ('issued_bytes','issued_address_sum','issued_address_xor'):
            assert row.get(key,0) == new['memory']['by_kind'][kind].get(key,0), (kind,key)
    for key in ('dram_read_bytes','dram_write_bytes'):
        assert old['memory']['counts'].get(key,0) == new['memory']['counts'].get(key,0)
    reference = read(Path(__file__).with_name('RESULTS.json'))
    areas = dict(reference['areas55_proxy_mm2'])
    old_area = areas.pop('DMA_24KiB_holding')
    areas['DMA_16KiB_holding'] = old_area*16/24
    phases = [dict(stage=x['stage'],old_us=x['duration_ns']/1000,
                   new_us=y['duration_ns']/1000) for x,y in zip(old['phases'],new['phases'])]
    assert [x['stage'] for x in old['phases']] == [x['stage'] for x in new['phases']]
    summary = dict(status='PASS',current_holding_KiB=16,old_holding_KiB=24,
        old_layer_us=old['time_us'],new_layer_us=new['time_us'],
        layer_change_percent=(new['time_us']/old['time_us']-1)*100,phases=phases,
        old_covered_area55_mm2=reference['area55_proxy_mm2'],
        covered_area55_mm2=math.fsum(areas.values()),areas55_proxy_mm2=areas,
        holding_area_saved_mm2=old_area/3,
        holding_leakage_W=dict(old=0.0015586133333333333,new=0.0015586133333333333*2/3),
        SRAM_KiB=1216,SRAM_banks=304,TT250_changed=False,
        validation=['completed full first-layer pair','queues and data slots drain',
            'sampling and arithmetic actions equal','DRAM bytes/address sum/xor equal',
            'fixed SRAM/ports/compute/clock;only ingress capacity changes'],
        scope=old['scope'],backend=old['backend'],
        whole_token_time_ms=None, whole_token_energy_mJ=None,
        new_PPA=False,new_PPL=False,
        raw_results=[dict(path=str(a.out/('LAYER_%dKiB.json'%k)),
                          sha256=sha(a.out/('LAYER_%dKiB.json'%k))) for k in (24,16)])
    save(a.out/'SUMMARY.json',summary)
    print(json.dumps(dict(status='PASS',old_us=old['time_us'],new_us=new['time_us'],
                         percent=summary['layer_change_percent'],
                         area55_mm2=summary['covered_area55_mm2'])),flush=True)


if __name__ == '__main__':
    main()
