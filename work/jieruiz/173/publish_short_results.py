# -*- coding: utf-8 -*-
import json
import github as g
assert g.api('GET','/user')['login']=='jieruiz'
r=g.push()
comment='''Slurm2891全部封存核验：48份/46唯一配置，36层全前缀，27项预检及原字节SHA通过。8×128后缀PPL，非完整WT2；BF16=13.5660。减半固定四档的三seed均值：IID64=27.4020，联合分层32/64/128=103.8940/21.8821/15.3647，最佳仍高13.26%。报告：qwen3/results/and_direct_20261024/short/REPORT_ZH.md。前级固定W8、四档、T=K64，准确Attention；没有训练或PPA。原件和执行SHA在RAW_INDEX，原尺度对照与旧任务逐值一致。已推送提交 %s，PR174待审未合并；STATUS/HANDOFF/长期备忘录已更新，Projects缺read:project权限待同步。'''%r['head']
r['issue_comment']=g.api('POST',g.PREFIX+'/issues/173/comments',{'body':comment})['html_url']
r.update(pr='https://github.com/'+g.REPO+'/pull/174',merged=False)
g.save('SHORT_PUBLICATION.json',r);print(json.dumps(r))
