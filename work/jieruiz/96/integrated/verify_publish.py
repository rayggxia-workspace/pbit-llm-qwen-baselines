"""Read back publication bytes and update the existing PR/Issue only."""
import base64,concurrent.futures,datetime,hashlib,importlib.util,json,subprocess
from pathlib import Path
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[2];OUT=TASK/'integrated'
s=importlib.util.spec_from_file_location('p',TASK/'publish.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def save(name,r):
 with (OUT/name).open('x',encoding='utf-8',newline='\n') as f:json.dump(r,f,ensure_ascii=False,indent=2);f.write('\n')
def main():
 assert m.api('GET','/user')['login']=='jieruiz'
 head=m.git('rev-parse','HEAD').decode().strip();assert m.api('GET',m.PREFIX+'/git/ref/heads/'+m.BRANCH)['object']['sha']==head
 files=['architecture_tlm/unified_v6/rng_integrated.py','architecture_tlm/unified_v6/model.py','architecture_tlm/unified_v6/config.py','architecture_tlm/unified_v6/configs/rng_ppa100.json','architecture_tlm/unified_v6/RNG_INTEGRATION_RESULTS_ZH.md','architecture_tlm/unified_v6/results/integrated_rng_20261022_v3/SUMMARY.json','work/jieruiz/96/integrated/AUDIT.json','work/jieruiz/96/HANDOFF.md','progress/jieruiz/STATUS.md']
 def verify(p):
  blob=m.git('rev-parse',head+':'+p).decode().strip();data=base64.b64decode(m.api('GET',m.PREFIX+'/git/blobs/'+blob)['content']);assert data==m.git('show',head+':'+p),p
  return dict(path=p,blob=blob,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(verify,files))
 save('REMOTE_VERIFY_SCIENCE.json',dict(head=head,repo=m.REPO,files=rows))
 pr=m.api('GET',m.PREFIX+'/pulls/103');assert pr['state']=='open' and not pr['merged'] and pr['head']['ref']==m.BRANCH
 pr=m.api('PATCH',m.PREFIX+'/pulls/103',dict(title='TLM：真实随机服务接入整机，统一100MHz并完成40项对照',body=(OUT/'PR_BODY.md').read_text(encoding='utf-8')))
 body='''已按用户要求把最新随机架构真正接入FullDecode默认，计算/SC/随机源/采样器/种子统一100MHz，SRAM保持SS宏约束80MHz。科学交付 `HEAD_SCIENCE` 已推送同PR103；原Issue95源码/RTL未改。

40/40完整模型情景完成、0失败；93项机制/回归、1421项源/归档/时钟/种子/全层/帧数/重放/互斥收费核对通过。另96个封存artifact的Git blob SHA符合manifest，9个关键远端blob已原字节读回。执行31aa4fa31fbfb7d74629b54811936ac30a41c250。12项S8赢家/拒绝是整机连通诊断，不冒充默认全预算质量；原52不变，104计划0完成/0失败主动取消并保留CANCELLED。

报告：[RNG_INTEGRATION_RESULTS_ZH](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/HEAD_SCIENCE/architecture_tlm/unified_v6/RNG_INTEGRATION_RESULTS_ZH.md)。Qwen2K SC+筛选PV seed0旧197.93816→新198.00316ms，约+0.033%；BF16准确对照时间和存储完全一致。新q/256影响地址/分布，差异不能全叫接口开销，也不继承PPL。native端点PPA取100MHz实报告做条件插值，完整随机/整机PPA仍未知。

本地/远端无本任务运行作业；无新GPU/Slurm/模型PPL/RTL/PT/实际DRAMSys。代码、40项原件/manifest、报告、个人STATUS及HANDOFF均已推送；后续补publication回执和长期备忘录状态。PR103待审未合并，Issue96不关闭。Projects沿read:project不足待同步，现有检查台旧52快照未自动刷新。'''.replace('HEAD_SCIENCE',head)
 comment=m.api('POST',m.PREFIX+'/issues/96/comments',dict(body=body))
 save('PUBLICATION.json',dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),repo=m.REPO,user='jieruiz',science_head=head,execution_commit='31aa4fa31fbfb7d74629b54811936ac30a41c250',branch=m.BRANCH,PR=dict(url=pr['html_url'],number=103,state=pr['state'],draft=pr['draft'],merged=False,base=pr['base']['ref']),issue_update_url=comment['html_url'],remote_blobs_verified=len(rows),projects='read:project unavailable, pending',metadata_receipt_followup='separate later commit, does not change execution/results'))
 print(json.dumps(dict(head=head,verified=len(rows),PR=pr['html_url'],issue=comment['html_url'])))
if __name__=='__main__':main()
