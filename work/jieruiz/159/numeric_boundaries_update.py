"""Record arithmetic bounds and user-confirmed functional/TLM interface rules."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
D=ROOT/'qwen3/training/sc_qat_20261023'
def save(path,data):
    path.write_bytes((json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))

rows=[]
for n in (64,2560):
    for t in (16,32,64):
        for w in (4,6,8):
            m=n*t*(2**(w-1)-1)
            width=m.bit_length()+1
            assert -2**(width-1)<=-m and m<=2**(width-1)-1
            assert m>2**(width-2)-1 # A narrower signed word fails the positive endpoint.
            rows.append(dict(inputs=n,samples=t,weight_bits=w,magnitude_bound=m,signed_bits=width))
save(ROOT/'work/jieruiz/159/ACCUMULATOR_BOUNDS.json',dict(
    scope='unscaled common-unit integer worst-case; not full mixed-scale FFN',
    signed_weight_rule='[-(2**(W-1)-1), +(2**(W-1)-1)]',
    formula='M=N*T*Qmax; signed_bits=1+ceil(log2(M+1))',
    checked_endpoint_and_minimality_cases=len(rows),rows=rows,
    measured_model_quality=False,rtl_or_ppa_run=False))

p=D/'HARDWARE_CONTRACT.example.json'
data=json.loads(p.read_bytes())
data['python_storage_dtype_is_not_hardware_format']=True
data['float_host_simulation_allowed_if_target_semantics_preserved']=True
data['rtl_required_before_functional_macro_estimation']=False
data['undefined_numeric_semantics_may_not_be_idealized']=True
data['algorithm_and_tlm_require_same_contract_sha']=True
data['unknown_cost_is_not_zero']=True
data['fields'].update(macro_numeric_behavior_and_evidence=None,
    macro_input_output_units_and_buffer_bytes=None,macro_cost_source_and_uncertainty=None,
    simulation_container_exactness_check=None)
save(p,data)

note='''> **2026-10-24补充：Python容器与电路数制分开。** 可以用FP32模拟定点运算，但须显式保持目标舍入、饱和、比较及概率响应；宽整数还须检查宿主精度。TLM和功能模拟引用同一数值契约。暂时没有RTL可以用已定义的功能宏及有来源的条件PPA估计，不得以理想转换代替尚未定义的硬件行为。局部累加位宽不等于g/u接口位宽，详见 [NUMERIC_BOUNDARIES_ZH.md](NUMERIC_BOUNDARIES_ZH.md)。

'''
for name in ('REMOTE_AGENT_START_HERE_ZH.md','HARDWARE_FORWARD_AUDIT_ZH.md'):
    p=D/name
    s=p.read_text(encoding='utf-8')
    first,rest=s.split('\n',1)
    p.write_bytes((first+'\n\n'+note+rest).encode('utf-8'))

entry='''## 2026-10-24 用户确认：功能模拟与TLM共用数制契约

Python可用FP32/FP64作为模拟容器，不能把dtype直接当电路格式；必须模拟定点比较、尺度、舍入/溢出、随机相关性与响应。TLM引用同一契约SHA，对每一步有宏/电路映射及时间/资源/存储/能耗依据；暂无RTL允许定义功能宏、用有来源的条件PPA估计，未知不为零，未定义功能不得理想化。W8/N64/T16/32/64局部同尺度精确计数需18/19/20位；输出可另缩放量化A8（另符号）或signed8，质量未验证。完整跨档/tile位宽另计，不宣称8位累加足够。

接续Issue159/PR170，分支task/159-hardware-forward-contract；正式NUMERIC_BOUNDARIES_ZH.md，18组整数上界/最小位宽校核见work/jieruiz/159/ACCUMULATOR_BOUNDS.json。无新PPL/训练/RTL/PPA，未改完整TLM代码。下一步先定功能宏、8/10/12接口对照再联合质量/代价验收；发布状态见同目录NUMERIC_PUBLICATION.json。Projects未同步，历史证据保留。

'''
for rel in ('PROJECT_MEMORY_ZH.md','progress/jieruiz/STATUS.md','work/jieruiz/159/HANDOFF.md'):
    p=ROOT/rel
    p.write_bytes(entry.encode('utf-8')+p.read_bytes())
root=ROOT.parents[1]
c=root/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md'
m=root/'PROJECT_MEMORY_ZH.md'
assert c.read_bytes()==m.read_bytes(), 'Reconcile concurrent memory updates first'
c.write_bytes(entry.encode('utf-8')+c.read_bytes());m.write_bytes(c.read_bytes())
print(json.dumps(dict(bound_cases=len(rows),w8_tile64_bits=[r['signed_bits'] for r in rows if r['inputs']==64 and r['weight_bits']==8])))
