"""Preserve sealed raw bytes outside Git and write the concise human report."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'qwen/results/static_multiscale_20261023'
SHA = '49bc6bd1356413585c99dad6513d25cc34cff090'
RAW = OUT/SHA
ARCHIVES = Path('C:/Users/86134/Documents/a_P_BIT/project_archives/fixed_multiscale_20261023')
REMOTE = '/home/Hongjie_Zeng/projects/pbit-qwen-static-multiscale-20261023-issue150'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    with path.open('w', encoding='utf-8', newline='\n') as f:
        f.write(value)

s = json.loads((OUT/'SUMMARY.json').read_text(encoding='utf-8'))
assert s['status'] == 'complete' and s['full_test']['completed'] == 21
assert not s['invalid'] and not s['missing']
ARCHIVES.mkdir(parents=True, exist_ok=True)
archive = ARCHIVES/('SEALED_RESULTS_'+SHA+'.tar.gz')
assert not archive.exists(), 'Never overwrite an existing raw archive'
files = {str(p.relative_to(RAW)).replace('\\','/'): dict(bytes=p.stat().st_size, sha256=sha(p))
         for p in sorted(RAW.rglob('*')) if p.is_file()}
with tarfile.open(archive, 'w:gz') as tar:
    for rel in files:
        tar.add(RAW/rel, arcname=rel, recursive=False)
with tarfile.open(archive, 'r:gz') as tar:
    assert len(tar.getmembers()) == len(files)
    for rel, item in files.items():
        payload = tar.extractfile(rel).read()
        assert len(payload) == item['bytes'] and hashlib.sha256(payload).hexdigest() == item['sha256']
for name in ('SELECTED.json', 'SELECTED.sha256.json'):
    shutil.copyfile(RAW/name, OUT/name)
index = dict(execution_commit=SHA, remote_output=REMOTE+'/outputs/'+SHA,
             local_archive=str(archive), archive_bytes=archive.stat().st_size,
             archive_sha256=sha(archive), raw_files=files,
             collector_sha256=sha(ROOT/'experiments/qwen_static_multiscale_20261023/collect_static.py'),
             access='Personal lab-server-ai SSH, or local archive. No public large artifacts required.',
             recovery='Extract archive into a new directory, then run collect_static.py --input DIR --output ANOTHER_DIR')
write(OUT/'RAW_INDEX.json', json.dumps(index, ensure_ascii=False, indent=2)+'\n')

groups = {(r['mode'],r['scope'],r['cycles']): r for r in s['groups']}
def g(scope,cycles=32): return groups[('sampled',scope,cycles)]
rows = [('| 原BF16 | 不采样 | %.6f | 基线 |' % s['baseline']['perplexity'])]
labels = [('w8_only','both',32,'仅W8，连续输入'), ('mean','both',32,'固定四档，无采样编码对照'),
          ('sampled','dynamic',32,'动态四档'), ('sampled','both',32,'全部固定四档'),
          ('sampled','x',32,'仅入口x固定'), ('sampled','z',32,'仅中间z固定'),
          ('sampled','dynamic',64,'动态四档'), ('sampled','both',64,'全部固定四档')]
for mode,scope,t,label in labels:
    r=groups[(mode,scope,t)]
    rows.append('| %s | %s | %.6f | +%.3f%% |' % (label, str(t) if mode=='sampled' else '不采样',
                r['perplexity_mean'],r['relative_ppl_percent']))
report = '''# 固定多档尺度：完整WT2结果与建议

本轮已完成原BF16和20项替换评测。Qwen2.5-0.5B的24层FFN全部参与；attention保留原始准确实现。采样配置均为三个独立seed的平均，固定INT8权重、A8概率、64路共享与分层采样保持不变。完整WT2计分299077个目标，窗口2048、步长1024。

## 选择了哪几档

训练文本上比较档间比2、4、8倍，各加0或1位顶档余量，共六种。另设独立TRAIN留出段。最低选择集平均NLL选中 **S、S/4、S/16、S/64**，不额外加一倍顶档余量。

S是每层、x/z各自每64通道组的固定二次幂，不是全模型共用一个S。例：S=8时为8、2、0.5、0.125；S=16时为16、4、1、0.25。实际最高档x为4～512，z为4～2048，多数组在8～32。尺度在测试前冻结；推理中只按输入大小选档，**不再计算组最大值，也不随token扩档**；超范围则截断。

## 效果

| 方法 | 采样次数 | 完整PPL，越低越好 | 相对BF16 |
|---|---:|---:|---:|
'''+ '\n'.join(rows) + '''

固定编码但不采样的对照接近W8连续输入，说明这套离线范围本身的整体损失较小。固定32次比动态32次差一些，主要来自z侧；只固定入口x最接近动态参考。增加到64次能降低有限采样误差，但不能因此把所有误差都归为方差：SiLU、传播误差、量化和少量截断仍有相互作用。

## 对硬件的意义

去掉的是逐组在线最大值归约和动态顶档生成；仍需要选档、符号/概率转换、档标签与尺度恢复。所有尺度是二次幂，可通过指数调整或移位处理。2160个组各保留一个顶档指数，按8bit指数仅约2.11KiB；四档间隔全局固定。这不包括运行时计数、档标签和控制状态，也不是已测面积。

建议把全固定64次作为去掉在线最大值的质量参考，把全固定32次作为低成本对照。若特别重视32次精度，则目前证据支持先固定x，z继续动态；这不是完全去除动态归约的方案。后续改进应重点研究z低幅值的固定档位覆盖，而不是直接给全模型再加更大的尺度。

目前只验证数值质量。它使用随机分层，不能写成未经组织的物理IID随机流；attention联合替换、跨语料泛化、实际RTL功耗/面积和周期收益尚未在本实验验证。

## 复现与证据

Issue150 / PR153；执行源49bc6bd1356413585c99dad6513d25cc34cff090。CPU2840、prepare2841、数组2842。模型/训练/测试原文、分词序列、执行源码、配置、尺度和原始JSON字节均有SHA；每层全部forward元素覆盖通过。较大的原件只保留服务器和本机归档，路径及SHA见RAW_INDEX.json；SELECTED.json保留实际固定档表。SUMMARY_ZH.md和SUMMARY.json含六候选、三seed标准差、截断及逐层诊断，不隐藏负面结果。没有更改任何已提交执行快照。
'''
write(OUT/'REPORT_ZH.md', report)
print(json.dumps(dict(raw_files=len(files), raw_bytes=sum(v['bytes'] for v in files.values()),
                     archive_bytes=archive.stat().st_size, archive_sha256=sha(archive))))
