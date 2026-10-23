from pathlib import Path
from pypdf import PdfReader
import hashlib,json,shutil,zipfile
P=Path(__file__).resolve().parent;R=P.parents[2]
O=R/'architecture_tlm/memory_savings_20261023'
name='概率计算的能耗面积与速度_两页说明.docx'
assert len(PdfReader(P/'brief_render/word_export.pdf').pages)==2
with zipfile.ZipFile(O/name) as z:assert z.testzip() is None
v=dict(date='2026-10-23',issue=129,owner='jieruiz',base='6966739a5223680888bf0315f7bb4f73423a1ae6',pages=2,
       qa='Native Word PDF plus packaged render_docx.py rasterizer; both page PNGs visually inspected',
       source='Existing REPORT_ZH.md, SOURCE_INDEX.json, CALCULATIONS.json; PR119/120/122/125/126/127 merged as stage artifacts',
       new_experiments=False,model_data_seed='Not applicable: explanatory document only',files={})
for n in [name,'BRIEF_ZH.md']:
    data=(O/n).read_bytes();v['files'][n]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
(P/'BRIEF_VALIDATION.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
dest=Path('C:/Users/86134/Documents/a_P_BIT/pbit_llm_master_report_20261012/SRAM_DRAM节省总结_20261023');dest.mkdir(exist_ok=True)
shutil.copyfile(O/name,dest/name)
entry='''## 2026-10-23 Issue129 两页通俗说明

按用户要求补充功耗面积节省机制、速度控制与剩余验证，面向非专业听众，省略内部结构细节。正式文件 architecture_tlm/memory_savings_20261023/概率计算的能耗面积与速度_两页说明.docx；两页，Word导出及逐页PNG检查通过。原7页报告保留，无新实验，不恢复暂停任务。分支 task/129-two-page-brief，复用 tmp/memory-savings-issue129-20261023；上传/PR以 BRIEF_PUBLICATION.json 为准，合并前不关闭Issue129。

'''
status=R/'progress/jieruiz/STATUS.md';status.write_bytes(entry.encode()+status.read_bytes())
hand=P/'HANDOFF.md';hand.write_bytes(entry.encode()+hand.read_bytes())
readme=O/'README.md';readme.write_bytes(('新增面向非专业听众的[两页Word说明]('+name+')，讲解能耗、面积、速度与剩余验证；原详细报告保留。\n\n').encode()+readme.read_bytes())
print(json.dumps(v,ensure_ascii=False))
