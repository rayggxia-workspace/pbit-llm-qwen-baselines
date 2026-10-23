from pathlib import Path
import importlib.util, json, sys, concurrent.futures, base64
ROOT=Path(__file__).resolve().parent
REPO='rayggxia-workspace/pbit-llm-qwen-baselines'
BASE='pbit-tlm-attention-details-20261016'
def save(name,obj):
    (ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def client():
    spec=importlib.util.spec_from_file_location('gh_identity_verified',ROOT.parent/'pbit_attention_e01_20261019/control.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);mod.ROOT=ROOT
    s=mod.client();assert json.loads((ROOT/'repository.json').read_text(encoding='utf-8'))['permissions']['push'];return s
def main():
    s=client();u='https://api.github.com/repos/'+REPO+'/'
    def get(path):
        r=s.get(u+path,timeout=45);r.raise_for_status();return r.json()
    if sys.argv[1]=='inspect':
        rows=get('issues?state=all&per_page=100&sort=updated&direction=desc');save('recent.json',rows)
        branch=get('branches/'+BASE);save('base.json',branch);ref=branch['commit']['sha']
        print(json.dumps({'base':ref,'issues':[{'n':r['number'],'title':r['title'],'state':r['state'],'updated':r['updated_at'],'owner':r['user']['login']} for r in rows[:50]]},ensure_ascii=False))
        tree=get('git/trees/'+ref+'?recursive=1');assert not tree['truncated'];save('tree.json',tree)
        paths=['README.md','AGENTS.md','PROJECT_MEMORY_ZH.md','progress/amlink1219/STATUS.md','progress/jieruiz/STATUS.md','architecture_tlm/WORKSPACE_LATEST_ZH.md','baselines/BASELINES.md','requirements.txt']
        def read(path):
            r=s.get(u+'contents/'+path,params={'ref':ref},timeout=45)
            if r.status_code==404:return path,False
            r.raise_for_status();(ROOT/('remote_'+path.replace('/','_'))).write_bytes(base64.b64decode(r.json()['content']));return path,True
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            print(json.dumps(list(pool.map(read,paths))))
        print(json.dumps({'related_paths':[x['path'] for x in tree['tree'] if any(w in x['path'].lower() for w in ['sparq','qwen3','ppa8']) and x['type']=='blob'][:120]},ensure_ascii=False))
    elif sys.argv[1]=='get':
        for path in sys.argv[2:]:
            data=get(path);save(path.replace('/','_').split('?')[0]+'.json',data)
            if isinstance(data,list):print(json.dumps({'path':path,'data':[{'author':x.get('user',{}).get('login'),'body':x.get('body')} for x in data]},ensure_ascii=False))
            else:print(json.dumps({'path':path,'body':data.get('body'),'state':data.get('state'),'head':data.get('head',{}).get('sha')},ensure_ascii=False))
    elif sys.argv[1]=='create':
        marker='<!-- amlink1219-sparq-baseline-20261023 -->'
        rows=get('issues?creator=amlink1219&state=all&per_page=100')
        found=[r for r in rows if marker in (r.get('body') or '')]
        if found:data=found[0]
        else:
            assert not (ROOT/'issue_intent.json').exists(),'recover prior write before retry'
            body=marker+'\n负责人amlink1219。用户明确要求核对SparQ原论文与官方代码，将现有max4/小网络筛选替换为SparQ baseline，评测Qwen3 4B的PPL、ARC-Easy/HellaSwag/PIQA并评估功耗面积速度。\n\n分工：沿用Issue139文献及已有模型/评分协议；不覆盖Issue144/PR147已完成26项后缀，不接管其原作业；不重启Issue116/123全尺寸FFN。仅新SparQ实现/对照/成本及相关接合。当前Base与后训练模型名称差异已向用户核对，算法先独立实现。\n\n依赖：集成2f233449；Qwen3原生QK-Norm/RoPE/GQA适配参考PR147@357db588；官方三任务评分参考PR149。任务独立checkout/分支，历史结果/默认快照保留。\n\n验收：\n- [ ] 固定论文/官方代码SHA，区分GQA论文probability-sum与官方tag rawscore-sum及k/local off-by-one\n- [ ] SparQ核心、Qwen3接合、官方oracle/机制/真实dense等价门槛\n- [ ] 同模型配对完整WT2与三任务准确率，所有计分token实际走替换路径，阶段结果与未完成项分开\n- [ ] GPU速度/能耗与ASIC估算/STA-PPA分开；完整selector/布局/更新成本，不虚构物理结果\n- [ ] 源码/配置/输入版本/结果SHA/失败证据、STATUS/HANDOFF和PR同步\n\n只在本人规范home的Slurm分配内运行；GPU至多1个且跨配置服务器检查在途任务。文献Zotero后台当前关闭，SparQ已有待导入原PDF，完成前保留可恢复收录状态。无自动合并或权限变更。'
            payload={'title':'SparQ作为Qwen3-4B筛选基线：原实现核对、PPL/任务准确率与硬件成本','body':body,'assignees':['amlink1219']}
            save('issue_intent.json',payload);r=s.post(u+'issues',json=payload,timeout=45);r.raise_for_status();data=r.json()
        save('issue_receipt.json',data);print(json.dumps({'number':data['number'],'url':data['html_url']},ensure_ascii=False))
    else:raise ValueError(sys.argv[1])
if __name__=='__main__':main()
