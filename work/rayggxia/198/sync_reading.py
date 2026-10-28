"""Incremental guarded root reading mirror and memo updates, preserving history."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3];WS=ROOT.parents[1];W=Path(__file__).parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode())


def main():
    reg=WS/'digital_circuit_simulation_registry';pre=json.loads((W/'REGISTRY_PREIMAGE.json').read_text())
    assert sha(reg/'catalog.json')==pre['catalog_sha256'], 'concurrent catalog update; re-union first'
    assert {p.name:sha(p) for p in (reg/'records').glob('*.json')}==pre['records'], 'concurrent record update'
    record=ROOT/'digital_circuit_simulation_registry/records/attention-rejection-198-20261027.json'
    assert not (reg/'records'/record.name).exists()
    # Snapshot the old catalog/generated reading files; no existing run changed.
    backup=WS/'project_archives/attention_compare_issue198_20261027/reading_preimages'
    backup.mkdir(exist_ok=False)
    generated=['catalog.json','00_总览.md','01_结果地址索引.md','runs.csv','artifact_locations.csv']
    for name in generated:(backup/name).write_bytes((reg/name).read_bytes())
    (reg/'records'/record.name).write_bytes(record.read_bytes())
    for name in generated:(reg/name).write_bytes((W/'registry_check'/name).read_bytes())
    assert sha(reg/'records'/record.name)==sha(record)
    r=subprocess.run([sys.executable,str(reg/'registry.py'),'check'],capture_output=True,text=True,check=True)
    subprocess.run([sys.executable,str(reg/'registry.py'),'render'],check=True)
    memo_paths=[WS/'PROJECT_MEMORY_ZH.md',WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md']
    prefix=('## 2026-10-27 Issue198：Attention单query首轮代码与功能仿真\n\n'
      '用户提供Attention对照PDF/专门交接后授权实现；rayggxia连接器，main d83eeb1f，task/198-attention-compare，'
      'tmp/attention-compare-issue198-20261027。新Issue198独立于186/95/193，后续仍开放。'
      '六方案D0/P0–P4、分块在线参考、同候选筛选、PR88采样复用、实际V重复计数/burst和有限tile宏调度已实现。'
      'L512/2K/8K、d64/128、三seed共108合成项完成，6机制检查；另72项预算探索，不是模型/PPL/bittrue BF16。\n\n'
      '完整外供bit校正拒绝控制N16/64/512三seed22500拍逐周期oracle全等，含配置/公平位/输出等待、reset、cap和m24饱和。'
      '仅RTL功能，100MHz为TB时钟；与PR88时序尚未绑定，不改unified_v6/PR192 sink或暂停116/123。'
      '单合成2K/d128以完整IID128解析MSE阈值匹配，P3/P4网格观察须S512，条件周期117264/22181，D033586；'
      '拒绝较慢负例保留，三seed均值过线不是置信/真实模型质量验收。能耗面积null；D1/赢家RTL/GQA/真实后训练QKV/STA/PT待后续。\n\n'
      '正式入口architecture_tlm/attention_compare_20261027/README_ZH.md，源/配置/质量/原始轨迹SHA与5.31MB本地399成员归档见work/rayggxia/198；'
      '统一台账新增attention-rejection-198-20261027，79联合记录check/render通过。'
      '发布状态以PUBLICATION.json/远端PR为准，未合并不关闭Issue；无GPU/Slurm/许可EDA。'
      '两记忆副本已有历史差异，分别前置同一新段保留旧字节，不覆盖其他任务更新。\n\n---\n\n').encode('utf-8')
    before=[]
    for i,p in enumerate(memo_paths):
        b=p.read_bytes();(backup/f'memory_{i}.bin').write_bytes(b)
        assert b'Issue198' not in b[:2000], 'already appended'
        p.write_bytes(prefix+b);assert p.read_bytes()[len(prefix):]==b
        before.append(dict(path=str(p),old_sha256=hashlib.sha256(b).hexdigest(),new_sha256=sha(p)))
    write(W/'READING_SYNC.json',dict(registry=json.loads(r.stdout),record_sha256=sha(record),
        all_old_records_preserved=True,memory=before,preimages=str(backup),
        note='root mirror incremental union; canonical memo preexisting differences preserved; no foreign checkout switched or reset'))
    d=json.loads((W/'DELIVERY.json').read_text());d['root_registry_sync']='79 record union verified';write(W/'DELIVERY.json',d)
    print('root registry 79 records and both memory prefixes updated; old bytes preserved')


if __name__=='__main__':main()
