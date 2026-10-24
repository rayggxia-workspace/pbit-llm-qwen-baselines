import json
from pathlib import Path
from github import api,push,save,PREFIX,BRANCH
assert api('GET','/user')['login']=='jieruiz'
latest=api('GET',PREFIX+'/pulls/172')
assert latest['head']['sha']=='38de07962a05f39391a778f7b81e2ed389546bf9'
issue=api('GET',PREFIX+'/issues/173')
assert issue['state']=='open'
receipt=push()
prs=api('GET',PREFIX+'/pulls?state=open&head=rayggxia-workspace:'+BRANCH)
body='''实现八位g/u幅度与sigmoid概率三条独立随机流AND，直接驱动固定W8，仅在Wd输出端进行带符号定点累加；删除中间z统计/再编码。加入16位定点恢复系数、signed52输出累加与整数RNE BF16，避免把Wd恢复当成无限精度免费运算。gate/up恢复仍是FP32参考边界。

关联 #173，依赖 #172；不代表整个FFN已bit-true或PPA已测。本地9项功能通过、CUDA检查待服务器，本机runner缺transformers，服务器必须通过完整12项预检。Slurm2881五分片已提交，执行098c7a00；36层后训练Qwen3-4B、8×128目标后缀PPL、T64/256/1024/4096各三seed，另同轮BF16及均值/旧重编码对照。当前尚无本次PPL结果；结果将原SHA封存核验后补入。
'''
pr=prs[0] if prs else api('POST',PREFIX+'/pulls',dict(title='Qwen3-4B：八位AND随机流直连Wd与输出整数累加',head=BRANCH,base='task/171-nonlinear-width',body=body,draft=True))
receipt.update(pr=pr['html_url'],number=pr['number'],issue=173,merged=False)
save('PUBLICATION.json',receipt)
api('POST',PREFIX+'/issues/173/comments',dict(body='冻结执行098c7a00，Slurm2881五分片已提交；尚无PPL结果。实现及契约见 '+pr['html_url']+'。本地9项功能通过，GPU整数检查和runner将在分片启动时验证。完整三seed及封存SHA核验后更新同PR，不重复提交。Projects看板未同步。'))
print(json.dumps(receipt))
