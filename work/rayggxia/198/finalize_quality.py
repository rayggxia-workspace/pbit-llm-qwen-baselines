"""Update task indexes only after the independent full-result audit passes."""
from pathlib import Path
import hashlib,json,subprocess
R=Path(__file__).resolve().parents[3];W=Path(__file__).resolve().parent
S=json.loads((R/'experiments/sparq_ising_20261028/results/SUMMARY.json').read_bytes())
assert S['full_status']=='complete'
F=S['full']; T=S['full_logical_kv']
winner=F['winner_S128']
text=f'''## 2026-10-28 SparQ＋Ising完整WT2三seed完成（Issue198 / PR199）

负责人rayggxia；task/198-attention-compare，原独立checkout继续复用，PR待审未合并。GPU Slurm3270_[0-2]完整结果均已收齐，独立SHA/回执、299077目标恰好各一次、36层计分覆盖及每头160更新/128保留采样审计通过。执行源a7108f8cba2c72ad319114af34557f4cec2b793d；短流源d9b64717641ae8f7efeaa2e9375a1b01a30361d0。模型Qwen/Qwen3-4B后训练revision1cfa9a7208912126459214e8b04321603b3df60c，权重/tokenizer/原始train-test/token SHA在provenance中核验。原BF16 FFN/投影/归一化不改，dense prefill、全36层单query Attention替换；无chat模板、无BOS，window2048/stride1024、batch32。

完整PPL：BF16 {F['bf16']['ppl_mean']:.6f}；纯SparQ {F['sparq_exact']['ppl_mean']:.6f}；SparQ＋winner S128 {winner['ppl_mean']:.6f}±{winner['ppl_sample_std']:.6f}（三seed样本标准差），相对BF16 {winner['delta_ppl_percent_vs_bf16']:+.3f}%，相对纯SparQ {winner['delta_ppl_percent_vs_sparq']:+.3f}%。固定r32/k128/local32、burn32/spacing1，赢家地址直接V读出；理想FP32 sigmoid/Philox行为参考，不是器件或q/256实测。完整结果不同于1024目标初筛，短流S32退化/S512≈IID128的负结果保留。

完整平均每KV组唯一V {winner['mean_unique_v_per_kv_group']:.3f}行。理想标量读取、候选K维度复用、4Q完整去重下，K+V逻辑元素需求为dense的{100*T['winner_vs_dense_ratio']:.2f}%、纯SparQ的{100*T['winner_vs_sparq_ratio']:.2f}%；不是实测DRAM字节或速度。SparQ第一阶段全N近似softmax和top-k仍存在，只替换候选上的第二阶段softmax/PV。当前说明质量可行但未证明同质量完整硬件PPA胜出；完整缓存、布局、仲裁、累加及有限相关采样成本待补，不继承旧控制RTL为整机PPA。无新数字电路台账run。

正式源码及报告：experiments/sparq_ising_20261028/results/REPORT_ZH.md、SUMMARY.json。准确SOURCE/SUBMISSION/COLLECTION见work/rayggxia/198/QUALITY_*；原始结果保留本人GPU目录/home/Hongjie_Zeng/projects/attention-sparq-ising-issue198-20261028和本地project_archives/attention_compare_issue198_20261027/quality。report_quality.py可按封存原件重建。下一步以纯SparQ为硬件主要对手，在匹配质量下接有限KV读出和控制费用；未自动启动额外全量扫参、未合并PR或关闭Issue，Projects权限待维护者同步。发布以QUALITY_PUBLICATION.json和远端实际head为准。

'''
for rel in ['progress/rayggxia/STATUS.md','work/rayggxia/198/HANDOFF.md']:
    p=R/rel;old=p.read_bytes();assert not old.startswith(text[:60].encode())
    p.write_bytes(text.encode()+old)
log=R/'architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md'
old=log.read_bytes() if log.exists() else subprocess.check_output(['git','show','HEAD:architecture_tlm/ARCHITECTURE_OPTIMIZATION_LOG_ZH.md'],cwd=R)
assert text[:60].encode() not in old
log.parent.mkdir(parents=True,exist_ok=True);log.write_bytes(old+b'\n\n'+text.rstrip().encode()+b'\n')
archive=Path('C:/Users/86134/Documents/a_P_BIT/project_archives/attention_compare_issue198_20261027/quality/memory_preimages');archive.mkdir(exist_ok=True)
receipt=[]
for p in [Path('C:/Users/86134/Documents/a_P_BIT/PROJECT_MEMORY_ZH.md'),Path('C:/Users/86134/Documents/a_P_BIT/tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md')]:
    old=p.read_bytes();sha=hashlib.sha256(old).hexdigest();pre=archive/(sha+'.md');pre.write_bytes(old)
    new=text.encode()+old;p.write_bytes(new)
    receipt.append(dict(path=str(p),preimage=str(pre),before_sha256=sha,after_sha256=hashlib.sha256(new).hexdigest(),previous_bytes_preserved=True))
(W/'QUALITY_FULL_MEMORY_SYNC.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(text)
