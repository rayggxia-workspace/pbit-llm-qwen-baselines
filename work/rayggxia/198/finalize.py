"""Archive raw runs, bind evidence, render first-stage report (no experiments)."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[3]
WS=ROOT.parents[1]
A=ROOT/'architecture_tlm/attention_compare_20261027'
W=ROOT/'work/rayggxia/198'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8'))
def text(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(s.encode('utf-8'))


def main():
    archive=WS/'project_archives/attention_compare_issue198_20261027/raw_runs_v1.zip'
    archive.parent.mkdir(parents=True,exist_ok=True)
    assert not archive.exists(), 'archive already frozen'
    files=[p for p in (A/'results').rglob('*') if p.is_file() and p.suffix!='.vvp']
    members={str(p.relative_to(A)).replace('\\','/'):dict(sha256=sha(p),bytes=p.stat().st_size) for p in files}
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,str(p.relative_to(A)).replace('\\','/'))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,meta in members.items():
            b=z.read(name);assert hashlib.sha256(b).hexdigest()==meta['sha256'] and len(b)==meta['bytes']
    write(W/'RAW_ARCHIVE.json',dict(path=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,
         members=members,access='authorized local archive; not publicly accessible',
         failures_preserved=['initial Python3.8 newline argument','rtl_v1 sandbox WinError623',
                             'rtl_v2 testbench display format; fixed in v3',
                             'v1/v2 numerical snapshots superseded by final feedback-aware schedule'],
         regenerate='run.py/quality.py/validate_rtl.py; binaries excluded as regenerable'))
    original=Path(r'C:/Users/86134/.codex/visualizations/2026/10/27/01a17c55-a1bb-7f23-bf0d-443d05f92a2c/output')
    sources=[original/'ATTENTION_COMPARISON_HANDOFF_ZH_20261027.md',
             original/'pdf/Attention与FFN数字基线调研及估算建议_20261027.pdf',WS/'AGENTS.md',WS/'PROJECT_MEMORY_ZH.md']
    deps=[ROOT/'architecture_tlm'/f for f in ['parallel_sampler_v5.py','winner_hold_tlm_v5.py','corrected_rejection_tlm_v5.py']]
    write(W/'INPUTS.json',dict(read_on='2026-10-27',base='d83eeb1fc6b89a3dff51b5b62bf79acf665c7166',
          identity='rayggxia via GitHub connector; CLI git author config is not login',
          user_sources={str(p):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sources},
          dependencies={str(p.relative_to(ROOT)):sha(p) for p in deps},
          singleton=dict(parent_git='8f87dc56516598716cbcbaf1a0e6432d9b7d352b',
             parent_path='architecture_tlm/digital_ppa_v1/rtl/nr_attention_control.sv',
             parent_sha256='e4e562e158a0cde44514c574e2dc6f8ade84e3ac3a40ca8d4864054fdd96148f',
             extraction='unchanged prefix through first endmodule, plus LF; original CRLF retained',
             extracted_sha256=sha(A/'rtl/nr_singleton_tree.sv')),
          model_tokenizer_dataset='not applicable: synthetic normal arrays; no model loaded',
          literature=[
           dict(name='FlashAttention',url='https://arxiv.org/abs/2205.14135',use='online stable fused reference, no probability matrix'),
           dict(name='FlashAttention-2',url='https://arxiv.org/abs/2307.08691',use='legal work partition/parallelism; no GPU throughput used as ASIC cycle'),
           dict(name='SANTA v2',url='https://arxiv.org/html/2605.01910v2',code='https://github.com/OPUSLab/SANTA',use='systematic PV/second pass/budget; no CUDA code copied'),
           dict(name='ITA',url='https://arxiv.org/abs/2307.03493',code='https://github.com/pulp-platform/ITA',
                license='software Apache2.0, hardware Solderpad0.51; no external RTL vendored yet',use='future D1 integer reference; not implemented in this stage'),
           dict(name='H-FA v1',url='https://arxiv.org/html/2511.00295v1',use='ordinary FA hardware comparison; 19/20/21 are pipeline latency, no PPA values imported'),
           dict(name='Sanger',url='https://liqianglu-zju.github.io/files/conference/2021/MICRO_2021_Sanger.pdf',use='sparse prediction boundary'),
           dict(name='SOFA v1',url='https://arxiv.org/html/2407.10416v1',use='cross-stage tiling/interface boundary')],
          supplemental_SOT='local PDF listed in user handoff; not re-read in this stage; no physical-source assertion'))
    summary=read(A/'results/sweep_final/SUMMARY.json')
    quality=read(A/'results/quality_final/QUALITY.json')
    rtl=read(A/'results/rtl_v4/VALIDATION.json')
    groups=defaultdict(list)
    for r in summary:
        if r['length']==2048 and r['d']==128:groups[r['mode']].append(r)
    lines=['# Attention单query首轮实现与结果（Issue198）','',
       '2026-10-27；rayggxia；main@d83eeb1f；task/198-attention-compare。当前是第一阶段交付，后续验收仍开放。',
       '', '已读取用户PDF/交接、最新远端规则/README、本人187交接，以及78/87/186状态；PR88已合并，PR192/197仍待审。',
       '', '本轮新增六方案数值对照、有限tile宏调度和完整校正拒绝数字控制。108个合成案例全部完成；6项机制检查通过；N16/64/512×三seed的22500拍RTL与独立oracle逐拍全等。RTL为外供比特控制，未综合/STA/PT，不是完整QK到V的硬核。',
       '', '## 固定预算观察','',
       '同一合成BF16 QKV输入、L2048/d128、S128、三seed均值；数字算术FP64数学参考，宏调度不是逐位BF16硬件。K/V字节为本head准确burst集合；summary/state本地流量另计。',
       '', '|方案|条件周期|K字节|V字节|相对完整输出L2误差|', '|---|---:|---:|---:|---:|']
    for mode,rows in groups.items():
        mean=lambda k:sum(r[k] for r in rows)/len(rows)
        lines.append(f"|{mode}|{mean('conditional_cycles'):.2f}|{mean('K_physical_bytes'):.0f}|{mean('V_physical_bytes'):.0f}|{mean('relative_error_full'):.4f}|")
    lines += ['', '合成V近零均值时相对误差易显大，不能转成PPL；QUALITY.json同时保存绝对MSE、目标分布单样本方差归一化误差、筛选误差及采样误差。二者平方误差存在交叉项，不声称可直接相加。',
       '', '## 探索性质量匹配','',
       '固定以上输入，以完整分布IID128的解析期望MSE（约0.99772）为全输出阈值。扫描S32/128/512/1024；下表是三seed均值首次过线的测试网格点，不是置信保证/精确最小预算/模型验收。D0/P1无采样预算，表中S列不适用。',
       '', '|方案|首次观察预算|条件周期|','|---|---:|---:|']
    for mode,r in quality['matched'].items():
        lines.append(f"|{mode}|{'不适用' if mode in ('D0','P1') else r['samples'] if r else '未达标'}|{r['cycles_mean']:.2f}|" if r else f'|{mode}|未达标|—|')
    lines += ['', '校正拒绝为达此探索阈值要S512，条件周期117264，约为D0的3.49倍；赢家S512约22181拍。不能用固定S128的省流量数字宣传同质量收益，更不能据一次合成输入确定最终方案。',
       '', '## 实现合同与限制','',
       '- D0/P1分块在线max/分母/非归一输出，末尾统一归一化；无需长度L的概率行，更无L×L概率矩阵。',
       '- P0/P2准确softmax＋systematic CDF，保留全局归一化、第二遍扫描和直方图费用。P3/P4直接复用已合PR88，地址只映射一次，无二次PV抽样。',
       '- P1–P4共享max4/64块、首末2强制、Bernoulli＋固定配额修复。此轮中心0/温度1为合成校准，非已训练Qwen筛选器。summary生成是fixture预处理；warm路径计追加更新/存储/读出，cold全K读量与生成加法另列，不能声称首次查询也无需全K。',
       '- 2有限K/V tile槽、有限本地容量、共享memory_link/MAC/vector/local_sram资源和在线依赖。V按唯一地址读取，以重复加法保留次数，d64按L7反馈限制发起率。QK/PV吞吐是并行点积归约宏假设，不将独立L14 MAC直接当同状态II1。',
       '- PR88采样时序仍为该接口的条件FSM；本次RTL实际实现与其源/配置等待尚未逐边沿绑定，因此没有用RTL小例冒称更新完整TLM。此模块实验未改unified_v6、PR192新存储或其sink检查。',
       '- Link不是DRAMSys，不含bank/NoC/DRAM命令级、GQA多头调度；kv_union只提供同组物理并集检查。没有新增平行整机模型或修改主入口。',
       '- 完整能量/面积为null：MAC、Softmax、RNG、LUT/驱动转换、时钟门控/idle、互连与有效外存未同边界闭合；文献跨工艺PPA未套为本次实测。',
       '- RTL具有配置valid/ready、流水singleton、m反馈、精确低m位全零校正、proposal cap和1条有限输出寄存。cfg_ready表示后端已稳定；独立随机性由外部源保证。cap失败之前可能已输出部分地址，消费者只在done且!failed时提交整query，失败时丢弃其部分和。',
       '- 未实施D1/ITA移植、赢家控制RTL、完整V gather/累加RTL、后训练Qwen捕获/匹配BF16/PPL、同吞吐面积和真实PPA；不自动恢复暂停116/123或启动昂贵任务。',
       '', '## 复现与后续','',
       '从仓库根运行，输出目录必须不存在；Python3.12＋NumPy2.3.5用于正式数值结果：',
       '', '```sh',
       'python -B -m unittest architecture_tlm.attention_compare_20261027.test_core -v',
       'python -B -m architecture_tlm.attention_compare_20261027.run --output NEW_SWEEP',
       'python -B -m architecture_tlm.attention_compare_20261027.quality --output NEW_QUALITY',
       'python -B -m architecture_tlm.attention_compare_20261027.validate_rtl --iverilog /path/iverilog --vvp /path/vvp --ivl-lib /path/lib/ivl --output NEW_RTL',
       '```','',
       'Icarus10.1在Windows沙箱内WinError623，已通过自动审批在沙箱外完成上述短功能验证；无许可EDA/服务器/GPU任务。原失败日志/快照保留，rtl_v4是最终功能版本；v3与v4属于同控制源码的覆盖补充，不计为两个独立电路run。',
       '', '精确输入/源码/文献入口见work/rayggxia/198/INPUTS.json。原始逐case结果、事件、比特轨迹与编译日志在RAW_ARCHIVE.json指向的本地ZIP，逐成员SHA已核；Git保留小型汇总和manifest。后续优先绑定RTL时序与源接口、用后训练真实QKV验证质量，再扩GQA和D1/存储/成本。',
       '', '统一台账本任务仅新增attention-rejection-198-20261027。main尚无完整registry工具，聚合check/render在本人辅助目录进行，并增量同步根阅读镜像；依赖PR197不混入本PR。Projects权限未核实/待维护者同步。发布回执见PUBLICATION.json；PR待审不关闭Issue。','']
    text(A/'README_ZH.md','\n'.join(lines))
    text(A/'.gitattributes','* -text\n')
    text(A/'.gitignore','results/**\n!results/sweep_final/\n!results/sweep_final/SOURCE.json\n!results/sweep_final/CONFIG.json\n!results/sweep_final/SUMMARY.json\n!results/sweep_final/MANIFEST.json\n!results/quality_final/\n!results/quality_final/QUALITY.json\n!results/rtl_v4/\n!results/rtl_v4/SOURCE.json\n!results/rtl_v4/VALIDATION.json\n__pycache__/\n')
    text(W/'.gitignore','registry_check/\n__pycache__/\nPUBLISH_PAYLOAD.json\n')
    stages=dict(functional='pass',synthesis='not_run',sta='not_run',power='not_run',postlayout='not_run')
    artifacts=[]
    for rel,role in [('results/rtl_v4/SOURCE.json','executed_source_manifest'),('results/rtl_v4/VALIDATION.json','functional_summary')]:
        f=A/rel;artifacts.append(dict(path=str(f),role=role,present_at_registration=True,required=True,sha256=sha(f),bytes=f.stat().st_size))
    artifacts.append(dict(path=str(archive),role='original_vectors_logs_and_prior_failures',present_at_registration=True,required=True,
                          sha256=sha(archive),bytes=archive.stat().st_size))
    record=dict(schema_version=1,id='attention-rejection-198-20261027',name='Attention校正拒绝控制：流水反馈/配置/回压22500拍',
       family='Attention/控制',registered_on='2026-10-27',owner='rayggxia',issue=198,evidence_level='RTL_FUNCTIONAL',
       status='functional_pass_ppa_pending',stages=stages,
       boundary='N16/64/512外供proposal/fair bit，singleton流水＋m0..24反馈＋配置握手＋一输出寄存；不含RNG/LUT/QK/V/SRAM',
       conditions=dict(node_nm=None,corner=None,voltage_V=None,temperature_C=None,clock_MHz=100,seeds=[17,503,1009],
                       window_ns=25000,load_pF=None,sdf=False,spef=False,cts=False,activity='synthetic external bits;2500cycles percase'),
       source=dict(git_commit=None,source_manifest_sha256=sha(A/'results/rtl_v4/SOURCE.json'),binding='main d83eeb1f plus exact RTL/TB/oracle manifest; not HEAD alone'),
       artifacts=artifacts,cases=rtl['cases'],limitations=['功能only，100MHz只是TB时钟，未STA/PT/综合/物理源','RTL与PR88端到端时序尚未绑定','失败query丢弃已输出的部分和；无IID兜底','本地归档非远端公共可访问；旧失败保留'],
       next_action='真实源接口/反馈代价和N512代表STA/PT，后训练真实QKV质量；不自动启动许可EDA')
    write(ROOT/'digital_circuit_simulation_registry/records/attention-rejection-198-20261027.json',record)
    # Evaluate union without editing another task checkout. Record and root
    # mirror are updated separately only after successful portable checks.
    check=W/'registry_check'
    check.mkdir(exist_ok=False)
    source=WS/'digital_circuit_simulation_registry'
    for name in ('registry.py','catalog.json','archive_inventory.csv'):shutil.copyfile(source/name,check/name)
    shutil.copytree(source/'records',check/'records')
    write(W/'REGISTRY_PREIMAGE.json',dict(catalog_sha256=sha(source/'catalog.json'),records={p.name:sha(p) for p in (source/'records').glob('*.json')}))
    subprocess.run([sys.executable,str(check/'registry.py'),'add',str(ROOT/'digital_circuit_simulation_registry/records/attention-rejection-198-20261027.json')],check=True)
    r=subprocess.run([sys.executable,str(check/'registry.py'),'check'],capture_output=True,text=True,check=True)
    write(W/'REGISTRY_CHECK.json',json.loads(r.stdout))
    subprocess.run([sys.executable,str(check/'registry.py'),'render'],check=True)
    write(W/'DELIVERY.json',dict(stage='first implementation complete, broader Issue198 open',
           tests=6,synthetic_cases=108,quality_grid_cases=72,rtl_cases=9,rtl_cycles=22500,
           no_model_or_EDA_jobs=True,archive_sha256=sha(archive),root_registry_sync='pending',
           registry_records=json.loads(r.stdout)['records']))
    print(json.dumps(dict(archive_bytes=archive.stat().st_size,archive_members=len(members),registry=json.loads(r.stdout))))


if __name__=='__main__':main()
