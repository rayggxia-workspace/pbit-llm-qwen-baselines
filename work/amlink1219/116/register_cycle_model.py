"""Register evidence indices; no experiment execution or PPA inference."""
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parents[3]
def read(path):return json.loads((root/path).read_text(encoding='utf-8'))
base='architecture_tlm/cycle_v1/results/'
matrix=read(base+'matrix_20261023/SUMMARY.json')
smoke=read(base+'matrix_20261023/SMOKE_SUMMARY.json')
sensitivity=read(base+'ffn_sensitivity_20261022/summary.json')
execution=read(base+'matrix_20261023/EXECUTION.json')
names=[base+'matrix_20261023/SUMMARY.json',base+'matrix_20261023/ARCHIVE_INDEX.json',
       base+'matrix_20261023/REAL_ARTIFACT_MANIFEST.json',base+'matrix_20261023/CASE_SUMMARIES.json.gz',
       base+'ffn_sensitivity_20261022/summary.json',
       'architecture_tlm/cycle_v1/audit/results/matrix_v5_offline_review_final.json']
artifacts=[]
for name in names:
    p=root/name;data=p.read_bytes()
    artifacts.append(dict(path=p.as_posix(),repository_path=name,role='summary',required=True,
        present_at_registration=True,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data)))
cases=[]
for suite,label in ((matrix,'real'),(smoke,'smoke')):
    for case in suite['cases']:
        cases.append(dict(case_id=label+'/'+case['name'],operator=case['operator'],latency_ns=case['latency_ns'],
            functional='pass',cycle_event_equal=case['mode_equivalence']['equal'],
            config=case['config'],area_um2=None,power_uW=None,energy_pJ=None,
            evidence='executed configured model; not RTL/STA/PPL'))
for case in sensitivity['cases']:
    cases.append(dict(case_id='sensitivity/'+case['case'],latency_ns=case['latency_ns'],functional='pass',
        cycle_event_equal=True,varied_parameter=case['varied_parameter'],varied_value=case['varied_value'],
        area_um2=None,power_uW=None,energy_pJ=None,evidence='one synthetic fixture and one seed'))
record=dict(schema_version=1,id='cycle-116-conditional-model',name='周期FFN与Attention条件执行及敏感性',
    family='周期执行条件模型',registered_on='2026-10-23',owner='amlink1219',issue=116,
    evidence_level='DESIGN_PROOF',status='conditional_model_verified',
    stages=dict(functional='pass',synthesis='not_run',sta='not_run',power='not_run',postlayout='not_run'),
    boundary='68真实裁剪FFN/query、8smoke、8单变量敏感性；有限资源实际字节执行与cycle/event回归，不是完整模型或物理PPA。',
    conditions=dict(core_period_ps=10000,memory_period_ps=12500,random_backend='native',
                    memory_backend='banked finite descriptor assumption; not DRAMSys/Ramulator',
                    physical_area=None,physical_power=None),
    limitations=['真实FFN为896→70→16裁剪片段；query从预投影QKV与显式候选开始。',
                 '参数latency/II未由完整数据通路STA标定，数组驻留宽供数仍是接口假设。',
                 '302制品独立验收；34完整trace逐项复验，42无trace仅回执级验收；不冒称76例全数学独立证明。',
                 '全模型、全局容量/共享随机网络和同质量同资源PPA尚未闭合；时间列不可直接当旧v6的speedup。'],
    source=dict(git_commit=execution['source']['commit'],
                binding='matrix EXECUTION.files exact source bytes; sensitivity summary.source independent frozen execution',
                source_manifest_sha256=hashlib.sha256((root/(base+'matrix_20261023/EXECUTION.json')).read_bytes()).hexdigest()),
    artifacts=artifacts,cases=cases,
    next_action='先闭合真实单层/GQA/全局资源与在线内存接口，再运行完整模型；匹配RTL/STA后回填动作价格。')
out=root/'work/amlink1219/116/conditional_model_record.json'
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'output':str(out),'cases':len(cases),'artifacts':len(artifacts)}))
