"""Read existing evidence only. Never run EDA, relocate originals or publish libraries."""
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tarfile

ROOT = Path('C:/Users/86134/Documents/a_P_BIT')
REPO = Path(__file__).resolve().parents[3]
OUT = REPO / 'digital_circuit_simulation_registry'
APR = Path('C:/Users/86134/Documents/10月_MPW/APR_results')
BASE = 'eb317e4f6fb1b0d8844887401f3275f128ef8a83'
SHA_CACHE = {}
RECORDS = []


def sha(p):
    p = Path(p)
    if p not in SHA_CACHE:
        h = hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda: f.read(1024 * 1024), b''):
                h.update(b)
        SHA_CACHE[p] = h.hexdigest()
    return SHA_CACHE[p]


def dump(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def evidence(rel, role='summary', required=True):
    p = Path(rel)
    if not p.is_absolute():
        p = ROOT / p
    e = dict(path=p.as_posix(), role=role, present_at_registration=p.is_file(), required=required)
    if p.is_file():
        e.update(bytes=p.stat().st_size, sha256=sha(p))
    else:
        e.update(bytes=None, sha256=None, missing_reason='原报告引用的位置目前不在本地；保留定位，不能写成已核实原件')
    return e


def tar_read(path, suffix):
    with tarfile.open(path) as t:
        members = [m for m in t.getmembers() if m.isfile() and m.name.endswith(suffix)]
        if not members:
            raise ValueError((str(path), suffix))
        m = sorted(members, key=lambda x: (x.name.count('/'), x.name))[0]
        b = t.extractfile(m).read()
        e = evidence(path, 'archive')
        e.update(member=m.name, member_bytes=len(b), member_sha256=hashlib.sha256(b).hexdigest())
        return json.loads(b), e


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8-sig'))


def stages(functional='not_run', synthesis='not_run', sta='not_run', power='not_run', postlayout='not_run'):
    return dict(functional=functional, synthesis=synthesis, sta=sta, power=power, postlayout=postlayout)


def record(id, name, family, level, status, report, stage, description, limits, cases=None, extra=None, source=None, pvt=None, next_action='仅在匹配模块边界、PVT和活动时复用；不重复运行已有健康结果'):
    x = dict(schema_version=1, id=id, name=name, family=family,
        registered_on='2026-10-22', owner='jieruiz', issue=110,
        evidence_level=level, status=status, stages=stage,
        boundary=description, conditions=pvt or {}, limitations=limits,
        source=source or dict(git_commit=None, binding='旧实验源以原manifest/源文件SHA为准，未将当前HEAD冒认为执行版本'),
        artifacts=[evidence(report)] + (extra or []), cases=cases or [],
        next_action=next_action,
        review='本任务只读登记/校验原件与现有审核；未重跑RTL/DC/PT/STA，未独立重放全部VCD')
    RECORDS.append(x)
    return x


def csv_read(rel):
    return list(csv.DictReader((ROOT / rel).open(encoding='utf-8-sig', newline='')))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pvt_ss = dict(node_nm=55, corner='SS', voltage_V=1.08, temperature_C=125, clock_MHz=100,
        activity='合成事务；不是模型激活或硅片实测', sdf=False, spef=False, cts=False)
    sc_limits = ['64输入×单输出，不是64×64阵列；权重存储为DFF。',
        '零延迟门级活动驱动布局前PT，外部随机源/物理熵/PLL/IO/CTS/布线不在范围。',
        'OR为有损算法；fixed低占空与满速MAC不同；不同批次接口/种子不同，不能按总数公平排名。']
    comparison = 'sc_architecture_power_comparison_20261014/'
    rows = csv_read(comparison + '全部架构_72组数据.csv')
    for job, title, folder in [('37962470', '旧精确树 / 全64路OR / 低占空定点 / 独立比较器', 'legacy_37962470'),
                               ('37981139', '同批精确树与CSA压缩器对照', 'csa_37981139'),
                               ('38015538', '分组OR 1/2/4/8 × 缓存1/4/8拍', 'grouped_38015538')]:
        cases = [r for r in rows if r['job'] == job]
        record('sc-' + job, title, 'FFN随机矩阵', 'DC_GATE_PT_PRELAYOUT', 'completed_provisional',
            comparison + '00_先看这里_架构功耗对比.txt', stages('pass','completed','reported_review','calculated'),
            '按该批完整被测顶层计费；原表保留所有活动、帧长、面积、范围和误差，不只选最低功耗。',
            sc_limits + (['当前无ICG缓存增加能量；G/B变化不能等同精度。'] if job=='38015538' else []),
            cases, [evidence(comparison+'全部架构_72组数据.csv','numeric_table'),
                    evidence(comparison+'source_manifest.json','provenance'),
                    evidence(comparison+'sources/'+folder+('/verification.json' if job=='38015538' else '/manifest.json'),'provenance')], pvt=pvt_ss)
    record('sc-37962379-partial', '旧OR初始化失败前的精确树结果', '历史诊断', 'DC_GATE_PT_PRELAYOUT', 'partial_superseded',
        'sc_weighted_rtl_20261011/任务37962379功耗与诊断.txt', stages('partial','completed','reported_review','partial'),
        'exact四活动已完成；OR初始化失败；fixed/encoder未跑；不能标整批通过。',
        ['后续37962470为完整批，不把两批重复累加为新独立实验。'], pvt=pvt_ss)
    record('sc-38014357-partial', '分组OR旧覆盖率解析失败批', '历史诊断', 'DC_GATE_PT_PRELAYOUT', 'partial_superseded',
        'sc_grouped_or_cache_20261013/diagnosis_38014357/诊断总结.txt', stages('partial','completed','reported_review','partial'),
        '12设计只有case0门级/PT；解析器中断，其他活动未跑。',
        ['case0不是门控idle；新38015538另有48完整case；不重复算完成数。'], pvt=pvt_ss)

    sram_report='architecture_tlm/SRAM_PT_CHARACTERIZATION_ANSWERS_ZH_20261016.txt'
    sramlimits=['SS hold未收敛；完整DUT历史X/Z边界审查未闭合，访问能量保留暂定标记。',
        'CE关闭动态为库缺项下PT结果，不证明真实动态为零；无NAP/RET/PWD。',
        '宏和标准单元面积之和，不含halo/通道/完整CTS；四宏只有64个9bit权重输出。']
    comp=csv_read('sram_q3_review_20261016/analysis/comparison.csv')
    for id,name,side,job in [('sram-38068649-1','四SRAM OR4完整主模块','sram','38068649_1'),
                              ('dff-38057668-0','门控DFF OR4完整主模块对照','dff','38057668_0')]:
        cases=[dict(case=r['case'],phase=r['phase'],power_uW=float(r[side+'_uW']), energy_nJ=float(r[side+'_nJ']),
            area_um2=float(r[side+'_area_um2']), setup_slack_ns=float(r[side+'_slack_ns']),hold_slack_ns=float(r[side+'_hold_ns']),
            xz_codes=int(r[side+'_xz']),status=r['status']) for r in comp]
        record(id,name,'权重存储与OR4','DC_GATE_PT_PRELAYOUT','completed_provisional',sram_report,
            stages('pass','completed','violations' if side=='sram' else 'reported_review','calculated'),
            '包含概率/符号及有效位寄存器、OR4、控制；计算/预读/配置窗口分开，不能只收费宏漏电。',
            sramlimits,cases,[evidence('sram_q3_review_20261016/analysis/comparison.csv','numeric_table'),
                evidence(APR/('result_'+job+'.tar.gz'),'archive'),
                evidence('sram_q3_review_20261016/analysis/comparison.provenance.json','provenance')],pvt=pvt_ss)
    states_path='tmp/sram_review_38068649/38068650/characterization.csv'
    state_cases=csv_read(states_path) if (ROOT/states_path).is_file() else []
    record('sram-38068650-states','四SRAM S0–S5读写/保持/重启标定','SRAM状态','DC_GATE_PT_PRELAYOUT','completed_provisional',
        sram_report,stages('pass','completed','violations','calculated'),
        '四个32×144宏＋ICG/OR4/标定控制；宏与全标定模块能量分开。',sramlimits,
        state_cases,[evidence(states_path,'numeric_table',False),evidence('tmp/sram_review_38068649/38068650/summary.json','raw_summary',False)],pvt=pvt_ss)
    lib_cases=csv_read('architecture_tlm/SRAM_CALIBRATION_DATA_38071895/macro_summary.csv')
    record('sram-38071895-library','A–F/H共14组SS/TT宏库提取','SRAM库表征','LIBRARY_EXTRACTION','completed_with_missing_geometry',
        'architecture_tlm/SRAM_CACTI_EXISTING_RESULTS_SS_TT_ZH_20261016.txt',stages('not_run','library_only','library_only','library_only'),
        '.lib/.lef/.ds提取面积、内部事件能量、漏电、时序；A–F拟合/H独立验证；G两角生成失败。',
        ['42行对应14宏/PVT×3负载点，不能叫42次PT。','F/H SS最小周期超过10ns，不能默认100MHz每拍访问。','不上传厂商库本体；库值不等于接口STA或硅片测量。'],
        lib_cases,[evidence('architecture_tlm/SRAM_CALIBRATION_DATA_38071895/macro_summary.csv','numeric_table'),
          evidence('architecture_tlm/SRAM_CALIBRATION_DATA_38071895/manifest.csv','provenance'),evidence(APR/'sram_calibration_38071895.tar.gz','archive')],
        pvt=dict(node_nm=55,corners=['SS1.08V125C','TT1.20V25C'],clock_MHz=None))
    record('sram-38070775-tt-library','旧32×144 TT宏生成与库提取','SRAM库表征','LIBRARY_EXTRACTION','generation_only',
        'architecture_tlm/SRAM_PT_CHARACTERIZATION_ANSWERS_TT_ZH_20261016.txt', stages('not_run','library_only','library_only','library_only'),
        'TT模型/LC转换成功；截至答复没有该版本TT主模块/S0–S5的完整DC/VCS/PT。',
        ['TT库能量可读，不能冒称已有TT完整模块PPA；后续多宏库提取见38071895。'],
        extra=[evidence(APR/'sram_generation_38070775.tar.gz','archive')],pvt=dict(node_nm=55,corner='TT',voltage_V=1.2,temperature_C=25))
    record('sram-cacti-v1','SRAM CACTI校准探索模型','SRAM估计','CALIBRATED_ESTIMATE','estimate_only',
        'architecture_tlm/SRAM_CACTI_CALIBRATION_V1_RESULTS_ZH_20261016.txt', stages(),
        '用已有库点拟合未生成组织；不是新的数字电路仿真。',
        ['H独立验证写能量误差64–73%，不能声称全指标误差10%；现成几何应直接查库。'])

    epdir='tmp/ffn-epilogue-ppa-20261017/architecture_tlm/results/ffn_epilogue_ppa100_38100634/'
    ep_audit=load(epdir+'AUDIT.json')
    for i,corner in enumerate(['TT','SS']):
        path=APR/('38100634_'+str(i)+'.reports.tar.gz')
        cases,ev=tar_read(path,'/summary.json')
        record('swiglu-38100634-'+corner.lower(), 'Q10 SwiGLU单通道 '+corner, 'FFN非线性与乘积','DC_GATE_PT_PRELAYOUT','completed_provisional',
            epdir+'RESULTS_ZH.txt', stages('pass','completed','reported_nonnegative','calculated'),
            'g/u16bit Q10→z24bit Q10；4级流水II=1；LUT＋两级乘法＋舍入饱和＋寄存器。每角18case。',
            ['不是FP32/new数字v1或完整FFN成本；合成full/central分布。','TT有单pin表范围警告；SS setup约13.3ps裕量；无CTS/SPEF/SDF。','idle能量/结果无定义，不能填0；不得再重复加入时钟内部功耗。'],
            cases,[ev,evidence(epdir+'AGGREGATE.csv','numeric_table'),evidence(epdir+'AUDIT.json','provenance')],
            source=dict(git_commit='dac6e0426da6421ccc62077275e236532ca3c3da',binding='v2–v4本地补丁：精确源以manifest为准',
                source_manifest_sha256=ep_audit[i]['config']['source_manifest_sha256']),
            pvt=dict(node_nm=55,corner=corner,voltage_V=1.2 if i==0 else 1.08,temperature_C=25 if i==0 else 125,clock_MHz=100,sdf=False,spef=False,cts=False))
    for job,version,stage,desc in [('38099357','v2',stages('failed','completed','reported_nonnegative','not_run'),'TT/SS DC成功，TB顶层绑定失败，未产生PT功耗。'),
                                  ('38099581','v3',stages('partial','reused','reused','not_run'),'每角首场景黄金核对成功；dump库notifier后XZ审计停止，PT未开始。')]:
        record('swiglu-'+job+'-history','SwiGLU '+version+'诊断历史','历史诊断','PARTIAL_FLOW','partial_superseded',
            'tmp/ffn-epilogue-ppa-20261017/work/jieruiz/7/epilogue_ppa/LOCAL_REVIEW_'+job+'.txt',stage,
            desc,['后续38100634复用DC并完成新活动/PT，不能重复统计为独立综合。'])

    rng_report='远端上传/rng_service_v1_20261022/architecture_tlm/random_service/POWER_RESULTS_38322118_ZH_20261022.txt'
    scopes={'lfsr':'LFSR32＋1个8bit字＋比较/种子/端点控制',
            'gf64':'GF64映射64个8bit字＋64路比较＋端点控制；非64独立熵源',
            'bivium':'177bit状态/160bit展开，20个8bit字＋20比较，5拍预热',
            'ffn':'单8bit字共享64阈值比较＋阈值保持/回压；不是整个FFN'}
    for core in scopes:
        for freq in [100,300,500]:
            path=APR/(core+'_'+str(freq)+'MHz_reports.tar.gz')
            cases,ev=tar_read(path,'/summary.json')
            source,sv=tar_read(path,'/source_manifest.json')
            timing_ok=all(c['setup_slack_ns']>=0 and c['hold_slack_ns']>=0 for c in cases)
            rec=record('rng-38322118-'+core+'-'+str(freq),core.upper()+'服务端点 '+str(freq)+'MHz','随机源服务',
                'DC_GATE_PT_PRELAYOUT','completed_provisional',rng_report,
                stages('pass','completed','reported_nonnegative' if timing_ok else 'violations','calculated'),
                scopes[core]+'；18门级用例/21PT窗口，3seed=17/503/1009。',
                ['所有结果CALCULATED_PROVISIONAL；PWR-981/库表外告警不因覆盖率100%消失。',
                 '无SDF/CTS/SPEF/物理熵源/健康调理/额外CDC/全局长线与完整sigmoid。',
                 '生成帧与消费帧、idle/burst/stall/启动/reseed分开；不同输出宽度不能只按pJ/帧排名。',
                 '默认1e8拍换种；测试reseed300为独立网表，不能混入部署平均。'],cases,
                [ev,sv,evidence('analog_pbit_20261016/digital_rng_38322118_review_20261022/audit.json','prior_audit')],
                source=dict(git_commit=None,local_fix_commit_short='00a8b43',source_manifest_sha256=sv['member_sha256'],
                    binding='v3归档内source_manifest逐字节；本地未发布执行补丁，不用集成HEAD替代'),
                pvt=dict(**pvt_ss,nominal_MHz=freq,effective_MHz=cases[0]['effective_MHz'],clock_ns=cases[0]['clock_ns']))
            rec['conditions']['clock_MHz']=cases[0]['effective_MHz']
            rec['remote_results']='/public3/home/t6s011227/pbit_chimera_pipeline_20260920/rng_ppa_freq_20261022_v3/results/38322118/'+core+'_'+str(freq)+'MHz/'
    record('rng-38321781-smoke','LFSR v2单seed smoke与v3只读重汇总','历史诊断','DC_GATE_PT_PRELAYOUT','partial_superseded',
        'tmp/rng-ppa-issue95-20261022/architecture_tlm/random_service/ppa100/SMOKE_REVIEW_38321781_ZH.txt',
        stages('partial','completed','reported_nonnegative','partial'),
        'DC/stream PT已完成；旧摘要单位解析失败，v3只读重汇总；无完整矩阵FLOW_COMPLETE。',
        ['原包同名lfsr_100MHz，SHA2259d693不同于38322118正式矩阵，禁止按文件名复用。'],
        extra=[evidence('tmp/rng-ppa-issue95-20261022/work/jieruiz/95/review_units_20261022/lfsr_100MHz/reanalysis_units_v3_final/summary.json','numeric_table')],pvt=pvt_ss)
    record('rng32x64-20261015','早期LFSR32→64字数学/RTL草案','随机源功能与设计','DESIGN_PROOF','design_only',
        'rng32x64_design_20261015/README.md',stages('model_checks'),
        '四个GF线性展开候选；XOR计数/代数秩是结构分析。',
        ['早期报告未做HDL/工艺综合；新GF服务端点见38322118，边界不同。'],
        extra=[evidence('rng32x64_design_20261015/manifest.json','provenance'),evidence('rng32x64_design_20261015/checks.json','functional')])
    record('conversion-1587-functional','BF16/FP32/定点转换及跨块累加','数制转换','RTL_FUNCTIONAL','functional_only',
        'format_conversion_rtl_20261016/FUNCTIONAL_STATUS_ZH.txt',stages('pass'),
        '18类探针；607047数值/4608接口/181累加帧；Slurm1587 CPU/Icarus。',
        ['模板和活动TB不是工艺PPA；旧累加路径各自契约通过，不是彼此逐位等价。'],
        extra=[evidence('format_conversion_rtl_20261016/results/source_hashes.json','provenance'),evidence('format_conversion_rtl_20261016/results/vector_generation.json','functional')])
    record('digital-107-functional','完整TLM所需非随机数字模块v1','非随机算术/控制','RTL_FUNCTIONAL','functional_only',
        'tmp/tlm-digital-issue107-20261022/architecture_tlm/digital_ppa_v1/README_ZH.md',stages('pass'),
        '66功能组/12870逐位输出/63活动；21KIND＋控制/存储/数组包装；PR109待审。',
        ['没有DC/STA/PT结果；功能一拍不证明10ns。','近似FP32非线性/融合恢复还需模型质量；不套用Q10成本。'],
        extra=[evidence('tmp/tlm-digital-issue107-20261022/architecture_tlm/digital_ppa_v1/results/RTL_VALIDATION.json','functional'),
               evidence('project_archives/tlm_digital_issue107_20261022/RAW_VALIDATION.zip','archive')],
        source=dict(git_commit='23e8d65fbd84cf548ab82a6c9cfe423d37e59ae4',binding='29源文件Git原字节核验'),
        next_action='按PPA_TASK逐配置跑DC/STA/PT，回传后追加新run记录；不要覆盖本功能证据')
    RECORDS[-1]['source']['url']='https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/tree/23e8d65fbd84cf548ab82a6c9cfe423d37e59ae4/architecture_tlm/digital_ppa_v1'
    record('short-stream-22-functional','A8共享64短流/分层采样RTL','FFN短流','RTL_FUNCTIONAL','functional_only',
        'tmp/qwen-short-stream-issue22-20261018/sc_short_stream_20261018/results/VALIDATION_ZH.md',stages('pass'),
        'Issue22/PR25：36配置252帧、7活动窗口；条件能量模型不是新PT。',
        ['不能将T4096旧矩阵PPA不加条件当成短流实际PPA。'],
        next_action='从已合并PR25恢复源码与验证索引后做匹配工艺表征，已有功能无需重复昂贵实验')

    for id,report,desc,stage in [
        ('backend-38125344','tmp/backend-power-estimate-20261018/RESULT_REVIEW_38125344_ZH.txt',
         '共享数字p-bit后端整片标准单元，实际299.401MHz，SDF/SPEF；不是LLM专用核。',stages('partial','completed','reported_review','calculated','artifacts_present')),
        ('backend-38151072','tmp/backend-scale-review-20261019/RESULT_REVIEW_38151072_ZH.txt',
         '32已配置节点PT完成；128节点后仿通过但当时PT证据定位失败；更新归档38165794另列待审。',stages('partial','completed','reported_review','partial','artifacts_present')),
        ('backend-38168593','tmp/backend-functional-review-38168593/v2-package-check/backend_functional_20261019/RESULT_REVIEW_38168593.txt',
         '后端功能：errors通过/crossbank读回时点假设失败；boundaries/recovery当时未跑；后续38215256待核。',stages('partial','not_run','reported_review','not_run','artifacts_present'))]:
        record(id,'共享p-bit后端 '+id.split('-')[1], '共享数字后端（独立项目）','POSTLAYOUT_PROVISIONAL' if 'power' in report or 'scale' in report else 'GATE_FUNCTIONAL',
            'partial_provisional',report,stage,desc,
            ['仅交叉索引已有共享后端，不能把整片功率除少量活跃节点当单节点成本。',
             '有大批未知信号/库表外与PLL模型缺项，后布局原件存在不等于签核完成；不自动回填LLM。'],
            next_action='按新归档重新核对实际完成状态，原作者维护；本次不接管独立芯片项目')

    # Completeness safety net: all downloaded digital archive candidates remain findable,
    # including newer runs that have no reviewed summary yet. Metadata is NOT acceptance.
    patterns=('sc_', 'sram_', 'result_380', '38100634_', '38099357_', '38099581_', 'backend_',
              'chimera_power', 'postlayout', 'pt_power_probe', 'single_node',
              'lfsr_', 'gf64_', 'bivium_', 'ffn_', 'pbit_20x20_', 'pbit_sdf_')
    inventory=[]
    known_jobs=('37962470','37962379','37981139','38015538','38014357','38068649','38068650','38057668','38070775','38071895','38100634','38099357','38099581','38125344','38151072','38168593')
    for p in sorted(APR.glob('*.tar.gz')):
        if not p.name.startswith(patterns):continue
        related=[x['id'] for x in RECORDS if any(a['path']==p.as_posix() for a in x['artifacts'])]
        job=next((j for j in known_jobs if j in p.name),None)
        if not related and job:
            related=[x['id'] for x in RECORDS if job.replace('_','-') in x['id']]
        inventory.append(dict(path=p.as_posix(),bytes=p.stat().st_size,sha256=sha(p),
            linked_records=';'.join(related),review_state='indexed_batch_see_record' if related else 'discovered_not_audited',
            note='只读归档字节SHA已核；未由发现文件自动推断仿真通过'))
    with (OUT/'archive_inventory.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(inventory[0]));w.writeheader();w.writerows(inventory)
    for r in RECORDS:dump(OUT/'records'/(r['id']+'.json'),r)
    dump(OUT/'catalog.json',dict(schema_version=1,as_of='2026-10-22',issue=110,
        scope='LLM数字计算、随机服务、SRAM库/状态；另交叉索引共享p-bit芯片，不接管独立项目',
        base_commit=BASE,record_ids=[r['id'] for r in RECORDS],
        archive_inventory='archive_inventory.csv',archives_discovered=len(inventory),
        note='一条为一个批次/模块，不等于一个实验；cases为该批逐配置/seed/窗口记录。'))
    print(json.dumps(dict(records=len(RECORDS),cases=sum(len(r['cases']) for r in RECORDS),
        artifacts=sum(len(r['artifacts']) for r in RECORDS),missing=[a['path'] for r in RECORDS for a in r['artifacts'] if not a['present_at_registration']],
        archives=len(inventory)),ensure_ascii=False,indent=2))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
