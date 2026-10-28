"""Dated local progress/memory delta; preserve concurrent task evidence."""
from report_dtype import *
stage='''## 2026-10-28 Issue198：Qwen3-4B softmax入口BF16/FP32审计完成

用户要求确定QK分数是否必须FP32；rayggxia继续task/198-attention-compare / 草稿PR199，base main，本次执行父提交0d8a6f1a加不可变5文件SHA快照；工作目录tmp/attention-compare-issue198-20261027。GPU3290已完成、本人队列为空，无全量PPL/新RTL/PPA，统一电路台账不新增run。

同Qwen3-4B后训练revision1cfa9a7、权重/tokenizer及WT2原文/token SHA核验，BF16原生SDPA参考每窗复跑两次，4/4词表logits逐位一致。WT2起点0/4096、长度512/2048，层0/12/23/35、全32头，16个query-layer/512头行；另对同一批固定SparQ128候选诊断，共32张量比较。无随机采样，单seed0确定性测试，不冒称独立1024原生行或全层PPL。

RTX5090/torch2.7.1+cu128/transformers4.51.3，全部32个被测decode调用profiling确认FlashAttention。PyTorch2.7.1固定子模块979702c8源码表明QK acc_s为FP32并直接进入softmax，之后概率片段才转BF16用于PV；没有完整score矩阵必须落盘的要求。只对本批batch1/query_len1形状实测，不冒称历史batch32/prefill所有调用都已追踪。BF16输入输出不代表全部内部BF16；eager原生BF16 score→FP32 softmax也可执行。因此FP32是原生融合内核选择，BF16 score接口可行但不逐位等价。

仅将同一FP32 score舍入BF16再用相同FP32 softmax/PV：完整KV平均/最大单头TV0.360387%/1.607700%，128候选0.357265%/1.606836%；128候选输出相对RMS跨16张量平均0.606232%、最大张量1.004689%，argmax6/512变化。不是逐头最大输出误差，不是PPL变化，不含LUT/概率阈值量化或有限随机误差。可将BF16 score作为后续接口候选、FP32保留参考，不自动修改当前默认或声称模型无损。

正式experiments/attention_score_dtype_20261028/REPORT_ZH.md、SUMMARY/RESULTS/provenance/COMPLETE/REFERENCES；源码audit.py，辅助work/rayggxia/198/deploy_dtype.py/report_dtype.py。DTYPE_SOURCE/SUBMISSION/COLLECTION绑定原始6文件SHA及3290；本机project_archives/attention_compare_issue198_20261027/score_dtype_20261028。实际上传回读查DTYPE_PUBLICATION.json；PR199待审未合并，Issue开放，Projects沿权限限制待同步。下一步在同协议下验证BF16分数＋有限LUT接口质量；本轮不启动全量PPL。

---

'''
def main():
    for p in [R/'progress/rayggxia/STATUS.md',W/'HANDOFF.md']:
        b=p.read_bytes();assert not b.startswith(stage.encode());p.write_bytes(stage.encode()+b)
    backup=A/'reading_preimages';backup.mkdir(exist_ok=False);mem=[]
    for i,p in enumerate([WS/'PROJECT_MEMORY_ZH.md',WS/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md']):
        b=p.read_bytes();(backup/f'memory{i}.bin').write_bytes(b);assert p.read_bytes()==b;p.write_bytes(stage.encode()+b)
        mem.append(dict(path=str(p),pre_sha256=hashlib.sha256(b).hexdigest(),new_sha256=sha(p)))
    save(W/'DTYPE_MEMORY_SYNC.json',dict(memories=mem,preimages=str(backup),old_bytes_preserved=True))
    print('STATUS_HANDOFF_MEMORY_UPDATED')
if __name__=='__main__':main()
