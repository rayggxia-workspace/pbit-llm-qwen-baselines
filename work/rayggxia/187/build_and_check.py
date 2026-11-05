"""Render the research matrix and check documentation consistency; no HW/model run."""
from pathlib import Path
import csv
import hashlib
import io
import json
import re
from collections import Counter

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'architecture_tlm/simulator_survey_20261025'
AUX = Path(__file__).resolve().parent

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding='utf-8', newline='\n')

def dump(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

data = json.loads((OUT / 'EVIDENCE.json').read_text(encoding='utf-8'))
records = data['records']
fields = ['id', 'title', 'venue', 'year', 'category', 'target', 'purpose',
          'simulator', 'granularity', 'process', 'frequency', 'power_area',
          'memory', 'workload', 'results', 'validation', 'limitations',
          'source_urls', 'evidence_locator', 'access_status']
assert len(records) == 33
assert len({r['id'] for r in records}) == len(records)
for r in records:
    assert set(r) == set(fields), r['id']
    assert 2010 <= r['year'] <= 2026
    assert all(r[f] for f in fields)
    assert all(u.startswith('https://') for u in r['source_urls'])
    assert not any('\r' in str(r[f]) for f in fields)

# Semantic guards for the most consequential scope errors identified in review.
by_id = {r['id']: r for r in records}
assert '排除DRAM/NoC' in by_id['ONNXIM']['results']
assert '非GPU实测' in by_id['ANDA']['limitations']
assert '65nm' in by_id['KELLE']['process'] and '45nm' in by_id['KELLE']['process']
assert 'RetNet' in by_id['HSA']['workload']
assert '外部控制电脑' in by_id['PCMALBERT']['memory']
assert '10^9' in by_id['ISINGSOT']['results']
assert '2605.01910v2' in by_id['SANTA']['source_urls'][0]
assert '666MHz' in by_id['ATTACC']['frequency'] and '1.3GHz' in by_id['ATTACC']['frequency']

buf = io.StringIO(newline='')
writer = csv.DictWriter(buf, fieldnames=fields, lineterminator='\n')
writer.writeheader()
for r in records:
    writer.writerow({**r, 'source_urls': ' | '.join(r['source_urls'])})
write(OUT / 'EVIDENCE.csv', buf.getvalue())
back = list(csv.DictReader(io.StringIO(buf.getvalue())))
assert len(back) == len(records)
for x, r in zip(back, records):
    assert x['id'] == r['id'] and x['title'] == r['title']
    assert x['source_urls'].split(' | ') == r['source_urls']

def cell(s):
    return str(s).replace('|', '\\|').replace('\n', ' ')

lines = ['# 逐篇论文与模拟器证据', '',
         '核查日期：2026-10-25。共33个代表性条目；ACCELSIM、ASTRASIM为明确标记的工具家族，含多篇版本，不是33篇单独的LLM论文。', '',
         'NR=本次核查范围未明确披露。最终全文未取得、补充材料未核全、仅核公开代码入口分别注明。论文结果是作者报告，本轮未重跑。', '',
         '[综合结论](README_ZH.md) · [需求与验收](REQUIREMENTS_ZH.md) · [CSV](EVIDENCE.csv) · [JSON](EVIDENCE.json)', '',
         '## 导航', '', '| 条目 | 年份/会议 | 硬件/工具类别 | 时序与物理层级 |', '|---|---|---|---|']
for r in records:
    lines.append(f"| [{r['id']}](#{r['id'].lower()}) | {r['year']} / {cell(r['venue'])} | {cell(r['category'])} | {cell(r['granularity'])} |")
labels = {'target':'被模拟硬件', 'purpose':'目的', 'simulator':'工具链', 'granularity':'建模层级',
          'process':'工艺/PVT', 'frequency':'频率/时基', 'power_area':'能量/面积来源',
          'memory':'存储与DRAM', 'workload':'模型/场景', 'results':'代表结果及条件',
          'validation':'验证证据', 'limitations':'局限/不能推导的结论',
          'evidence_locator':'原文定位', 'access_status':'本轮访问核查范围'}
for r in records:
    lines += ['', f"<a id=\"{r['id'].lower()}\"></a>", f"## {r['id']} — {r['title']}", '',
              f"{r['venue']}，{r['year']}。类别：{r['category']}。", '']
    for k, label in labels.items():
        lines.append(f"- **{label}**：{r[k]}")
    lines += ['', '原始来源：' + '；'.join(f"[来源{i+1}]({u})" for i, u in enumerate(r['source_urls'])), '']
write(OUT / 'EVIDENCE.md', '\n'.join(lines))

pdfs = [
 ('FIGNA', 'C:/Users/86134/Downloads/FIGNA_Integer_Unit-Based_Accelerator_Design_for_FP-INT_GEMM_Preserving_Numerical_Accuracy.pdf', '9–12'),
 ('ASCEND', 'C:/Users/86134/Downloads/71_pdf_upload.pdf', '5–6'),
 ('MBA', 'C:/Users/86134/Downloads/509_Camera_Ready_Paper.pdf', '5'),
 ('ISINGSOT', 'C:/Users/86134/OneDrive/文档/FTJ.Attachments/p-bit/ising/Energy-Efficient_Parallel_Ising_SoftMax_Engine_for_Transformer_Attention_Based_on_Asynchronous_SOT-P-Bits.pdf', '1–3'),
]
local = []
for rid, name, pages in pdfs:
    p = Path(name)
    assert p.is_file(), name
    local.append({'record_id': rid, 'path': name, 'bytes': p.stat().st_size,
                  'sha256': sha(p), 'key_pdf_pages': pages,
                  'uploaded': False, 'access': 'user-provided local source, path not portable'})
remote = [{'record_id': r['id'], 'urls': r['source_urls'],
           'locator': r['evidence_locator'], 'access_status': r['access_status']}
          for r in records]
dump(OUT / 'SOURCES.json', {'as_of': data['as_of'], 'local_pdfs': local, 'remote_sources': remote,
                          'note': '远端来源只存URL和核查位置，不伪造原始网页/PDF字节哈希；本地PDF不上传。',
                          'project_refs': {
                              'main': '5273e5d9fdae811a714f1a278fee6e776c5675af',
                              'PR183': '0341b4acde1e0afd7decf4a48b037e6b376343d8',
                              'PR183_state_at_check': 'open, not merged',
                              'scheduling_owner_issue': 186}})

for p in OUT.glob('*.md'):
    t = p.read_text(encoding='utf-8')
    assert '\ufffd' not in t and '\r' not in t
    for target in re.findall(r'\]\(([^)]+)\)', t):
        if target.startswith(('https://', '#')):
            continue
        rel, _, anchor = target.partition('#')
        target_path = p.parent / rel
        assert target_path.is_file(), (p.name, target)
        if anchor:
            assert f'id="{anchor}"' in target_path.read_text(encoding='utf-8'), target
assert abs(80.97 / (6 * 2048) * 1000 - 6.589) < .001
artifacts = [{ 'path': str(p.relative_to(ROOT)).replace('\\','/'),
               'bytes': p.stat().st_size, 'sha256': sha(p)}
             for p in sorted(OUT.iterdir()) if p.is_file()]
result = {'date': '2026-10-25', 'kind': 'documentation_consistency_only',
          'records': len(records), 'unique_source_urls': len({u for r in records for u in r['source_urls']}),
          'category_counts': dict(Counter(r['category'] for r in records)),
          'checks': ['required fields and IDs', 'JSON/CSV round trip', 'primary URL syntax',
                     'review scope guards', 'Markdown local links/anchors', 'UTF-8 LF',
                     '4 local PDF SHA-256', 'SANTA batch metric arithmetic'],
          'not_run': ['model/PPL/training', 'TLM hardware simulation', 'RTL/EDA/PPA', 'paper reproduction'],
          'artifacts': artifacts, 'status': 'passed'}
dump(AUX / 'VALIDATION.json', result)
print(json.dumps({k: result[k] for k in ['status','records','unique_source_urls','kind']}, ensure_ascii=False))
