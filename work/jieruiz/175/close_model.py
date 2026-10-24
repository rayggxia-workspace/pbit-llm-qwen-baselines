# -*- coding: utf-8 -*-
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parents[1]
archive=BASE/'project_archives/smurf_model_20261024/sealed-2898-2902.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='f53c05e9e65d50e0a329bddd0c75380f728c48c2ae8c93a9c8e61b0046e60ba8'
p=ROOT/'work/jieruiz/175/MODEL_SUBMISSION.json';r=json.loads(p.read_bytes())
for a in r['attempts']:
    if a['job']=='2898_[0-3]':a.update(status='verified_completed',actual_physical_results=64,preflight_tests_per_shard=13)
if not any(a['job']=='2902_[4-7]' for a in r['attempts']):
    r['attempts'].append(dict(job='2902_[4-7]',commit='3ac8bfdb05ff6637b058eb8d68a004815b2fc958',
        source_sha256='06a6a47722d5911cb39bd7cb417026b6dd7ce4da470d08c8d61cb6afc3c725c9',
        snapshot='snapshot-3ac8bfdb',status='verified_completed',actual_physical_results=64,
        preflight_tests_per_shard=13,logs='logs/2902_[4-7].log',results='results/shard4..7',
        note='Exploratory smaller-range follow-up after first-run mean diagnostics; no healthy task rerun.'))
r.update(archive=str(archive),archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
         total_physical_results=128,unique_semantic_cases=118,all_layer_coverage_verified=True)
p.write_bytes((json.dumps(r,indent=2)+'\n').encode())
note='''## Issue175固定g范围FSM：完整模型试测失败结果（2026-10-24）

Slurm2898/2902八片完成；128份/118唯一配置，13项预检每片通过、documents/sidecar SHA、36层全前缀、1024目标位置和8份BF16一致核验。Qwen3-4B后训练，准确Attention、前级固定W8/x四档共享64 T=K64。后级FSM是逐拍IID随机过程，不是Binomial或均值替代。g固定G=1/2/4/8/16、4或8状态、T64/128，真实尺度进入SiLU拟合目标；无g在线max/选档，u仍TRAIN固定四档。原2894在编译预检失败、模型未启动，旧快照保留，新执行462d4fe1/3ac8bfdb。

BF16=13.566049。实际FSM最佳G8/N4/负输出单位.5/T128 PPL1757.8026；对应FSM期望623.0500，T64期望22906.145。G8/N8/负单位8的精确SiLU表期望13.2860，FSM128期望615.4719、实际1785.7054；G16/N8/.5的精确表期望13.3085。说明固定g数制并非必然失败，但当前小状态链函数拟合严重不足，不只是采样噪声。G1/2/4截断叠加劣化；不能用SMURF正半轴0..1 MAE代替LLM证据。所有结果是8×128后缀，不是完整WT2；无训练/RTL/PPA，gate/up恢复仍FP32参考。T各自有限时长拟合，改变T同时改变系数，不把差异全归采样方差。

报告qwen3/results/smurf_swish_20261024/model/REPORT_ZH.md，SUMMARY/RAW_INDEX含三seed、逐层分布、模型/数据/校准/源码SHA。原件project_archives/smurf_model_20261024/sealed-2898-2902.tar.gz，远端与本地SHAf53c05e9e65d50e0a329bddd0c75380f728c48c2ae8c93a9c8e61b0046e60ba8。无本任务运行中作业或新定时，不重交。建议保留三路AND为当前主线：Issue173最佳联合128=15.3647，仍非无损；FSM另需改变表示/拟合或训练。

本人jieruiz，task/175-smurf-swish，目录tmp/smurf-swish-20261024，Issue175/PR176待审未合并；新结果发布以MODEL_PUBLICATION.json为准。Projects缺read:project待同步。恢复先读最新Issue/PR及本交接，原件可按RAW_INDEX恢复，不修改执行快照，不把条件均值当可部署路径。

'''
canonical=BASE/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';mirror=BASE/'PROJECT_MEMORY_ZH.md'
assert canonical.read_bytes()==mirror.read_bytes()
old=canonical.read_text(encoding='utf-8');data=old if old.startswith(note) else note+old
for p in (canonical,mirror,ROOT/'PROJECT_MEMORY_ZH.md'):p.write_bytes(data.encode('utf-8'))
for p in (ROOT/'progress/jieruiz/STATUS.md',ROOT/'work/jieruiz/175/HANDOFF.md'):
    old=p.read_text(encoding='utf-8')
    if not old.startswith(note):p.write_bytes((note+old).encode('utf-8'))
