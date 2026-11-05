"""Run three representative layers of Attention, with all eight groups live."""
from pathlib import Path
import argparse,json,hashlib,time,sys
from collections import Counter
from architecture_tlm.digital_baselines_20261104.factory import make_model
from architecture_tlm.digital_baselines_20261104.backend import RamulatorBackend
from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
from adapter import install,SAMPLED

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(d,indent=2)+'\n').encode())
def main():
    p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True)
    p.add_argument('--mode',required=True);p.add_argument('--seed',type=int,default=17)
    p.add_argument('--timing',default='late');p.add_argument('--out',type=Path,required=True)
    p.add_argument('--analytic',action='store_true');p.add_argument('--layers',type=int,default=3)
    a=p.parse_args();base=a.runtime;start=time.time()
    a.out.mkdir(parents=True,exist_ok=False)
    if (base/'SOURCE_MANIFEST.json').exists():
        manifest=json.loads((base/'SOURCE_MANIFEST.json').read_bytes())
        for rel,digest in manifest['files_sha256'].items():assert sha(base/rel)==digest,rel
    profiles=json.loads((base/'profiles/PROFILES.json').read_bytes())
    profile=next(v for v in profiles if v['name']=='derived8533')
    backend=AnalyticDRAM(bandwidth_GBs=136.4606) if a.analytic else RamulatorBackend(base/'liblpbridge.so',base/'profiles/derived8533.yaml',profile['period_ns'],256)
    raw=json.loads((base/'representative.json').read_bytes());sample=json.loads((base/'SAMPLES.json').read_bytes())
    h,m=make_model(backend,'D_W8_screen',layers=a.layers,include_lm=False,seed=a.seed,attention_input=raw)
    install(m,a.mode,sample,a.timing)
    for layer in range(a.layers):m.phase('attention',[m.attention_group(layer,g) for g in range(8)],layer)
    memory=h.report();z=memory['ingress']
    assert memory['final_pending']==memory['final_response_occupied']==0
    assert z['captured_beats']==z['forwarded_beats']==z['landed_beats']
    assert z['final_queued']==z['final_tracked_ids']==0 and not h.mem.queue
    assert all(x<=d for x,d in zip(h.mem.bank_allocated,h.mem.bank_depths))
    native=backend.finish(h.now);total=memory['counts']['dram_read_bytes']+memory['counts']['dram_write_bytes']
    if not a.analytic:assert native['counts']['logical64_completed']*64==total
    acts=dict(m.actions)
    if a.mode in SAMPLED:
        assert acts['PV_ADD']==acts['samples']*128
        assert acts['sampler_queries']==a.layers*32
        assert acts['unique_V']*256==memory['by_kind']['sample_V']['read_bytes']
        assert not acts.get('attention_PV_MAC',0)
    else:assert acts['attention_PV_MAC']==a.layers*32*(2048 if a.mode.startswith('dense') else 128)*128
    r=dict(mode=a.mode,seed=a.seed,timing=a.timing,layers=a.layers,context=2048,
        status='completed',simulated_ms=h.now*1e-6,phases=m.phases,actions=acts,
        compute=dict(m.compute),memory=memory,native=native,
        adapter=m.attention_adapter_contract,capacity=dict(allocated=h.mem.top,bytes=h.mem.capacity,per_bank=h.mem.bank_allocated),
        input_sha256=sha(base/'representative.json'),samples_sha256=sha(base/'SAMPLES.json'),
        config_sha256=sha(base/'profiles/derived8533.yaml'),
        source_manifest_sha256=sha(base/'SOURCE_MANIFEST.json') if (base/'SOURCE_MANIFEST.json').exists() else None,
        scope='Attention only;three captured layers,not whole36 or new model quality',
        PPA_measured=False,PPL_measured=False,external_power_native=False,wall_seconds=time.time()-start)
    save(a.out/'RESULT.json',r);save(a.out/'SEAL.json',dict(result_sha256=sha(a.out/'RESULT.json')))
    print(json.dumps(dict(mode=a.mode,seed=a.seed,timing=a.timing,us_per_layer=h.now/a.layers/1000,wall_seconds=time.time()-start)))
    backend.close()
if __name__=='__main__':main()
