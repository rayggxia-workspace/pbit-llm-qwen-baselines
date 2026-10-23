from publish import api, PREFIX, save

assert api('GET', '/user')['login'] == 'jieruiz'
issue = api('GET', PREFIX + '/issues/158')
assert issue['state'] == 'open'
marker = '执行提交e174d91cfcdb318da6481884bbf17ff37c1e3797'
if marker not in issue['body']:
    body = issue['body'] + '\n\n实际部署：' + marker + '，44源码/本地与提取快照5合同通过、17发布文件远端原字节通过；CPU2869镜像下载（原生CPU覆盖/保存重载已过），GPU2870 afterok2869依赖，最多1GPU。PR160 draft/open未合并，尚无新PPL，不能沿用Base基线。ROOT /home/Hongjie_Zeng/projects/pbit-qwen3-stochastic-nonbase-20261023-issue158。与Issue157分工评论6367526124。未创建新定时检查；恢复先读work/jieruiz/158/HANDOFF.md及实际队列，不重交健康作业。\n'
    issue = api('PATCH', PREFIX + '/issues/158', dict(body=body))
save('ISSUE_SYNC.json', dict(number=158, state=issue['state'], updated_at=issue['updated_at']))
print('ISSUE158_DEPLOYMENT_SYNCED')
