from pathlib import Path
import importlib.util,json,base64,hashlib,subprocess
P=Path(__file__).resolve().parent;R=P.parents[2]
s=importlib.util.spec_from_file_location('g','C:/Users/86134/Documents/a_P_BIT/tmp/tlm-digital-issue107-20261022/work/jieruiz/107/publish.py')
g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
g.ROOT=R;g.BRANCH='task/129-two-page-brief';g.BASE='6966739a5223680888bf0315f7bb4f73423a1ae6'
g.git=lambda *args:subprocess.check_output(['git','-c','core.quotePath=false',*args],cwd=R)
g.allowed=lambda p:p.startswith(('architecture_tlm/memory_savings_20261023/','work/jieruiz/129/')) or p=='progress/jieruiz/STATUS.md'
assert g.api('GET','/user')['login']=='jieruiz'
out=g.publish()
pr=g.api('POST',g.PREFIX+'/pulls',dict(title='两页说明 概率计算的能耗面积节省与速度控制',head=g.BRANCH,base='pbit-tlm-attention-details-20261016',body='关联 #129。补充面向非专业听众的两页 Word，说明计算简化、存储和搬运节省、控制采样时间的办法，以及尚未完成的验证。原详细报告保留。\n\n实际验证：原生 Word 导出恰好两页，packaged render_docx.py 渲染后逐页检查，DOCX ZIP完整性及SHA核验。仅整理已有证据；无新PPL、TLM、RTL或工艺仿真，不恢复暂停任务。'))
out['pr']=pr['html_url'];out['number']=pr['number']
for n in ['概率计算的能耗面积与速度_两页说明.docx','BRIEF_ZH.md']:
    p='architecture_tlm/memory_savings_20261023/'+n
    oid=g.git('rev-parse',out['head']+':'+p).decode().strip()
    raw=base64.b64decode(g.api('GET',g.PREFIX+'/git/blobs/'+oid)['content'])
    assert raw==(R/p).read_bytes()
out['exact_deliverable_bytes']=True
(P/'BRIEF_PUBLICATION.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
msg='两页通俗说明已交付 '+out['pr']+'，Word严格两页并逐页渲染检查，远端DOCX/正文与已验证本地原字节一致。介绍能耗面积节省机制、速度控制和剩余验证，原详细报告保留。无新实验；PR待审未合并；看板沿已核实的read:project权限限制待同步。'
g.api('POST',g.PREFIX+'/issues/129/comments',dict(body=msg))
print(json.dumps(out,ensure_ascii=False))
