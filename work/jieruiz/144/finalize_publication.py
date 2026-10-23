"""Update only Issue144/PR147 after exact-byte result publication verification."""
import json
from publish import api, git, save, PREFIX, OUT

assert api('GET', '/user')['login'] == 'jieruiz'
head = git('rev-parse', 'HEAD').decode().strip()
verified = json.loads((OUT / 'REMOTE_VERIFY.json').read_bytes())
assert verified['head'] == head and verified['status'] == 'PASS'
pr = api('GET', PREFIX + '/pulls/147')
assert pr['state'] == 'open' and not pr['merged']
assert pr['head']['sha'] == head and pr['head']['ref'] == 'task/144-qwen3-stochastic'
assert pr['base']['ref'] == 'task/136-qwen3-bf16'
body = '''关联 #144；依赖PR137/base task/136-qwen3-bf16。全部26项4096目标后缀先导已完成并独立验证，不是完整WT2候选。

|方案（三seed均值±样本std）|1.7B PPL|相对matched BF16|4B PPL|相对matched BF16|
|---|---:|---:|---:|---:|
|BF16一次|7.590088|—|6.331575|—|
|FFN-only|7.666993±0.008650|+1.0132%|6.365253±0.002990|+0.5319%|
|screen-exact+FFN|8.067234±0.030143|+6.2864%|6.676899±0.014846|+5.4540%|
|rejection128+FFN|8.249476±0.027266|+8.6875%|6.810810±0.021287|+7.5690%|
|winner1024+FFN|8.091915±0.010626|+6.6116%|6.700177±0.012948|+5.8217%|

执行8c35145冻结；Slurm2828/2829均PILOT_COMPLETE。W8/64x64、B4/T32/K32共享64 A8；max4/64-token/8块/首末2强制；TRAIN16+16独立校准，temp1；拒绝128接受、赢家1024相关更新，argmax/burn0/spacing1。legacy args burn16/spacing4未消费，实际参数见sampling_stats。FFN prefill/decode全层，Attention仅所有计分decode，prefill原生SDPA；Qwen3 QK-Norm/RoPE/GQA保留。软件FP32 Philox不是物理RNG；两采样预算不等成本。

成果qwen3/results/stochastic_20261023/REPORT_ZH.md、SUMMARY.json、checkpoints/complete；78小原件包SHA a3d0df3f043d4a1fee23f9da547d585bcde0f28e9c325d665880fdd5c1a2ace3。37 sidecar/77清单文件/27执行源blob、26病例模型/原文/token/config/校准SHA、全目标全层覆盖及NLL/PPL重算通过，17篡改负例通过，提交blob原字节和远端逐blob读回通过。

验证：python qwen3/stochastic/validate_results.py qwen3/results/stochastic_20261023/checkpoints/complete --require-complete --git-blobs；python -m qwen3.stochastic.test_result_validation qwen3/results/stochastic_20261023/checkpoints/complete --complete；python -m qwen3.stochastic.summarize_final。CPU/GPU tiny、真实模型wrapper bitwise及未修改完整BF16锚点NLL复现门槛也通过。

完整WT2全部26项预算约156 GPU小时，若两卡固定分模型约3.7天，±30%规划余量2.6–4.8天，不含排队/校准；不是实测或置信区间。未启动全量，不上传权重、不合并、不关闭Issue。无新RTL/PPA/真实随机源验证。Projects缺read:project待有权限成员同步。全部结果发布后删除本对话定时检查；实际回执work/jieruiz/144/FINAL_PUBLICATION.json。
'''
result = api('PATCH', PREFIX + '/pulls/147', dict(body=body))
issue = api('GET', PREFIX + '/issues/144')
assert issue['state'] == 'open'
updated_body = issue['body'].replace('- [ ] 两模型后缀', '- [x] 两模型后缀').replace(
    '- [ ] 小型原字节', '- [x] 小型原字节').replace('- [ ] 任务分支/PR', '- [x] 任务分支/PR')
updated_body += '\n\n2026-10-23最终26/26验证完成，三seed结果/完整WT2预算/限制见PR147最终表和REPORT_ZH；科学结果提交' + head + '。保持Issue open待审，不自动启动全量。\n'
issue_result = api('PATCH', PREFIX + '/issues/144', dict(body=updated_body))
if pr['draft']:
    ready = api('POST', '/graphql', dict(query='mutation($id:ID!){markPullRequestReadyForReview(input:{pullRequestId:$id}){pullRequest{isDraft}}}', variables=dict(id=pr['node_id'])))
    assert not ready.get('errors'), ready
    assert ready['data']['markPullRequestReadyForReview']['pullRequest']['isDraft'] is False
final = api('GET', PREFIX + '/pulls/147')
assert final['state'] == 'open' and not final['draft'] and not final['merged']
assert final['head']['sha'] == head
save('FINAL_PUBLICATION.json', dict(status='RESULTS_PUBLISHED_PR_READY_UNMERGED',
    scientific_head=head, verified_github_files=len(verified['verified']),
    committed_server_files_verified=77, negative_guards=17,
    pr=final['html_url'], pr_state=final['state'], draft=final['draft'], merged=final['merged'],
    issue_state=issue_result['state'], issue_updated_at=issue_result['updated_at'],
    automation='qwen3 deletion pending immediately after this receipt',
    full_candidate_submitted=False, project_board='permission pending read:project'))
print(json.dumps(dict(head=head, pr_ready=True, issue_open=True)))
