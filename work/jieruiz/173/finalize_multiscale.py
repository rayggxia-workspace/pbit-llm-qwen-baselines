import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HOME=ROOT.parents[1];OUT=ROOT/'work/jieruiz/173'
ARCHIVE=HOME/'project_archives/qwen3_and_direct_20261024'
def save(path,obj):path.write_bytes((json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode())
package=json.loads((OUT/'MULTISCALE_PACKAGE.json').read_bytes())
source=Path(package['path']);target=ARCHIVE/source.name
assert source.parent.resolve()==OUT.resolve() and target.parent.resolve()==ARCHIVE.resolve()
if source.exists():
    assert hashlib.sha256(source.read_bytes()).hexdigest()==package['sha256']
    if target.exists():assert target.read_bytes()==source.read_bytes()
    else:shutil.copyfile(source,target)
    assert hashlib.sha256(target.read_bytes()).hexdigest()==package['sha256'];source.unlink()
save(ARCHIVE/'MULTISCALE_RECOVERY.json',dict(source_archive=str(target),source_sha256=package['sha256'],
    results_archive=str(ARCHIVE/'multiscale-sealed-2886.tar.gz'),
    results_sha256='9d7fbc40697ebbd6e4a80194778308784e6b2b803864438fbbd5b34675935b4b',
    execution=package['commit'],issue=173,pr=174,branch='task/173-and-direct-wd'))
save(OUT/'MULTISCALE_SUBMISSION.json',dict(job_array=2886,shards=list(range(5)),execution_commit=package['commit'],
    root='/home/Hongjie_Zeng/projects/pbit-qwen3-and-multiscale-20261024-issue173',snapshot='snapshot-8249fad6',
    package_sha256=package['sha256'],server_preflight_tests_per_shard=18,
    status='five completed JSON verified',physical_scored_results=45,unique_scored_configs=41,
    local_new_tests='5 passed, 1 CUDA deferred; all18 tests passed on server',
    scheduler_accounting='disabled; use sealed complete JSON/logs, not fabricated sacct'))
entry='''## Issue173多档g/u直连Wd完成（2026-10-24）

用户提出幅度多档与输出移位对齐。已接续PR174实现，冻结8249fad60203679f6fc51f0661aaaac2889c86f1，Slurm2886五片完成；每片18项功能（含CUDA整数对照）通过。45份封存计分/41唯一配置、36层全前缀与SHA核验通过；无训练/RTL/PPA。Qwen3-4B后训练，准确Attention，8×128目标后缀；BF16五次一致13.566049，旧z重编码三seed及B1均值与前轮完全一致。

g/u每64通道的TRAIN固定S不变，通道选择固定档位：B2=[S,S/64]，B4=[S,S4,S16,S64的除法档]，B8=[S,S/2,...,S/128]，无在线absmax。三seedPPL：B2 T64/256=2482468.68/2294.6095；B4 T64/256/1024=42.34168/14.46628/13.71393；B8=15.97791/13.90611/13.46984。均值对照B1/2/4/8=13.49820/13.45553/13.44746/13.43162。B8同时增加密度与低端覆盖，不把收益全归档数；不是完整WT2，不据略低于BF16声称能力提高。

首层x/g/u RMS=0.115725/0.211005/0.178412：g/u确实较x大，但相对量程占空比仍低。平均AND概率B1/B4/B8=.0009104/.123414/.227285。sigma必须按真实g驱动：幅度8+符号+指数经整数移位/RNE/饱和转signed8 field，再P8 LUT+独立比较器；不是sigma(g/Sg)。Wd同局部scale域的乘积指数合并B4为7类、B8为15类；先同指数归约再对齐，64倍=6位，双边64倍=12位。无z恢复/重采样；16位scale系数沿用，signed64容器/实际上界检查。gate/up恢复仍FP32参考，未完成全FFN bittrue或TLM/PPA接入。

报告qwen3/results/and_direct_20261024/multiscale/REPORT_ZH.md；方法与一手文献qwen3/and_direct/MULTISCALE_ZH.md。原件project_archives/qwen3_and_direct_20261024/multiscale-sealed-2886.tar.gz，SHA9d7fbc40697ebbd6e4a80194778308784e6b2b803864438fbbd5b34675935b4b；MULTISCALE_RECOVERY.json恢复源码包。负责人jieruiz/task/173-and-direct-wd，沿用tmp/qwen3-and-direct-issue173-20261024，PR174待审未合并。无定时、勿重交；Projects未同步。最终发布见MULTISCALE_PUBLICATION.json。

'''.replace('B4=[S,S4,S16,S64的除法档]','B4=[S,S/4,S/16,S/64]')
for path in (ROOT/'PROJECT_MEMORY_ZH.md',ROOT/'progress/jieruiz/STATUS.md',OUT/'HANDOFF.md'):
    text=path.read_text(encoding='utf-8')
    if not text.startswith(entry):path.write_bytes((entry+text).encode())
canonical=HOME/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';mirror=HOME/'PROJECT_MEMORY_ZH.md'
assert canonical.read_bytes()==mirror.read_bytes()
text=canonical.read_text(encoding='utf-8')
if not text.startswith(entry):
    b=(entry+text).encode();canonical.write_bytes(b);mirror.write_bytes(b)
print('Multiscale archive and recovery, same-byte memory, handoff updated')
