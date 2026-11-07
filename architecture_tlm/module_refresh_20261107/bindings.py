"""Bind hash-pinned external execution code without publishing private traces."""
from pathlib import Path
import hashlib, importlib.util, json, os, sys

HERE = Path(__file__).resolve().parent

def bind_attention(source=None):
    pin = json.loads((HERE/'ATTENTION_SOURCE.json').read_bytes())
    if source is None:
        source = os.environ.get('PBIT_ATTENTION_SUPPLY_SOURCE')
    if source is None:
        checkout = HERE.parents[1]
        for project in (checkout, checkout.parents[1]):
            candidate = project/'tmp/attention-compare-issue198-20261027/architecture_tlm/attention_supply_front_20261107'
            if candidate.is_dir():
                source = candidate
                break
    if source is None:
        raise FileNotFoundError('Set --attention-source or PBIT_ATTENTION_SUPPLY_SOURCE to the pinned owner execution package; no legacy fallback')
    source = Path(source).resolve()
    for name, digest in pin['execution_sources'].items():
        if hashlib.sha256((source/name).read_bytes()).hexdigest() != digest:
            raise ValueError('Attention execution source changed: '+name)
    name = pin['package']
    if name in sys.modules:
        if Path(sys.modules[name].__file__).resolve() != source/'__init__.py':
            raise ValueError('Different Attention package already bound')
    else:
        spec = importlib.util.spec_from_file_location(name, source/'__init__.py',
            submodule_search_locations=[str(source)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return dict(package=name, public_handoff_commit=pin['public_handoff_commit'],
                execution_sources_sha256=dict(pin['execution_sources']))


def ffn_profile():
    return json.loads((HERE/'FFN_PROFILE.json').read_bytes())


def core_budget(frames, wall_ns, cores, clock_MHz):
    """Gross service energy + stopped-clock residency, without double billing."""
    profile = ffn_profile()
    core = profile['versions'][str(clock_MHz)+'MHz']['core']
    if core is None:
        return dict(status='shortT_C19_PPA_pending', clock_MHz=clock_MHz,
            cores=cores, area55_mm2=None, total_mJ=None,
            reason='Do not transpose SS100 or TT250 T64 energy into shortT250')
    assert core['clock_MHz'] == clock_MHz
    active_ns = 0
    gross_pJ = 0
    for mode, counter in (('GU','GU_frames'),('Wd','Wd_M128_frames')):
        item = core['modes'][mode]
        n = frames.get(counter,0)
        active_ns += n*item['frame_ns']
        gross_pJ += n*item['gross_pJ_per_frame']
    residency_ns = cores*wall_ns
    if active_ns > residency_ns+1e-4:
        raise ValueError('Core service exceeds available residency')
    wait_ns = max(0,residency_ns-active_ns)
    wait_pJ = wait_ns*core['waiting_total_W']*1000
    return dict(status=core['status'], clock_MHz=clock_MHz, cores=cores,
        area55_mm2=cores*core['area55_mm2'],
        active_core_ns=active_ns, waiting_core_ns=wait_ns,
        active_gross_mJ=gross_pJ/1e9, waiting_mJ=wait_pJ/1e9,
        total_mJ=(gross_pJ+wait_pJ)/1e9,
        stopped_waiting_reference_seed=core['waiting_reference_seed'],
        area_factor_already_applied=0.81,
        includes_GF64_SNG_nonlinear_weighted_tree_C19_results_ICG=True,
        excludes=profile['excluded'])
