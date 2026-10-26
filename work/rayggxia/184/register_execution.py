"""Central indexes and handoff for existing-data exports and actual new Slurm run."""
from pathlib import Path
import csv,hashlib,json
ROOT=Path(__file__).resolve().parents[5]
TASK=ROOT/'tmp/normal-readout-issue184-20261025';WORK=Path(__file__).resolve().parent
FORMAL=TASK/'architecture_tlm/physical_rng_normal_readout';SRC=FORMAL/'src'
DATA=ROOT/'analog_pbit_20261016/ideal_and_old_20000_v1'
obs=json.loads((WORK/'OBSERVATION_38387635_2.json').read_text(encoding='utf-8'))
sub=json.loads((WORK/'SUBMISSION_20261025.json').read_text(encoding='utf-8'))
export=json.loads((DATA/'SUMMARY.json').read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def artifact(p,role):
    a=dict(path=str(p),role=role,present_at_registration=True,required=True,bytes=p.stat().st_size,sha256=sha(p))
    if p.is_relative_to(TASK):a['repository_path']=p.relative_to(TASK).as_posix()
    return a
stages=dict(functional='running_physical_checks_recorded_statistics_pending',synthesis='not_run',sta='not_run',power='not_run',postlayout='not_run')
base=dict(schema_version=1,registered_on='2026-10-25',owner='rayggxia',issue=184,evidence_level='PARTIAL_FLOW')
derived=dict(base,id='physical-rng-184-existing-20000-export',name='38380128已有波形每seed20000次理想/旧比较器导出（非新仿真）',family='RNG派生样本',
    status='derived_existing_run_export_complete_no_new_simulation',stages=dict(stages,functional='existing_waveform_export_only'),
    boundary='同一38380128既有三条20ms/500Hz真实波形派生，固定1us各20000次。理想0.6V为软件判决，旧比较器MID保留。不得将这60000次派生样本计作新物理实验。',
    conditions=dict(source_job=38380128,new_simulation=False,seeds=[32003,32009,32027],samples_per_seed=20000,interval_s=1e-6,
        start_s=.002,effective_s=.02,noisefmin_Hz=500,noisefmax_Hz=1e8,maxstep_s=2.5e-9,corner='TT',temperature_C=25,
        core_V=1.2,old_comparator_V=.8,old_midrail_counts=[1089,1145,1115],ideal_P1=[.50175,.508,.4959]),
    source=dict(repository='rayggxia-workspace/pbit-llm-qwen-baselines',source_simulation_commit=export['source_simulation_commit'],
        source_manifest_sha256=export['source_manifest_sha256'],source_archive_sha256=export['source_archive_sha256'],
        actual_export_code_sha256=export['export_code_sha256'],portable_export_source_commit=sub['source_commit'],
        model_tokenizer_dataset='N/A analog-waveform export'),
    artifacts=[artifact(DATA/name,'existing_waveform_derived_data') for name in json.loads((DATA/'manifest.json').read_text(encoding='utf-8'))]+[
        artifact(DATA/'manifest.json','derived_file_manifest'),artifact(WORK/'export_existing_executed.py','exact_executed_export_script'),
        artifact(Path(export['source_archive']),'original_parent_archive_not_new_run')],cases=[],
    limitations=['No new Spectre execution; originalrun38380128 is indexed separately.',
        'Ideal readout is not an implemented comparator or completelybare core; the original source was loaded by the old comparator.',
        'Old thresholdbits includeMID; ideal/thresholdbit traces do not certify entropy,IID,10Hz drift or electrical validity.'],
    next_action='Use CSV/TXT for exploratory source/architecture statistics; compare against the separately submitted conventional comparator job38387635.')
normal=dict(base,id='physical-rng-normal-38387635',name='常规偏置10MOS比较器38387635（运行中）',family='RNG模拟通道Spectre',
    status='submitted_running_physics_screened_noise_statistics_pending',stages=stages,
    boundary='原两MOS核心＋常规偏置10MOS比较器＋5fF输出。3候选通过工作点/阶跃，SVT20u尾管饱和裕量不足被拒；后续短精度/独立校准/3新seed各20000次仍待结果。',
    conditions=dict(job_id=38387635,partition='v6_384',allocated_CPUs=8,workers=8,threads_per_case=1,solver='APS',memory_GB=16,
        compute_budget_h=6,wall_limit_s=22500,node_nm=55,corner='TT',temperature_C=25,core_V=1.2,comparator_V=1.2,load_fF=5,
        noisefmin_Hz=500,noisefmax_Hz=1e8,maxstep_s=2.5e-9,noisescale=1,validation_seeds=[64007,64013,64033],
        calibration_seeds=[62003,62009,62017],numeric_seeds=[63003,63017,63029],planned_validation_samples=20000,sample_interval_s=1e-6,
        observed_utc=obs['observed_utc'],observed_slurm_state='RUNNING',spectre=obs['spectre_version'].strip(),python='3.6.8',
        remote_tests=8,remote_PDK_hashes=27,selected_by_deterministic_policy='lvt_i20u',
        selected_input_overdrive_V=[.189927,.19334],selected_input_gmoverid=[11.9829,11.8637],
        loaded_1mV_step_maximum_delay_s=3.5e-9,loaded_10mV_step_maximum_delay_s=1.5e-9,
        rejected_svt20u_tail_saturation_margin_V=-.0126162),
    source=dict(repository='rayggxia-workspace/pbit-llm-qwen-baselines',git_commit=sub['source_commit'],
        source_manifest_sha256=sub['source_manifest_sha256'],config_sha256=sub['config_sha256'],
        remote_execution_snapshot='/public3/home/t6s011227/analog_pbit_20261016/normal_readout_v1/submissions/normal-JMJc0ox0/source',
        command='STUDY_PYTHON=/usr/bin/python3 NORMAL_SOURCE_COMMIT='+sub['source_commit']+' bash submit.sh',
        publication='Local exactcode commit; API publication equivalent recorded separately when successful',model_tokenizer_dataset='N/A analog-circuit study'),
    artifacts=[artifact(WORK/name,role) for name,role in [('SUBMISSION_20261025.json','submission_receipt'),('submission_stdout.txt','actual_submission_stdout'),
        ('submission_stderr.txt','actual_remote_8test_preflight'),('OBSERVATION_38387635_1.json','initial_running_observation'),('OBSERVATION_38387635_2.json','running_physical_check_observation')]]+[
        artifact(SRC/'package_manifest.json','executed_source_manifest'),artifact(SRC/'config.json','executed_config'),artifact(FORMAL/'results/LOCAL_VALIDATION.json','local_script_validation')],
    cases=[dict(case=r['case'],status=r['status'],elapsed_s=r['elapsed_s'],check_error=r['error'],complete=True,
        step_max_delay_s=r.get('step',{}).get('maximum_delay_s')) for r in obs['cases']],
    limitations=['RUNNING observation; no completed numerical/independent calibration/heldout20k-record acceptance yet.',
        'Onecandidate physicalfailure retained; selected comparator alone proceeds. Nonzero stage failures do not mean Spectre syntax errors.',
        'Nanosecond noiseless overdrive step is not independentbit rate; load/reference/source coupling,noise andMID require actualstatistics.',
        'No10Hz/1s drift,gatedsharedMUX,latch,PEX,entropy certification or precise dynamic-power integration.'],
    next_action='Inspect existing38387635; do not resubmit healthy job. Verify finalarchive SHA, numeric screen,frozenreference and each heldout20000sample record before architecture use.')
for task in [TASK,ROOT]:
    reg=task/'digital_circuit_simulation_registry'
    catalog=json.loads((reg/'catalog.json').read_text(encoding='utf-8'))
    for record in [derived,normal]:
        p=reg/'records'/(record['id']+'.json');assert not p.exists();save(p,record)
        assert record['id'] not in catalog['record_ids'];catalog['record_ids'].append(record['id'])
    catalog['as_of']='2026-10-25';save(reg/'catalog.json',catalog)
    inventory=reg/'archive_inventory.csv'
    with inventory.open(encoding='utf-8',newline='') as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
    if not any(r['path']==export['source_archive'] for r in rows):
        p=Path(export['source_archive']);rows.append(dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p),linked_records=derived['id'],review_state='existing_parent_verified_not_new_run',note='复用Issue152已完成原包；导出不计新物理实验'))
        with inventory.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
