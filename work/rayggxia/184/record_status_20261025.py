"""Append a local timestamped status receipt; do not modify running job or source."""
import hashlib,json
from pathlib import Path
TASK=Path(__file__).resolve().parents[3]
ROOT=TASK.parents[1]
WORK=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
obs=load(WORK/'OBSERVATION_38387635_4.json');progress=load(WORK/'PROGRESS_38387635_5.json')
note=('2026-10-25 07:24:42Z只读复查：38387635仍RUNNING，8CPU，已运行3:33:05；28物理检查、9短精度、18校准案例共55条已结束，'
      '保留原SVT20u OP失败。预设SHORT_SCREEN_PASS，独立校准参考已冻结0.604745V（SHA c9d2358bf5f400c9d4c40059d29a6210ce47bde61e7c60fb6b0dd2a3d3c8c8fe），'
      '验证64007/64013/64033正在并行，已保存到19.7283/19.6519/19.7186ms，总22ms，物理时间进度89.3%～89.7%。'
      '按实际运行速度外推剩余约11分钟加收集打包，非保证；最终每seed20000次统计尚未完成，不能用校准/部分波形代替。'
      '未改快照、未取消或重交。此次本地状态原件OBSERVATION_38387635_4.json、PROGRESS_38387635_5.json保留，最终结果归同PR185追加。')
for base in (TASK,ROOT):
    path=base/'digital_circuit_simulation_registry/records/physical-rng-normal-38387635.json';r=load(path)
    r['conditions'].update(observed_utc=progress['observed_utc'],observed_slurm_state='RUNNING',frozen_reference_V=.604745,numerical_screen_status='SHORT_SCREEN_PASS',validation_progress=progress['cases'])
    r['stages']['functional']='running_heldout_validation_short_screen_and_calibration_complete'
    r['cases']=[dict(case=x['case'],status=x['status'],elapsed_s=x['elapsed_s'],check_error=x.get('error'),complete=True,**({'noise':x['noise']} if 'noise' in x else {})) for x in obs['cases']]
    for name in ('OBSERVATION_38387635_4.json','PROGRESS_38387635_5.json'):
        p=WORK/name
        assert not any(a.get('repository_path')=='work/rayggxia/184/'+name for a in r['artifacts'])
        r['artifacts'].append(dict(path=str(p),repository_path='work/rayggxia/184/'+name,role='running_heldout_progress',present_at_registration=True,required=True,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    r['limitations'][0]='RUNNING. Preset short numerical screen passed and independent reference frozen; all three heldout22ms records still in progress at last observation. No final20000sample acceptance or entropy certification.'
    save(path,r)
canonical=ROOT/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';mirror=ROOT/'PROJECT_MEMORY_ZH.md'
assert canonical.read_bytes()==mirror.read_bytes()
for p in (canonical,TASK/'PROJECT_MEMORY_ZH.md'):
    text=p.read_text(encoding='utf-8');mark='## 6 随机源、p-bit与相关性\n';assert mark in text and note not in text
    p.write_text(text.replace(mark,mark+'\n'+note+'\n',1),encoding='utf-8',newline='\n')
mirror.write_bytes(canonical.read_bytes())
for p in (WORK/'HANDOFF.md',TASK/'progress/rayggxia/STATUS.md'):
    with p.open('a',encoding='utf-8',newline='\n') as f:f.write('\n'+note+'\n')
path=ROOT/'analog_pbit_20261016/normal_readout_v1_delivery.json';d=load(path)
d.update(observed_utc=progress['observed_utc'],status_at_observation='RUNNING',frozen_reference_V=.604745,validation_progress=progress['cases'],actual_20k_new_comparator_results_complete=False)
save(path,d)
print('Local status receipts and central registry updated; running snapshot unchanged.')
