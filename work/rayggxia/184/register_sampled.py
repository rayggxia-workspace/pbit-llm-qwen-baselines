"""Register the actual timed-readout job without touching prior run records."""
import hashlib,json
from pathlib import Path
TASK=Path(__file__).resolve().parents[3];ROOT=TASK.parents[1];WORK=Path(__file__).resolve().parent
FORMAL=TASK/'architecture_tlm/physical_rng_sampled_readout';SRC=FORMAL/'src'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def artifact(p,role):
    a=dict(path=str(p),role=role,present_at_registration=True,required=True,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    if TASK in p.parents:a['repository_path']=p.relative_to(TASK).as_posix()
    return a
s=load(WORK/'SUBMISSION_SAMPLED_20261025.json');obs=load(WORK/'OBSERVATION_SAMPLED_38398237_1.json')
assert s['job']==38398237 and obs['pdk_comparison.json']['matches']
assert len(obs['cases'])==16 and all(r['status']=='COMPLETED_REVIEW_REQUIRED' for r in obs['cases'])
record=dict(schema_version=1,registered_on='2026-10-25',owner='rayggxia',issue=184,id='physical-rng-sampled-38398237',
    evidence_level='PARTIAL_FLOW',name='真实MOS定时采样38398237（16确定性案例通过，噪声验证运行中）',family='RNG模拟通道Spectre',
    status='submitted_running_deterministic_timed_readout_pass',stages=dict(functional='deterministic16_pass_noise_statistics_running',synthesis='not_run',sta='not_run',power='not_run',postlayout='not_run'),
    boundary='单通道2MOS零外加C核心＋10MOS已验证常规比较器＋13MOS真实传输门/再生保持锁存＋5fF。理想时钟/复位激励，无具体阵列或选行/MUX。',
    conditions=dict(job_id=38398237,observed_utc=obs['observed_utc'],observed_slurm_state='RUNNING',allocated_CPUs=8,workers=8,threads_per_case=1,solver='APS',memory_GB=16,compute_budget_h=6,walltime='06:15:00',
        node_nm=55,corner='TT',temperature_C=25,vdd_V=1.2,comparator_bias_A=20e-6,comparator_and_Q_load_fF=5,
        period_s=1e-6,track_s=1e-7,read_delay_after_close_s=5e-8,nonoverlap_s=2e-9,clock_edge_s=1e-9,
        clock_drivers='ideal finite-edge testbench voltage sources; clocktree energy/area excluded',reference_V=.604745,parent_reference_sha256='c9d2358bf5f400c9d4c40059d29a6210ce47bde61e7c60fb6b0dd2a3d3c8c8fe',
        noisefmin_Hz=500,noisefmax_Hz=1e8,maxstep_s=2.5e-9,save_strobe_s=5e-8,noisescale=1,
        numeric_seeds=[66007,66013,66029],validation_seeds=[68003,68011,68023],planned_validation_samples_per_seed=20000,
        read_times_s='2ms+k*1us for k0..19999; capture closes50ns earlier',reference_policy='Frozen38387635 independentcalibration; no retuning with new validation seeds',
        local_tests=10,remote_tests=10,Python36_AST=17,bash_syntax=2,PDK_hashes_matched=27,
        first_actual_deterministic_case_count=16,first_deterministic_invalid_Q=0,first_deterministic_hold_bad=0,
        numerical_and_full_noisy_statistics='not_complete'),
    source=dict(repository='rayggxia-workspace/pbit-llm-qwen-baselines',git_commit=s['source_commit'],source_manifest_sha256=s['source_manifest_sha256'],config_sha256=s['config_sha256'],
        remote_execution_snapshot='/public3/home/t6s011227/analog_pbit_20261016/sampled_readout_v1/submissions/sampled-vWv3v20y/source',remote_result_root=obs['remote_results'],
        command='STUDY_PYTHON=/usr/bin/python3 SAMPLED_SOURCE_COMMIT='+s['source_commit']+' bash submit.sh',model_tokenizer_dataset='N/A realMOS circuit study',publication='PR185 increment; actual publication receipt will record equivalent API tree'),
    artifacts=[artifact(WORK/n,role) for n,role in [('SUBMISSION_SAMPLED_20261025.json','actual_submission_receipt'),('sampled_submission_stdout.txt','submission_stdout'),('sampled_submission_stderr.txt','remote10test_preflight'),('sampled_queue_before_submission.txt','queue_before_submission'),('OBSERVATION_SAMPLED_38398237_1.json','actual16case_running_observation')]]+
        [artifact(SRC/'package_manifest.json','executed_source_manifest'),artifact(SRC/'config.json','executed_config'),artifact(SRC/'parent_reference.json','original_frozen_reference_bytes'),artifact(FORMAL/'results/LOCAL_VALIDATION.json','local_checks')],
    cases=[dict(case=r['case'],status=r['status'],complete=True,elapsed_s=r['elapsed_s'],metrics=r['metrics'],kind=r['kind']) for r in obs['cases']],
    limitations=['RUNNING; three fresh20000sample sequences not yet complete. No independence/entropy qualification.',
        'Only single-channel timedQ/Qbar; external clocks/reset/bias/reference ideal, no array/MUX/SRAM/clocktree/PEX/PVT.',
        'Near-edge sweep and50ns resolution do not prove a bound on rare metastability failures.',
        'CaptureMID retained; no Q-invalid filtering allowed to claim a qualified hardware stream. VN/packets are offline diagnostics.',
        'No new reference calibration, dynamic-power integration or1s/10Hz drift task. Shortscreen must pass before costly long run.'],
    next_action='Inspect existing38398237 short noise screen and measured cost; no duplicate submission or mutation of source. Then review3fresh20k timedQ records and automatically packed archive SHA.')
for base in (TASK,ROOT):
    reg=base/'digital_circuit_simulation_registry';path=reg/'records'/(record['id']+'.json');assert not path.exists();save(path,record)
    p=reg/'catalog.json';catalog=load(p);assert record['id'] not in catalog['record_ids'];catalog['record_ids'].append(record['id']);catalog['as_of']='2026-10-25';save(p,catalog)
note=('2026-10-25用户授权下一轮只做到真实比较器定时采样，不展开阵列；接续Issue184/PR185及现有目录，不新建全量checkout。'
      '新增physical_rng_sampled_readout/src、远端sampled_readout_v1；原38387635/normal_readout_v1不改。2MOS核心＋10MOS连续LVT20u比较器＋13MOS真实传输门/再生保持锁存，共25MOS；外部理想有限边沿两相时钟和复位，不计时钟树/阵列。'
      '1us一读：读点t，track从t-150ns到t-50ns，关闭后2ns闭反馈，再生到t；保存点检查保持到t+800ns。Vref沿独立冻结.604745V，不按新验证seed重调；captureMID保留，由实际Q/Qbar电平判读，禁止模拟oracle筛掉Q坏点。'
      '源be26000c2c401befa13eb7b2b1bde2e11e52a9e2、manifest9df7309709ebe6748479b0c66b19756c6198247508b544c503983d57a8f5ca27、配置1e8cfceefafd6293a3e76a2241a44ad0777fa1096e7f13bb73a0186fc7882a1e；25文件逐个SFTP已传。'
      '本地/远端各10检查、17Python3.6 AST、2Bash、27PDK哈希通过。Slurm38398237已RUNNING，8CPU16GB、最多8个APS1案例、6h计算＋15min收集；source snapshot sampled-vWv3v20y/source不可改。'
      +obs['observed_utc']+'首查16真实确定性案例（2通道阶跃＋14锁存边界）全通过，读点无无效Q、保持保存点无变化；含近边沿captureMID仍在50ns后得到有效Q，但不等于罕见亚稳态认证。'
      '当前新numeric66007/13/29短精度/成本检查运行，过门后才用68003/11/23各20000次1us、2ms固定启动。TT25C/500Hz/100MHz/2.5ns，保存50ns不替代内部演化；正式统计未完成。'
      '结果/public3/home/t6s011227/analog_pbit_20261016/sampled_readout_v1/results/38398237，结束自动sampled_readout_38398237.tar.gz/.sha256。中央新增同一run，不把脚本/16短案例当正式60000随机位或PPA。发布以PUBLICATION_SAMPLED.json为准，Issue/PR未关闭合并。')
canonical=ROOT/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';mirror=ROOT/'PROJECT_MEMORY_ZH.md';assert canonical.read_bytes()==mirror.read_bytes()
for p in (canonical,TASK/'PROJECT_MEMORY_ZH.md'):
    t=p.read_text(encoding='utf-8');mark='## 6 随机源、p-bit与相关性\n';assert mark in t and note not in t
    p.write_text(t.replace(mark,mark+'\n'+note+'\n',1),encoding='utf-8',newline='\n')
mirror.write_bytes(canonical.read_bytes())
for p in (WORK/'HANDOFF.md',TASK/'progress/rayggxia/STATUS.md'):
    with p.open('a',encoding='utf-8',newline='\n') as f:f.write('\n'+note+'\n')
save(ROOT/'analog_pbit_20261016/sampled_readout_v1_delivery.json',dict(issue=184,job=38398237,observed_utc=obs['observed_utc'],status='RUNNING',source_commit=s['source_commit'],source_manifest_sha256=s['source_manifest_sha256'],local_upload=str(ROOT/'远端上传/sampled_readout_v1'),remote_root=s['remote_root'],first_deterministic16_pass=True,full_noisy_statistics_complete=False))
print('One actual sampled-channel run registered; prior records retained.')