note=('2026-10-25新Issue184由本轮已核实rayggxia负责，独立task/184-normal-readout@d6d33995，tmp/normal-readout-issue184-20261025，不接管152/jieruiz旧任务。'
      '已把38380128三seed各20000次1us理想/旧比较器逐位CSV及单列TXT导出到analog_pbit_20261016/ideal_and_old_20000_v1，11文件SHA通过；'
      '旧MID分别1089/1145/1115，全部保留。真实源原本接旧比较器，理想判决不是完全裸核心或实际数字读出，500Hz短记录不证明IID/慢漂移。'
      '新normal_readout_v1复用未实测10MOS无输出限流拓扑，1.2V、SVT/LVT输入、10/20uA，输入反型及饱和裕量实测门禁；'
      '源01d63b66aa5653dffb4d116e1b1d5f9c951b1571，manifest743bbec6b48ee440773623698c5de423d21756ad721edc4ee1411b7082d8ec82；'
      '24文件逐个SFTP上传，无新源码压缩包，8本地/8远端测试、17Python3.6 AST、Bash和27PDK哈希通过。'
      '实际Slurm38387635已RUNNING，m3ca1003，03:54:35Z观察；8CPU16GB、APS1最多8案例、6h+15m，snapshot normal-JMJc0ox0/source不可改。'
      '4候选中SVT20u尾管VDS-VDSAT=-12.6162mV拒绝，另3正常；确定性策略选LVT20u，输入overdrive189.9/193.3mV、gm/Id11.98/11.86；'
      '1mV连接核心阶跃最坏3.5ns、10mV1.5ns，采样分辨0.5ns；不等于独立随机位率。短精度、独立cal62003/9/17冻结及新val64007/13/33每条22ms总/20ms有效/1us/2万位仍待执行结果，'
      'numeric63003/17/29与cal/val分离，fmin500Hz，本轮不自动1s/10Hz长任务或精确能耗。结果根/public3/home/t6s011227/analog_pbit_20261016/normal_readout_v1/results/38387635，'
      '结束自动normal_readout_38387635.tar.gz/.sha256。台账新增派生索引（cases空、不算新实验）与真实新run，拒绝项保留。PR实际发布以work/rayggxia/184/PUBLICATION.json为准，不虚报合并。')
