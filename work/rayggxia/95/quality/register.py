"""Register this diagnostic run; preserve other records and frozen artifacts."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from digital_circuit_simulation_registry import registry
R=ROOT/'architecture_tlm/random_service/quality/results/20261023'
summary=json.loads((R/'SUMMARY.json').read_text(encoding='utf-8'))
archive=json.loads((R/'ARCHIVE_INDEX.json').read_text(encoding='utf-8'))
def artifact(path,role,repo=None):
    p=Path(path)
    a=dict(path=str(p),role=role,required=True,present_at_registration=True,
           sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
    if repo:a['repository_path']=repo
    return a
arts=[artifact(R/name,'summary',str((R/name).relative_to(ROOT)).replace('\\','/')) for name in
      ('SUMMARY.json','SOURCE_MANIFEST.json','CONFIG.json','AUDIT.json','PHYSICAL_INPUT.json','STAGES.json','ARCHIVE_INDEX.json')]
arts.append(artifact(archive['full_results']['path'],'full_diagnostic_results'))
record=dict(schema_version=1,id='rng-quality-95-20261023',name='分层随机质量：物理轨迹回放与三数字后端',
 family='RNG质量诊断',registered_on='2026-10-23',owner='rayggxia',issue=95,evidence_level='DESIGN_PROOF',
 status='diagnostic_completed_not_quality_certified',
 stages=dict(functional='pass',synthesis='not_run',sta='not_run',power='not_run',postlayout='not_run'),
 boundary='189案例×2端点×4096帧，9条已有Spectre波形回放；直通/VN候选、LFSR/GF64/Bivium、种子分发及局部合成计算探针。无新RTL/EDA/LLM。',
 conditions=dict(node_nm=None,corner='physical input TT only; digital functional model no PVT',
 voltage_V=None,temperature_C=25,clock_MHz=100,physical_sample_us=.5,seeds=[401,503,607],
 reseed_cycles=[0,1024],frames_per_endpoint=4096,qualified_word_interval_cycles=1,
 source_timing='pre-collected replay, not measured physical throughput',sdf=False,spef=False,cts=False),
 source=dict(git_commit=None,local_execution_commit='8a862a38cf6e4e46f50e719f8b2b3877db745c75',
 base_git_commit='6966739a5223680888bf0315f7bb4f73423a1ae6',
 source_manifest_sha256=summary['source_manifest_sha256'],config_sha256=summary['config_sha256'],
 binding='8 exact files in SOURCE_MANIFEST; local execution commit retained; postprocessing audit/report are later additions'),
 artifacts=arts,cases=[dict(case_id=c['case_id'],backend=c['backend'],source=c['source'],seed=c['seed'],
    conditioner=c['conditioner'],reseed_cycles=c['reseed_cycles'],diagnostic_status=c['status'],
    power_W=None,area_um2=None,output_p1=c.get('p1'),rho1=c.get('rho1')) for c in summary['cases']],
 limitations=['不是NIST熵认证、独立性证明、完整FFN/Attention或LLM质量验收。',
 '三电路分别仿真，不是同一噪声逐级因果记录，缺同时多路空间相关数据。',
 'VN仅候选算法；健康检测/调理/CDC未新增RTL。1024拍加速测试不代表量产换种设定。',
 '门级/综合/STA/PT/后布局均未新运行；所有PPA未知。',
 '原始NPZ路径/SHA见SUMMARY，保留在project_archives；远端读者需本机/共享访问。'],
 next_action='更多epoch/长流、多路物理同时采样及PVT；按消费者联合相关要求验证后再选调理与换种策略。')
dest=ROOT/'work/rayggxia/95/quality/RECORD.json'
dest.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
registry.add(dest)
print(json.dumps(registry.check(),ensure_ascii=False))
