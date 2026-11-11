"""Explicit conditional full-token extrapolation; does not modify strict ledgers."""
from pathlib import Path
from types import SimpleNamespace as NS
import copy,csv,hashlib,json,math
from whole_pricing import price

ROOT=Path(__file__).resolve().parents[2];WS=ROOT.parents[1]
BASE=ROOT/'work/rayggxia/225/process28_whole_20261109'
OUT=ROOT/'architecture_tlm/process_28nm/rough_estimate_20261109';OUT.mkdir(exist_ok=True)
SOURCES={}
def read(p):
    p=Path(p);b=p.read_bytes();SOURCES[str(p)]=hashlib.sha256(b).hexdigest();return json.loads(b)
def save(n,x):(OUT/n).write_bytes((json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf8'))
cacti=read(ROOT/'work/rayggxia/225/process28_rough_20261109/CACTI_PARSED.json')
p28=cacti['results']['28'];p55=cacti['results']['55']
# Exact previous55 macro E TT as a sensitivity-transfer anchor, NOT28 library calibration.
anchorfile=WS/'architecture_tlm/results/sram_calibration_v1_20261016/exact_macro_table.csv'
SOURCES[str(anchorfile)]=hashlib.sha256(anchorfile.read_bytes()).hexdigest()
e=next(x for x in csv.DictReader(anchorfile.read_text(encoding='utf-8-sig').splitlines()) if x['id']=='E' and x['corner']=='TT')
anchor=dict(area_mm2=float(e['area_mm2'])*.81,read_pJ=float(e['read_internal_pJ']),
    write_pJ=float(e['write_internal_pJ']),leakage_W=float(e['ce_off_leakage_W']))
sram={k:p28[k]*anchor[k]/p55[k] for k in anchor}
summary=read(WS/'architecture_tlm/module_handoff/attention_tlm28_250_500_20261108/PPA_SUMMARY.json')
cases=[]
for mhz,name,nlayers in [(250,'closed250_v3',2),(500,'closed500_v3',1)]:
    original=read(BASE/name/'RESULT.json');binding=read(ROOT/('architecture_tlm/process_28nm/%sMHz/BINDINGS.json'%mhz))
    seal=read(BASE/name/'SEAL.json')
    assert seal['files_sha256']['RESULT.json']==SOURCES[str(BASE/name/'RESULT.json')]
    # SEAL validation itself is recorded by verify_whole; preserve source bytes.
    probes={n:read(BASE/('head_%s_%s'%(mhz,n))/'RESULT.json') for n in (1024,1152,2048)}
    for n,x in probes.items():
        s=read(BASE/('head_%s_%s'%(mhz,n))/'SEAL.json')
        assert s['files_sha256']['RESULT.json']==SOURCES[str(BASE/('head_%s_%s'%(mhz,n))/'RESULT.json')]
        assert x['MAC']==n*2560 and x['external_bytes']==n*5120
    slope=(probes[2048]['head_duration_ns']-probes[1024]['head_duration_ns'])/4
    intercept=probes[1024]['head_duration_ns']-4*slope
    tail=probes[1152]['head_duration_ns']-probes[1024]['head_duration_ns']
    full,rem=divmod(151936,256);assert (full,rem)==(593,128)
    head=intercept+full*slope+tail
    phases=original['phases'];embed=next(x['duration_ns'] for x in phases if x['stage']=='embedding')
    layer_ns=[sum(x['duration_ns'] for x in phases if x['layer']==i) for i in range(nlayers)]
    body=embed+layer_ns[0]+35*layer_ns[-1]+52*(1000/mhz)
    stage={s:sum(x['duration_ns'] for x in phases if x['stage']==s and x['layer']>=0)/nlayers*36/1e6 for s in ('QKV','O','attention','GU','NL_Wd')}
    r=copy.deepcopy(original);factor=36/nlayers;probe_rows=original.get('head_probe_rows',0) if original['includes_lm_head'] else 0
    for field in ('actions','process28_counts','kernel_active'):
        r[field]={k:v*factor for k,v in original[field].items() if isinstance(v,(int,float))}
    body_mac=(original['actions']['digital_BF16_MAC']-probe_rows*2560)*factor
    headmac=151936*2560
    r['actions']['digital_BF16_MAC']=body_mac+headmac
    r['time_ns']=body+head
    # Eliminate partial-run future norm prefetch; full model has two norms/layer + final.
    normbytes=36*(2*5120+512)+5120
    external={k:v['issued_bytes']*factor for k,v in original['memory']['by_kind'].items() if k not in ('embedding','norm_weight_stream','lm_head_weights')}
    external.update(embedding=5120,norm_weight_stream=normbytes,lm_head_weights=151936*5120)
    r['memory']['by_kind']={k:dict(issued_bytes=v) for k,v in external.items()}
    counts=dict(read_words=0,write_words=0)
    for tag,values in original['SRAM']['by_tag'].items():
        for mode in counts:
            z=values.get(mode,0)
            if tag=='embedding_fill':v=z
            elif tag=='norm_weight_stream_fill':v=normbytes/16
            elif tag in ('norm_activation','norm_gamma','norm_output'):v=(36*2+1)*320
            elif tag=='lm_head_weights_fill':v=151936*320
            elif tag=='lm_head_activation_to_local':v=320
            elif tag=='ordinary_weight_FIFO':v=(z-probe_rows*320)*factor+151936*320
            else:v=z*factor
            if z or (tag in ('norm_activation','norm_gamma','norm_output') and mode in values):counts[mode]+=v
    if not original['includes_lm_head']:
        counts['write_words']+=151936*320
        counts['read_words']+=320
    r['SRAM']['counts']=counts
    m=NS(common_cores=3 if mhz==250 else 2,sampler_pool=NS(slots=4),norm_pool=NS(slots=4),top_pool=NS(slots=4))
    ledger=price(m,r,binding);rows=ledger['rows']
    #500 FMA remains an explicit same-process250 price scenario, not qualified500 PPA.
    if mhz==500:
        b250=read(ROOT/'architecture_tlm/process_28nm/250MHz/BINDINGS.json')['shared_FMA']
        ops=r['actions']['digital_BF16_MAC']+r['actions']['attention_QK_MAC'];idle=b250['idle_W']
        rows[-1].update(area_mm2=16*b250['area_mm2'],incremental_activity_mJ=ops*(b250['gross_pJ_per_FMA']-idle*1052/4096*1000)/1e9,
            full_residency_idle_mJ=idle*16*r['time_ns']/1e6,basis='EXPLICIT500MAC_PROXY: same28nm250MHz FMA16/C4 price,STA500unqualified')
        rows[-1]['energy_mJ']=rows[-1]['incremental_activity_mJ']+rows[-1]['full_residency_idle_mJ']
    pv={x['top']:x for x in binding['diagnostic_PV_cards']}
    vacc=pv['bf_vacc16'];ctrl=pv['bf_vctrl4']
    raw=next(x for x in reversed(summary['rows']) if x.get('top')=='bf_vacc16' and x.get('MHz')==mhz and x.get('cell_area28_mm2'))
    groups=raw['cell_area28_mm2'];fixed=groups['register']+groups['icg']
    # All128 FP32 state/head kept; only remaining arithmetic/control fraction is width-scaled.
    pvarea=32*(fixed+groups['other_logic']*2/16)+8*ctrl['area28_mm2']
    pvenergy=(r['actions']['PV_ADD']*vacc['modes']['stream']['gross_pJ_per_op']+
        r['actions']['samples']*ctrl['modes']['cold']['gross_pJ_per_op'])/1e9
    pvidle=(32*vacc['modes']['idle_gated']['power_mW']+8*ctrl['modes']['idle_gated']['power_mW'])*r['time_ns']/1e9
    pvenergy+=pvidle
    # Measured28 register-cell area anchors DMA16KiB, operandFIFO8KiB and4KiB descriptor macro.
    window=next(x for x in raw['windows'] if x.get('groups',{}).get('registers',{}).get('cells'))
    reg=window['groups']['registers'];reg_bit_area=reg['area_um2']/reg['cells']/1e6
    storagearea=28*1024*8*reg_bit_area
    knownarea=sum(x['area_mm2'] for x in rows)
    # Named macro allowances (not circuit data); intentionally kept outside strict price cards.
    macro_area=.25+.15 # vector/reductions + CIM programming/local distribution
    activecore_area=knownarea+pvarea+storagearea+macro_area+240*sram['area_mm2']
    area=activecore_area*1.15 # explicit15% placement/local-control allowance, not die floorplan
    area_low=(knownarea+pvarea*.85+storagearea*.8+.2+240*p28['area_mm2'])*1.05
    area_high=(knownarea+(0.5 if mhz==500 else 0)+32*vacc['area28_mm2']+8*ctrl['area28_mm2']+storagearea*1.3+.8+240*sram['area_mm2']*1.4)*1.25
    sram_energy=(counts['read_words']*sram['read_pJ']+counts['write_words']*sram['write_pJ'])/1e9+240*sram['leakage_W']*r['time_ns']/1e6
    knownenergy=sum(x['energy_mJ'] for x in rows)
    #20--80mW unpriced DMA/FIFO/vector/interface activity+idle scenario, central40mW.
    macroenergy=.04*r['time_ns']/1e6
    chip=knownenergy+pvenergy+sram_energy+macroenergy
    dram_bytes=sum(external.values());external_mJ={str(e):dram_bytes*8*e/1e9 for e in (4.,6.6,8.)}
    total=chip+external_mJ['4.0']
    # Matched counterfactual removing readout work, while hardware remains resident.
    fma_row=rows[-1];fma_dynamic_per_op=fma_row['incremental_activity_mJ']/(body_mac+headmac+r['actions']['attention_QK_MAC'])
    chip_without=chip-headmac*fma_dynamic_per_op-(151936*320*(sram['read_pJ']+sram['write_pJ']))/1e9
    chip_without-=head/1e6*(.04+sum(z['full_residency_idle_mJ'] for z in rows)/(r['time_ns']/1e6)+240*sram['leakage_W'])
    chip_without-=pvidle*head/r['time_ns']
    without=chip_without+(dram_bytes-external['lm_head_weights'])*8*4/1e9
    assert body>0 and head>0 and dram_bytes/r['time_ns']<136.4606
    cases.append(dict(clock_MHz=mhz,FFN_cores=m.common_cores,area_mm2=area,area_scenario_interval_mm2=[area_low,area_high],
        time_ms=(body+head)/1e6,time_without_lm_head_ms=body/1e6,lm_head_ms=head/1e6,throughput_token_s=1e9/(body+head),
        chip_energy_mJ=chip,total_energy_mJ_at4pJbit=total,total_without_lm_head_mJ_at4pJbit=without,
        chip_average_W=chip/((body+head)/1e6),system_average_W_at4pJbit=total/((body+head)/1e6),
        energy_scenarios_mJ={k:chip+v for k,v in external_mJ.items()},external_bytes=dram_bytes,
        external_mJ=external_mJ,DRAM_ideal_floor_ms=dram_bytes/136.4606/1e6,
        SRAM_counts=counts,SRAM_energy_mJ=sram_energy,SRAM_area_mm2=240*sram['area_mm2'],
        component_rows=rows,PV_proxy=dict(area_mm2=pvarea,energy_mJ=pvenergy,timing_failed=True,fixed_state_preserved=True),
        other_macros=dict(register_storage_area_mm2=storagearea,register28_mm2_per_cell=reg_bit_area,
           vector_and_interface_area_mm2=macro_area,average_power_W=.04,energy_mJ=macroenergy),
        phase_projection_ms=stage,head_fit=dict(full256_tiles=593,tail_rows=128,slope_ns_per256=slope,intercept_ns=intercept,tail_increment_ns=tail),
        evidence='small finite-bank/DMA TLM + explicit36-layer/whole-head extrapolation;not completed36-layer run'))
save('RESULTS.json',dict(status='CONDITIONAL_ROUGH_SYSTEM_ESTIMATE_NOT_SIGNOFF',model='Qwen/Qwen3-4B',batch=1,context=2048,
    protocol='decode,36layers,K128,S64,GU16/Wd32,W8,BF16QKVO/lm_head,960KiB240banks,136.4606GBps30nsanalyticDRAM',
    area_scope='core subsystem including SRAM,local control/placement reserves;excludes external DRAM die,LPDDRPHY,pads,CPU,package',
    power_scope='core estimate plus external pJbit scenario;not board power or peak power',
    new_cacti=cacti,SRAM_cross_process_residual_transfer=sram,SRAM_transfer_is_28_foundry_calibration=False,
    macro_ranges=dict(other_average_power_W=[.02,.08],placement_factor=[1.05,1.25],system_time_native_margin_fraction=[0,.12]),cases=cases))
SOURCES[str(Path(__file__))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
save('SOURCES.json',dict(files_sha256=SOURCES))
for x in cases:print(json.dumps({k:x[k] for k in ('clock_MHz','time_ms','time_without_lm_head_ms','area_mm2','area_scenario_interval_mm2','chip_energy_mJ','total_energy_mJ_at4pJbit','system_average_W_at4pJbit')}))
