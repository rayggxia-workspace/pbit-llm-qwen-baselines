from pathlib import Path
import sys,json,subprocess,time,hashlib
import control
ROOT=control.ROOT;REPO=control.REPO;TREE=ROOT.parents[1]/'workspace_projects/sq157'
session=control.client();base='https://api.github.com/repos/'+REPO+'/'
def get(path):
    response=session.get(base+path,timeout=45);response.raise_for_status();return response.json()
branch='task/157-sparq-qwen3';dependency='task/144-qwen3-stochastic'
assert subprocess.check_output(['git','-C',str(TREE),'branch','--show-current'],text=True).strip()==branch
urls=subprocess.check_output(['git','-C',str(TREE),'remote','get-url','--push','--all','origin'],text=True).splitlines()
assert urls==['https://github.com/'+REPO+'.git'],urls
head=subprocess.check_output(['git','-C',str(TREE),'rev-parse','HEAD'],text=True).strip()
assert not subprocess.check_output(['git','-C',str(TREE),'status','--porcelain'],text=True).strip()
upstream=get('pulls/147');control.save('publication_dependency_147.json',upstream)
assert upstream['head']['sha']=='357db5884726a66d988d75f92447ff8ecf8698e6','dependency changed: review before publish'
issue=get('issues/157');control.save('publication_issue_before.json',issue)
changes=subprocess.check_output(['git','-C',str(TREE),'diff','--name-only','357db588..HEAD'],text=True).splitlines()
allowed=('qwen3/sparq/','architecture_tlm/sparq_baseline/','work/amlink1219/157/')
assert all(p.startswith(allowed) or p in ['AGENTS.md','PROJECT_MEMORY_ZH.md','progress/amlink1219/STATUS.md'] for p in changes)
# Every archived artifact must remain identical in the committed Git blob.
manifest=json.loads((TREE/'work/amlink1219/157/ARTIFACTS.json').read_text())
for path,digest in manifest.items():
    blob=subprocess.check_output(['git','-C',str(TREE),'show','HEAD:work/amlink1219/157/'+path])
    assert hashlib.sha256(blob).hexdigest()==digest,path
# Result bytes must survive Git attributes exactly, including downloaded JSON
# whose internal/envelope SHA has already been independently checked.
result_paths=subprocess.check_output(['git','-C',str(TREE),'ls-files','qwen3/sparq/results'],text=True).splitlines()
for path in result_paths:
    blob=subprocess.check_output(['git','-C',str(TREE),'show','HEAD:'+path])
    assert hashlib.sha256(blob).hexdigest()==hashlib.sha256((TREE/path).read_bytes()).hexdigest(),path
control.save('PUSH_INTENT.json',dict(repository=REPO,branch=branch,head=head,files=changes))
subprocess.run(['git','-C',str(TREE),'-c','credential.username=amlink1219','push','origin',branch],check=True)
ref=get('git/ref/heads/'+branch);assert ref['object']['sha']==head
pulls=get('pulls?state=open&head=rayggxia-workspace:'+branch)
body='''为后训练版 **Qwen/Qwen3-4B** 新建匹配BF16与SparQ基线，替换新入口中的max4/小网络筛选。保留历史实验，复用PR147原生Qwen3 plumbing，原FFN保持完整；不是沿用Qwen3-4B-Base的PPL。

关联#157；本PR以#147的`task/144-qwen3-stochastic@357db588`为依赖，未自动合并。

实现论文v6 GQA probability-sum r32/k_total128/local_total32及固定官方源码oracle，明确官方标签raw-score-sum/k+1差异；全部计分token采用缓存单查询，官方PIQA1838/ARC-Easy2376/HellaSwag10042配对评分，分段哈希恢复。新增双K容量/事务/选择器成本账本及GPU参考速度/板级功率测量。

已验证CPU Slurm2872：TF4.51.3/Torch2.7.1+cu128的45项全部通过、无跳过、CUDA未初始化；后续诊断向量追加1测试、GPU benchmark9项辅助测试本地通过。固定模型10文件和5份数据已由CPU2871校验完成。环境准备两次失败及日志保留。

尚未完成：真实模型GPU门禁正在推进，完整WT2/三任务以及GPU实测结果将在本PR继续追加。硬件账本是条件分析，未运行SparQ RTL/STA，物理面积/功率/能量保持null；不宣称硬件加速。仅原FFN的纯SparQ主基线，本轮未运行SparQ+概率FFN/采样attention组合。

入口`qwen3/sparq/README_ZH.md`；恢复`work/amlink1219/157/HANDOFF.md`。Issue116/123保持暂停。大权重/数据只在本人服务器目录。
'''
if pulls:
    assert len(pulls)==1;pr=pulls[0]
else:
    intent=ROOT/'PR_INTENT.json'
    assert not intent.exists(),'recover existing PR creation before retry'
    payload=dict(title='SparQ基线：后训练Qwen3-4B接合、完整评分与硬件成本',head=branch,base=dependency,body=body,draft=True)
    control.save(intent.name,payload)
    response=session.post(base+'pulls',json=payload,timeout=45);response.raise_for_status();pr=response.json()
control.save('PR_RECEIPT.json',pr)
for retry in range(5):
    current=get('pulls/'+str(pr['number']))
    if current['head']['sha']==head:break
    time.sleep(2)
else:raise RuntimeError('ref correct but PR head projection still delayed')
control.save('PUBLICATION.json',dict(head=head,ref_verified=True,pr=current['html_url'],pr_number=current['number'],
    pr_head_verified=current['head']['sha'],files=changes,state='draft_open_unmerged'))
updated=issue['body'].replace('当前Base与后训练模型名称差异已向用户核对，算法先独立实现。','用户已确认Qwen/Qwen3-4B后训练版，另建匹配BF16基线。')
updated=updated.replace('- [ ] 固定论文/官方代码SHA','- [x] 固定论文/官方代码SHA')
marker='\n\n当前交付PR：'+current['html_url']
if marker not in updated:updated+=marker+'（draft/open/未合并）；CPU45项原生门禁已过，模型/数据已准备；完整质量与GPU实测待后续回执。'
control.save('ISSUE_UPDATE_INTENT.json',dict(number=157,body=updated))
response=session.patch(base+'issues/157',json={'body':updated},timeout=45);response.raise_for_status()
assert get('issues/157')['body']==updated
print(json.dumps(dict(pr=current['html_url'],head=head,files=len(changes),status='uploaded draft, unmerged'),ensure_ascii=False))
