"""Rebuild the readable report and verify immutable per-run manifests."""
import hashlib
import json
import statistics
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'architecture_tlm/results/parallel_sampler_v5_20261021'


def write(path,obj):
    with path.open('w',encoding='utf-8',newline='\n') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')


def main():
    verified=[]
    for folder in ('standalone','attention_smoke'):
        p=OUT/folder;manifest=json.loads((p/'MANIFEST.json').read_text(encoding='utf-8'))
        for name,digest in manifest.items():
            if name=='sources':
                for source,sha in digest.items():
                    assert hashlib.sha256((ROOT/'architecture_tlm'/source).read_bytes()).hexdigest()==sha
                continue
            assert hashlib.sha256((p/name).read_bytes()).hexdigest()==digest
            verified.append(str((p/name).relative_to(ROOT)).replace('\\','/'))
    a=json.loads((OUT/'standalone/SUMMARY.json').read_text(encoding='utf-8'))
    b=json.loads((OUT/'attention_smoke/SUMMARY.json').read_text(encoding='utf-8'))
    assert len(a['results'])==30 and len(b['results'])==2
    groups={}
    for r in a['results']:groups.setdefault((r['input_id'],r['kind'],r['samples']),[]).append(r)
    lines=['# 全宽并行采样器 v5：本次可执行验证','',
        '18项新检查＋10项原v4检查通过，30个三seed合成模块情景和2个单层完整decode情景完成。',
        '这些是声明资源和时序参数下的事务结果，输入为合成分数，不是实际Qwen推理、PPL、PT或物理随机源测量。能量和面积未标定，完整结果为null。','',
        '源接口每轮一次读取所有候选，不按64路分波。示例10ns/拍；源命令/稳定/读取共4拍，数字树每拍2级；拒绝默认逐候选重写偏移后的驱动。','',
        '| 合成输入 | 方法 | 保留样本数 | 更新/提议数中位 | 总周期中位（范围） | 有偏bit读取中位 |',
        '|---|---|---:|---:|---:|---:|']
    for (row,kind,budget),items in groups.items():
        assert sorted(x['seed'] for x in items)==[11,29,47]
        cy=[r['elapsed_cycles'] for r in items]
        name='512等分数' if row=='synthetic_flat512' else '512节点双峰[12,12,0,...]'
        method='赢家保持' if kind=='winner_hold' else '校正拒绝'
        lines.append('| {} | {} | {} | {} | {}（{}–{}） | {} |'.format(
            name,method,budget,int(statistics.median(r['frames'] for r in items)),
            int(statistics.median(cy)),min(cy),max(cy),
            int(statistics.median(r['biased_bit_draws'] for r in items))))
    lines+=['','相同样本数不等于相同输出误差，不能用此表直接宣布谁的等质量能效更好。双峰输入拒绝很少；等分数输入的偏移反馈和重写明显更多，说明需要保留真实分数/提议轨迹及反馈前端模式。','',
        '单层完整decode连通检查：context128、14个Q头、原数字FFN、每头16样本、Link外存；不是24层真实模型实测。','',
        '| 采样器 | 配置情景ms/token | 提议/更新总数 | 完整J/token | 完整面积 |',
        '|---|---:|---:|---|---|']
    for r in b['results']:
        lines.append('| {} | {:.6f} | {} | 未标定/null | 未标定/null |'.format(
            r['kind'],r['mean_TPOT_ms'],r['sampler_frames']))
    lines+=['','模块与完整Attention地址列表、时间戳、输入SHA及代码/配置SHA见各JSON及MANIFEST；拒绝状态与保持次数均进入活动账本。',
        '代码执行提交：`'+a['code_commit']+'`。后续只增补报告和发布记录；原执行结果不重写。',
        '源码说明：[PARALLEL_SAMPLERS_V5_ZH.md](../../PARALLEL_SAMPLERS_V5_ZH.md)。',
        '限制：未重放PR86全部90组真实QKV，未做新完整模型PPL/训练/Slurm/PT/DRAMSys运行；已有27项通过说法是新增反馈测试之前的历史，本次为28项。']
    with (OUT/'RESULTS_ZH.md').open('w',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines)+'\n')
    report=dict(status='PASS',validated_result_files=len(verified),paths=verified,
        module_cases=30,attention_cases=2,new_tests=18,legacy_tests=10,
        execution_code_commit=a['code_commit'],
        scope='manifest/source consistency and result completeness; not model/PPA validation')
    write(ROOT/'work/jieruiz/87/RESULT_VERIFY.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='paths'}))


if __name__=='__main__':main()
