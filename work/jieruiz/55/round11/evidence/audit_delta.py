from pathlib import Path
import subprocess,json,hashlib,sys
A=Path(__file__).resolve().parent;W=A.parent.parent/'tmp/pr55-review-round11-20261025'
old='008b02276fe80e3f6e0017f43513101a54c06bdd';new='291c437a9df2f4a61d5f694f85220a78466c3ce1'
changed=subprocess.check_output(['git','-C',str(W),'diff','--name-only',old,new]).decode().splitlines()
assert len(changed)==7
assert all(p.endswith(('.md','.json')) or p=='work/jieruiz/186/report_asic_comparison.py' for p in changed)
p=W/'work/jieruiz/186/ASIC_COMPARISON_DERIVATION.json';doc=W/'architecture_tlm/unified_v6/ASIC_PAPER_COMPARISON_ZH.md'
saved={f:f.read_bytes() for f in (p,doc)};expected=json.loads(saved[p]);checked=[]
for x in expected['inputs']:
    assert hashlib.sha256((W/x['path']).read_bytes()).hexdigest()==x['sha256'];checked.append(x['path'])
try:
    r=subprocess.run([sys.executable,'-B',str(W/'work/jieruiz/186/report_asic_comparison.py')],cwd=W,capture_output=True)
    assert r.returncode==0,r.stderr
    actual=json.loads(p.read_bytes());actual.pop('created_utc');expected.pop('created_utc');assert actual==expected
    assert doc.read_bytes()==saved[doc]
finally:
    for f,b in saved.items():f.write_bytes(b)
record={'old_head':old,'reviewed_head':new,'changed_files':changed,'runtime_and_configs_unchanged':True,'inputs_sha256_verified':checked,'derived_values_and_document_reproduced':True,'original_bytes_restored':True,'primary_sources_checked':['https://arxiv.org/html/2405.07518v1','https://mlhardware.github.io/2020/groq.pdf','https://scale.snu.ac.kr/papers/2024-04-Conference-ASPLOS-AttAcc.pdf','https://arxiv.org/html/2403.00579v3','https://arxiv.org/html/2409.05902v3','https://arxiv.org/html/2601.06724v1']}
out=json.dumps(record,ensure_ascii=False,indent=2)+'\n';(A/'DELTA_AUDIT.json').write_text(out,encoding='utf-8');(W/'work/jieruiz/55/round11/evidence/DELTA_AUDIT.json').write_text(out,encoding='utf-8')
p=W/'work/jieruiz/55/round11/REVIEW_ZH.md';s=p.read_text(encoding='utf-8').replace('PR190@'+old,'PR190@'+new).replace('相对先前27763673只有发布交接追加，科学源码未变。','初审008b0227；合并前捕获291c437a追加的文献/已有结果派生分析，7文件增量未改运行源码、配置或原始结果。派生输入SHA、数值和文档重现通过，六项一手来源核对，原字节恢复。').replace('14类源码清单中可识别的','源码清单中可识别的').replace('当前PR190树运行110项','初审008b0227树运行110项');p.write_text(s,encoding='utf-8',newline='\n')
for name in ['premerge.py','MERGE190.json','START55.json']:
    p=A/name;s=p.read_text(encoding='utf-8').replace(old,new).replace('190@008b0227','190@291c437a');p.write_text(s,encoding='utf-8',newline='\n')
print(out)
