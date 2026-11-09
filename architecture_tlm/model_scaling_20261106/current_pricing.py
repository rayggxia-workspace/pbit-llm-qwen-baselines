"""Measured component action costs, state residency, and explicit macro reserves.

The same resource budget is shared by all models; native timing does not imply
native DRAM power. Four/6.6/8pJ/bit scenarios retain a distinct external boundary.
"""
from pathlib import Path
import json,math
load=lambda p:json.loads(Path(p).read_bytes())

def price(r,snapshot):
    from architecture_tlm.module_refresh_20261107.bindings import core_budget
    from architecture_tlm.ffn_digital_contract_20261107.adapter import make_profile
    from architecture_tlm.attention_digital_small_20261107.profile import price as att_price
    c=r['clock_MHz'];period=1000/c;T=r['time_ns'];L=r['layers'];a=r['actions'];s=r['shape'];scheme=r['scheme']
    H,F,Q,KV=[s[k] for k in ('hidden','ffn','q_heads','kv_heads')]
    attcal=load(snapshot/'inputs/DIGITAL_ATTENTION_PRICES.json');u=attcal['units'];target=load(snapshot/'architecture_tlm/equal_area_100_250_20261107/TARGETS.json')['versions'][str(c)]
    old=load(snapshot/'inputs/LEGACY_RESIDENCY_PRICES.json')
    other=load(snapshot/'host/architecture_tlm/sram1216_20261106/250MHz/vendor_attention/OTHER_PRICES.json')
    tt=load(snapshot/'host/architecture_tlm/sram1216_20261106/250MHz/vendor_attention/CALIBRATION.json')
    p=make_profile(c,'BF16' if scheme in ('SC_ising','BF16_dense') else 'W8')
    rows=[]
    def add(name,active_uJ=0,resident_uJ=0,basis='calibrated component or declared macro'):
        if min(active_uJ,resident_uJ)<-1e-6:raise ValueError('negative energy '+name)
        rows.append(dict(resource_id=name,activity_uJ=active_uJ,residency_uJ=resident_uJ,total_uJ=active_uJ+resident_uJ,basis=basis))
    ext=sum(z.get('issued_bytes',0) for z in r['memory']['by_kind'].values())
    add('SRAM_all_physical_banks',r['memory']['SRAM']['dynamic_mJ']*1000,r['memory']['SRAM']['leakage_mJ']*1000,'all actual executed R/W;all physical capacity leakage once')
    add('DMA16KiB_capture_and_hold',ext/64*other['capture_pJ_per64B']/1e6,other['DMA24_idle_W']*(16/24)*T/1000,'measured SS holding/capture proxy; controller/PHY separate')
    lanes=(640 if c==100 else 256) if scheme=='SC_ising' else r['allocation']['lanes']
    if scheme=='SC_ising':
        if c==250:
            from whole250.cim_weight_policy import weight_read_cost
            weight_proxy=weight_read_cost(r,12.0293)
            add('CIM_weight_presentation_SRAM_proxy',weight_proxy['additional_uJ'],0,
                'user-selected ordinary TT SRAM read per resident 8KiB tile;writes/area/leakage already in SRAM ledger;no per-sample reread')
        core=core_budget(r['kernel_active'],T,6 if c==100 else 3,c)
        add('FFN_common_core',core['active_gross_mJ']*1000,core['waiting_mJ']*1000,'matched gross service+remaining physical core-time waiting;RNG/nonlinear included')
        prices=old['common']['ab_state32'] if c==100 else dict(active_pJ=52.0366013072,idle_W=.0001372)
        count=a.get('common_state32_vectors',0)
        add('FFN_crossK_state32_arithmetic',count*(prices['active_pJ']-prices['idle_W']*period*1000)/1e6,
            2*prices['idle_W']*T/1000,'measured32update arithmetic;SRAM separately counted')
        sam=a.get('sampler_queries',0);groups=L*KV
        if c==100:
            z=next(x for x in load(snapshot/'inputs/SAMPLER_SS100.json')['cases'] if x['top']=='ab_both')
            idle=z['idle_mW']/1000;duration=z['cycles']*10
            gross=z['query_nJ']*1000;inc=gross-idle*duration*1000
            leak=sum(x['power_W']['leakage'] for x in z['windows'] if x['window']=='idle')/3
            inst=8
        else:
            z=tt['TT250_units']['ab_both']['groups'];idle=z['idle']['total_W'];leak=z['idle']['leakage_W']
            gross=z['work']['gross_pJ_per_operation'];duration=gross/z['work']['total_W']/1000;inc=gross-idle*duration*1000;inst=4
        busy=min(inst*T,sam*duration)
        add('Attention_Ising_P8_service',sam*inc/1e6,(inst*T*leak+busy*(idle-leak))/1000,
            'measured samePVT query+retained unseparated preparation allowance;not actual new-model score statistics')
        selectors=attcal['selectors'][str(c)];inst=8 if c==100 else 4
        for name,z in selectors.items():
            add('Attention_'+name,groups*sum(z['incremental_pJ_per_group'].values())/1e6,
                (inst*T*z['leak_W']+groups*(1730 if 'norm' in name else 979)*period*(z['idle_W']-z['leak_W']))/1000,
                'samePVT selector activity;fixed shared instances;group-dependentwork')
        add('Attention_PV_FP32_ADD',a.get('PV_ADD',0)*u['fpadd']['pJ']/1e6,
            (128 if c==100 else 64)*u['fpadd']['leak_W']*T/1000,'SS FP32 ADD proxy,including250 proxy;FP32 state/capture separate reserve')
        # Control/staging dynamically follows produced addresses and actual
        # packed operand traffic, never a dense V access when only S64 sampled.
        n=a.get('samples',0);unique=a.get('unique_V',0)
        if c==250:
            z=tt['TT250_units']['bf_vctrl4']['groups'];cold=z['cold'];idle=z['idle_gated']
            duration=cold['gross_pJ_per_operation']/cold['total_W']/1000
            inc=cold['gross_pJ_per_operation']-idle['total_W']*duration*1000
            control_active=n*inc/1e6;control_resident=8*idle['leakage_W']*T/1000
            control_basis='sameTT250 measured cold-address control tariff; all-cold upper sensitivity for reuse'
        else:
            control_active=.1*(a.get('PV_ADD',0)*u['fpadd']['pJ']/1e6+n*256/64*other['capture_pJ_per64B']/1e6)
            control_resident=8*2176*other['holding_idle_W_per_byte']*T/1000
            control_basis='SS explicit10% ADD/capture control composition reserve;not measured standaloneVcontrol'
        add('Attention_V_address_control',control_active,control_resident,control_basis)
        front=a.get('wide_score_quantize',0)
        add('Attention_wide_max_gap_P8_front',front*(2*u['fpadd']['pJ']+u['converter']['pJ'])/1e6,
            4*64*other['holding_idle_W_per_byte']*T/1000,'same existing add/convert/capture macro reserve,not newSTA')
        mac=a.get('digital_BF16_MAC',0)+a.get('attention_QK_MAC',0)
        reduction=a.get('digital_FP32_reduce_ADD',0)
        add('shared_FP32_reduction',reduction*p['prices']['reduction']['incremental_pJ']/1e6,
            (32 if c==100 else 16)*p['prices']['reduction']['idle_W']*T/1000,'SS ADD proxy;not extra FMA array')
        format_count=L*(2*H+2*F)
        add('FFN_format_scale_macro',format_count*(u['fpadd']['pJ']+u['converter']['pJ'])/1e6,0,
            'explicit oneADD+convert action reserve per dynamiccode;not measured production quantizer')
        area=target['target_area55_mm2'];area_parts=dict(target='fixed current SC hardware,three models share same chip')
        fifo_B=10240 if c==100 else 8192
    else:
        mac=a.get('digital_BF16_MAC',0)
        for rec in r['digital_FFN']:
            z=rec['actions'];mac+=z.get('BF16_FMA',0)+z.get('W8_BF16_FMA',0)
            add('FFN_digital_call%d'%len(rows),
                (z.get('A9W8_DOT64',0)*p['prices']['integer_GU']['incremental_pJ']+
                 z.get('W8_BF16_FMA',0)*p['prices'].get('decode',{}).get('incremental_pJ',0)+
                 z.get('SwiGLU',0)*p['prices']['nonlinear']['incremental_pJ']+
                 z.get('FP32_reduce_ADD',0)*p['prices']['reduction']['incremental_pJ'])/1e6,0,
                'measured deterministic FFN arithmetic;pool andresidency owned once globally')
        # Each delivered actor's module price contains scalar/capture only.
        # Its standalone FMA and SRAM attribution is removed before summing.
        for rec in r['digital_Attention']:
            z=rec['actions'];mac+=sum(z.get(k,0) for k in ('coarse_QK_MAC','exact_QK_MAC','PV_MAC'))
            dummy=dict(configuration=rec['configuration'],actions=z,time_ns=1,lanes=lanes,
                memory=dict(SRAM=dict(dynamic_mJ=0),by_kind={}))
            cost=att_price(dummy)
            active=sum(v for k,v in cost['incremental_uJ'].items() if k!='shared_FMA')
            active+=sum(v for k,v in cost['active_clock_uJ'].items() if k!='shared_FMA')
            add('Attention_digital_call%d'%len(rows),active,0,'delivered exact digital scalar/capture actions;FMA/SRAM owned byhost')
        inst=r['digital_FFN'][0]['profile'] if r['digital_FFN'] else p
        add('FFN_digital_fixed_residency',0,T/1000*(inst['NL_units']*p['prices']['nonlinear']['idle_W']+
            (inst['GU_units']*p['prices']['integer_GU']['idle_W'] if scheme!='BF16_dense' else 0)+
            p['reduction_units']*p['prices']['reduction']['idle_W']),
            'measured nonzero idle upper bound;root gating sensitivity retained')
        add('Attention_digital_fixed_residency',0,T/1000*8*sum(u[k]['leak_W']*n for k,n in [('fpadd',8),('explut',4),('fpmul',1),('recseed',1),('converter',1)]),
            'digital shared scalar instance leakage;active increments in per-group ledger')
        area=r['allocation']['area55_mm2'];area_parts=r['allocation'];fifo_B=r['allocation']['projection_FIFO_payload_bytes']
    pool=attcal['pools'][str(c)];idle=pool['idle_W'];leak=pool['leak_W'];busy=min(lanes/16*T,mac/16*period)
    add('shared_BF16_FMA_pool',mac*pool['incremental_pJ']/1e6,(lanes/16*T*leak+busy*(idle-leak))/1000,
        'one measured FMA pool;incremental activity+leakage andactiveclock,not gross+full idle')
    captured=a.get('ordinary_FIFO_capture_bytes',0)+sum(z['actions'].get('input_FIFO_capture_bytes',0) for z in r['digital_FFN'])
    add('projection_and_FFN_input_FIFO',2*captured/64*other['capture_pJ_per64B']/1e6,
        fifo_B*other['holding_idle_W_per_byte']*T/1000,'actualfiniteFIFO words;capture+select proxy;allocated payloadarea once')
    factor=(6*H+(Q+KV)*128)/(6*2560+40*128)
    add('RMSNorm_RoPE_residual_vector_macro',L*factor*other['vector_uJ_per_layer'],0,'existingSS vector-action reserve scaled by channel/head work,not SRAM traffic')
    add('shared_vector_format_and_activation_residency',0,
        (other['format_idle_W']+other['activation_hold_bytes']*other['holding_idle_W_per_byte'])*T/1000,
        'existing shared format/hold state cost,already in area,not allocated again per layer')
    energy=math.fsum(x['total_uJ'] for x in rows);assert len({x['resource_id'] for x in rows})==len(rows)
    total={str(e):energy/1000+ext*8*e/1e9 for e in (4.,6.6,8.)}
    return dict(status='CLOSED_DECLARED_COMPONENT_MODEL_NOT_PHYSICAL_CHIP',energy_sum_closed=True,
        area55_mm2=area,area_allocation=area_parts,onchip_mJ=energy/1000,external_bytes=ext,
        external_mJ_by_pJbit={str(e):ext*8*e/1e9 for e in (4.,6.6,8.)},system_mJ_by_pJbit=total,
        average_W_by_pJbit={k:v/(T/1e6) for k,v in total.items()},components=rows,
        no_28nm_mixing=True,new_circuit_PPA=False,all_physical_costs_measured=False,
        boundary=['native LPDDR timing;external pJbit energy sensitivity,not native power',
          'CIM weight interface at250 uses ordinary SRAM energy proxy;PHY/fullCTS/NoC outside calibrated boundary',
          'SS scalar/vector/conversion proxies retained at250',
          'sampled control and format macro energy explicitly estimated,0.5x/2x sensitivity',
          'logical QK/PV4-slot padding work preserved; no quality claim or maximal mapping claim'])
