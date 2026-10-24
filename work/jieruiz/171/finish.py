import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];D=ROOT/'work/jieruiz/171'
note='''## Issue171非线性位宽初筛完成（2026-10-24）

Slurm2880已结束，执行71cb58d0；28/28封存documents/sidecar SHA、36层全前缀覆盖通过。后训练Qwen3-4B，16×128=2048目标后缀，不是完整WT2。BF16 12.791943，W8原非线性12.584887；g/u幅度6/7/8/10/12分别13.041899/12.607359/12.607722/12.581222/12.577710；组合8/8/8为12.662423(+0.616%)，8/10/8为12.602765(+0.142%)。固定四档T64矩阵三seed：原非线性12.599698±0.016841，8/8/8为12.673273±0.066138(+0.584%)，10/10/10为12.586853±0.026572(-0.102%)。幅度位不含符号，驱动含符号，概率另true-one；TRAIN固定PoT尺度2..256，非线性只有条件均值，无有限AND采样。矩阵恢复仍FP32参考，不是整链bittrue/PPA或训练。

负责人jieruiz/task/171-nonlinear-width，PR172依赖PR169，待审未合并。报告qwen3/results/nonlinear_width_20261024/REPORT_ZH.md；原件project_archives/qwen3_nonlinear_width_20261024/sealed-2880.tar.gz，SHA5ea60da95c0d186f5ac1b20b68ff4348fb04107fb411340a93762cda2b889ac4，成员索引RAW_INDEX。无运行任务/定时，不重交；候选8位幅度+符号/驱动8/概率8，10位留余量，下一步有限AND噪声与全链有限恢复仍待验证。远端发布以FINAL_PUBLICATION.json为准，Projects未同步。

'''
body='''关联Issue #171，依赖PR #169。后训练Qwen3-4B全部36层FFN的非线性位宽初筛完成28/28项：TRAIN固定g/u PoT尺度，单因素区分幅度、sigmoid驱动与概率位宽，再与固定四档T64随机矩阵组合。

16×128目标后缀PPL：W8参考12.584887；g/u幅度6位13.041899、8位12.607722；组合8/8/8为12.662423(+0.616%)。T64矩阵三seed下，原非线性12.599698±0.016841，8/8/8为12.673273±0.066138(+0.584%)，10/10/10为12.586853±0.026572。8位幅度另有符号；概率另true-one，不能称全接口总共8位。

验证：本地4项格式/模块测试，服务器6项格式与计分预检；28封存JSON、所有documents/sidecar SHA、36层/前缀覆盖、NLL重算、相同目标位置通过；原件按SHA归档。执行71cb58d0不可变，Slurm2880已结束。

限制：非线性为有限码/LUT的条件均值，无有限三流AND噪声；矩阵恢复仍FP32参考，非整链bittrue；不是完整WT2、训练或PPA。结果仅支持位宽候选，不证明实际短流精度。正式报告qwen3/results/nonlinear_width_20261024/REPORT_ZH.md；摘要和原件索引同目录。Projects未同步，不自动合并。
'''
if sys.argv[1]=='prepare':
    for rel in ('PROJECT_MEMORY_ZH.md','progress/jieruiz/STATUS.md','work/jieruiz/171/HANDOFF.md'):
        p=ROOT/rel;p.write_bytes(note.encode()+p.read_bytes())
    c=ROOT.parents[1]/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';m=ROOT.parents[1]/'PROJECT_MEMORY_ZH.md'
    assert c.read_bytes()==m.read_bytes()
    c.write_bytes(note.encode()+c.read_bytes());m.write_bytes(c.read_bytes())
    (D/'PR_BODY.md').write_bytes(body.encode())
    archive=ROOT.parents[1]/'project_archives/qwen3_nonlinear_width_20261024/sealed-2880.tar.gz'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()=='5ea60da95c0d186f5ac1b20b68ff4348fb04107fb411340a93762cda2b889ac4'
    result=dict(status='verified_completed',cases=28,source='71cb58d0b4cfbf42004c34e28d5b5250f6a000c8',
        job=2880,local_format_tests=4,server_tests=6,all_documents_sha_verified=True,
        all_36_layers_and_prefixes=True,summary_command='python work/jieruiz/171/summarize.py',
        no_training_or_rtl=True,nonlinear_finite_sampling_tested=False)
    (D/'VALIDATION.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
elif sys.argv[1]=='publish':
    import github as p
    assert p.api('GET','/user')['login']=='jieruiz'
    result=p.push()
    pr=p.api('PATCH',p.PREFIX+'/pulls/172',dict(title='Qwen3-4B非线性位宽：28项初筛，8位组合PPL变化约0.6%',body=body))
    if pr['draft']:
        mutation='mutation($id:ID!){markPullRequestReadyForReview(input:{pullRequestId:$id}){pullRequest{isDraft}}}'
        r=p.api('POST','/graphql',dict(query=mutation,variables=dict(id=pr['node_id'])))
        assert not r.get('errors'),r
    comment=p.api('POST',p.PREFIX+'/issues/171/comments',dict(body=body+'\n\nPR: '+pr['html_url']+'\n科学提交：'+result['head']))
    changed=p.git('diff','--name-only',p.BASE,result['head']).decode().splitlines()
    import base64
    verified=[]
    for name in changed:
        blobsha=p.git('rev-parse',result['head']+':'+name).decode().strip()
        obj=p.api('GET',p.PREFIX+'/git/blobs/'+blobsha)
        raw=base64.b64decode(obj['content'])
        assert raw==p.git('show',result['head']+':'+name),name
        verified.append(dict(path=name,sha256=hashlib.sha256(raw).hexdigest()))
    result.update(pr=pr['html_url'],state='open_ready_not_merged',issue_comment=comment['html_url'],files=verified,project_board_synced=False)
    p.save('FINAL_PUBLICATION.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False))