canonical=ROOT/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';mirror=ROOT/'PROJECT_MEMORY_ZH.md';assert canonical.read_bytes()==mirror.read_bytes()
for path in [canonical,TASK/'PROJECT_MEMORY_ZH.md']:
    text=path.read_text(encoding='utf-8');mark='## 6 随机源、p-bit与相关性\n';assert mark in text
    path.write_text(text.replace(mark,mark+'\n'+note+'\n',1),encoding='utf-8',newline='\n')
mirror.write_bytes(canonical.read_bytes())
status=TASK/'progress/rayggxia/STATUS.md';status.write_text('# Issue184 常规比较器已实际运行 / 2026-10-25\n\n'+note+'\n\n'+status.read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
handoff=WORK/'HANDOFF.md'
with handoff.open('a',encoding='utf-8',newline='\n') as f:f.write('\n实际执行回执：'+note+'\n')
index=ROOT/'analog_pbit_20261016/实验记录与清理索引_20261018.txt';text=index.read_text(encoding='utf-8');head,rest=text.split('\n',1)
index.write_text(head+'\n\n'+note+'\n'+rest,encoding='utf-8',newline='\n')
save(ROOT/'analog_pbit_20261016/normal_readout_v1_delivery.json',dict(issue=184,owner='rayggxia',source_commit=sub['source_commit'],
    local_upload=str(ROOT/'远端上传/normal_readout_v1'),export_directory=str(DATA),source_manifest_sha256=sub['source_manifest_sha256'],
    job=38387635,status_at_observation='RUNNING',observed_utc=obs['observed_utc'],remote_results=obs['remote_results'],
    actual_20k_new_comparator_results_complete=False,registry_ids=[derived['id'],normal['id']],publication='Pending actual API receipt'))
save(WORK/'REGISTRATION_RECEIPT.json',dict(ids=[derived['id'],normal['id']],new_physical_run=38387635,derived_source_run=38380128,
    export_files=11,new_source_files=24,raw_exports_uploaded_to_Git=False,selected_candidate='lvt_i20u',last_observed_utc=obs['observed_utc']))
print('Registered existing-data export separately from one actual new Slurm run')
