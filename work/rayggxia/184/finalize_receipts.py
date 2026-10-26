"""Record verified publication and timestamped partial results without changing frozen source."""
import hashlib,json
from pathlib import Path
TASK=Path(__file__).resolve().parents[3]
ROOT=TASK.parents[1]
WORK=TASK/'work/rayggxia/184'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
pub=read(WORK/'PUBLICATION.json')
pub['equivalent_local_delivery_commit']='f7e6110bfae671b09e75d6dca7d020fbff3d85bb'
save(WORK/'PUBLICATION.json',pub)
obs=read(WORK/'OBSERVATION_38387635_3.json')
noise=next(r for r in obs['cases'] if r['case']=='precision_fine_seed63003')
for base in (TASK,ROOT):
    path=base/'digital_circuit_simulation_registry/records/physical-rng-normal-38387635.json'
    r=read(path)
    r['conditions']['observed_utc']=obs['observed_utc']
    r['conditions']['first_short_noise']=noise
    r['source']['publication']='PR185 draft/open; published 97ec6f12df651fc11cfa497521fe0b465cf7823a has identical full tree to local f7e6110bfae671b09e75d6dca7d020fbff3d85bb; source bytes unchanged from executed 01d63b66.'
    r['cases'].append(dict(case=noise['case'],status=noise['status'],elapsed_s=noise['elapsed_s'],check_error=None,complete=True,noise=noise['noise']))
    p=WORK/'OBSERVATION_38387635_3.json'
    r['artifacts'].append(dict(path=str(p),role='running_first_short_noise_observation',present_at_registration=True,required=True,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),repository_path='work/rayggxia/184/OBSERVATION_38387635_3.json'))
    r['limitations'][0]='RUNNING at 2026-10-25T04:06:57.334941Z. One short precision case completed: 2000 actual 1us samples, not heldout20000. Independent calibration and complete numerical acceptance pending.'
    save(path,r)
note=('2026-10-25发布回执：Issue184/PR185已实际发布为draft/open，未合并；科学提交97ec6f12df651fc11cfa497521fe0b465cf7823a，'
      '完整tree9600d63c40808cc2236dd1a06def8fc3686ffc10与本地f7e6110bfae671b09e75d6dca7d020fbff3d85bb一致，5份关键源文件远端逐字符读回一致。'
      '实际执行源仍01d63b66，提交后快照未改。04:06:57Z观察38387635仍RUNNING，29案例已结束；首条precision_fine_seed63003为3ms总/2ms有效，'
      '实际1us采样2000次，密集输出P1=0.5109、MID=0.0068，耗时877.6s；尚无新比较器独立校准冻结或每seed2万次最终验收，不能把该短记录当正式结果。'
      '旧3seed各2万次逐位文件已在ideal_and_old_20000_v1。Projects工具未暴露，待维护者同步。Issue152接口已留言，原负责人/分支/STATUS未改。')
canonical=ROOT/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md'
mirror=ROOT/'PROJECT_MEMORY_ZH.md'
assert canonical.read_bytes()==mirror.read_bytes()
for p in (canonical,TASK/'PROJECT_MEMORY_ZH.md'):
    t=p.read_text(encoding='utf-8');mark='## 6 随机源、p-bit与相关性\n';assert mark in t and note not in t
    p.write_text(t.replace(mark,mark+'\n'+note+'\n',1),encoding='utf-8',newline='\n')
mirror.write_bytes(canonical.read_bytes())
for p in (TASK/'progress/rayggxia/STATUS.md',WORK/'HANDOFF.md'):
    with p.open('a',encoding='utf-8',newline='\n') as f:f.write('\n'+note+'\n')
delivery=ROOT/'analog_pbit_20261016/normal_readout_v1_delivery.json'
d=read(delivery);d.update(publication=pub['pr'],published_scientific_commit=pub['published_scientific_commit'],observed_utc=obs['observed_utc'],first_short_noise=noise)
save(delivery,d)
plan=read(WORK/'PUBLICATION_PLAN.json')
cache=Path(plan['cache_path']).resolve()
expected=(ROOT/'tmp/normal-readout-publish-cache-184-20261025/payload.json').resolve()
assert cache==expected and cache.parent.parent==ROOT/'tmp'
if cache.exists():
    assert cache.stat().st_size==plan['payload_bytes']
    plan['transport_cache_sha256']=hashlib.sha256(cache.read_bytes()).hexdigest()
    cache.unlink()
    cache.parent.rmdir()
plan['transport_cache_removed']=True
plan['recovery']='Regenerate exact transport payload from Git f7e6110bfae671b09e75d6dca7d020fbff3d85bb and publication_payload.py; no unique source/data deleted.'
save(WORK/'PUBLICATION_PLAN.json',plan)
print('Publication, partial observation and registry updated; duplicate API transport cache removed.')
