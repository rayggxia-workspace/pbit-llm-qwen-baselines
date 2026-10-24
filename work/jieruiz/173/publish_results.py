import base64,json,concurrent.futures
from github import api,push,save,PREFIX,ROOT,git
assert api('GET','/user')['login']=='jieruiz'
pr=api('GET',PREFIX+'/pulls/174')
assert pr['head']['ref']=='task/173-and-direct-wd' and pr['base']['ref']=='task/171-nonlinear-width'
assert pr['state']=='open' and not pr['merged']
receipt=push();head=receipt['head']
paths=git('diff','--name-only','38de07962a05f39391a778f7b81e2ed389546bf9',head).decode().splitlines()
def verify(p):
    obj=api('GET',PREFIX+'/contents/'+p+'?ref='+head)
    assert base64.b64decode(obj['content'])==git('show',head+':'+p),p
    return p
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:verified=list(pool.map(verify,paths))
body='''非线性三条独立八位比较流经AND后直接驱动固定W8，不再统计z并重新编码。Wd输出端采用整数累加、16位固定恢复系数与整数RNE BF16。gate/up恢复仍FP32参考，不能称全链bit-true。

关联 #173，依赖 #172。Slurm2881五片封存齐全，27份计分（23唯一配置）原字节SHA和36层全前缀覆盖通过；每片12项功能检查包括CUDA整数归约。无训练/RTL/PPA。8段×128目标后缀PPL，不是完整WT2。

| 配置 | 三seed PPL均值 |
|---|---:|
| 同轮BF16（五次一致） | 13.566049 |
| 旧8位均值z再编码 | 13.428421 |
| 直连条件均值、有限尺度系数 | 13.498204 |
| AND64 | 8949057.25 |
| AND256 | 7735.00 |
| AND1024 | 30.6930 |
| AND4096 | 14.9373 |

首层平均事件概率0.000910389，64拍零事件比例95.02%。结果证明当前尺度下短流直连不合格，不能继承上一版条件均值的质量结论。误差随T增加收敛，主要瓶颈指向三流乘积的稀少事件；后续应先改尺度/编码，再确定训练前向。

报告：qwen3/results/and_direct_20261024/REPORT_ZH.md；SUMMARY/RAW_INDEX含每seed、格式契约、执行及输入SHA。Slurm accounting未启用，完成依据为五份status=completed封存JSON及正常日志，未伪造sacct记录。Projects未同步，不自动合并。
'''
api('PATCH',PREFIX+'/pulls/174',dict(body=body,title='Qwen3-4B：八位AND直连Wd仿真，短流稀少事件导致精度退化'))
if pr['draft']:
    api('POST','/graphql',dict(query='mutation($id:ID!){markPullRequestReadyForReview(input:{pullRequestId:$id}){pullRequest{isDraft}}}',variables={'id':pr['node_id']}))
api('POST',PREFIX+'/issues/173/comments',dict(body='仿真核验完成并发布PR174：同轮BF16 13.566，直连有限系数均值13.498，三seed AND64/256/1024/4096为8.949e6/7735/30.693/14.937。27份计分、23唯一配置、36层全前缀和SHA通过；12项服务器预检均通过。8×128目标后缀，不是完整WT2，无训练/PPA。当前短流直连不合格，首层事件概率仅0.000910389。结果提交 '+head+'；保持Issue开放待审，Projects未同步。'))
receipt.update(pr=174,issue=173,verified_blob_count=len(verified),merged=False,ready=True,
    results_verified=True,projects_synced=False)
save('FINAL_PUBLICATION.json',receipt)
print(json.dumps(receipt))
