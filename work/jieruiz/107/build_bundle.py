"""Portable source-only PPA package. Excludes tools, libs, netlists and large traces."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[3]
APP=ROOT/'architecture_tlm/digital_ppa_v1'
TARGET=Path('C:/Users/86134/Documents/a_P_BIT/digital_ppa_v1_20261022.zip')


def main():
    assert not TARGET.exists(),'never overwrite a delivered bundle'
    val=json.loads((APP/'results/RTL_VALIDATION.json').read_text(encoding='utf-8'))
    assert val['passed'] and len(val['results'])==66 and len(val['power_activity'])==63
    source=val['git_head']
    for rel,want in val['source_sha256'].items():
        raw=(ROOT/rel).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==want,rel
        assert subprocess.check_output(['git','show',source+':'+rel],cwd=ROOT)==raw,rel
    files={}
    for p in APP.rglob('*'):
        if p.is_file() and p.suffix in ('.sv','.svh','.py','.tcl','.md','.csv','.json') and '__pycache__' not in p.parts:
            files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
    for p in (ROOT/'format_conversion_rtl_20261016/rtl').glob('*.sv'):
        files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
    rel='format_conversion_rtl_20261016/sim/reference.py';files[rel]=(ROOT/rel).read_bytes()
    files['LICENSE']=(ROOT/'LICENSE').read_bytes()
    files['README_BUNDLE_ZH.md']=('''# 非随机数字模块RTL与PPA任务包

从architecture_tlm/digital_ppa_v1/README_ZH.md和PPA_TASK_ZH.md开始。保留目录结构。综合使用该目录rtl/与format_conversion_rtl_20261016/rtl/，并将前者加入include路径。测试和Python不进入综合；本包没有PRNG/p-bit阵列/工艺库/工具/模型权重。

Python RTL验证可在本目录运行，安装Git命令和Icarus；不需要Git仓库，仓库外git_head为null，以本manifest和验证源码版本为准。RTL_VALIDATION记录原执行版本、全部source SHA、66组功能/12870笔输出核对及63组活动预检。原周期审计的52个Git原件不复制到包里，周期表/报告已附；重新运行cycle_audit.py需要正式仓库及指定原件对象。

没有用户工艺DC/PT/STA、芯片功耗或新模型PPL。组合路径一拍的行为仿真不证明100MHz可达。KIND7/9/11/12/13含候选近似非线性，KIND22改变融合舍入，质量需另验证。MEMORY小测试的规模/波形不代表16GB/s整机调度。
''').encode('utf-8')
    manifest=dict(source_commit=source,packaging_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
                  scope='validated source-only modules and small reports; no EDA/IP/large data',
                  files=[dict(path=p,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for p,raw in sorted(files.items())])
    files['BUNDLE_MANIFEST.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    with zipfile.ZipFile(TARGET,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p,raw in sorted(files.items()):z.writestr(p,raw)
    with zipfile.ZipFile(TARGET) as z:
        for p,raw in files.items():assert z.read(p)==raw
    receipt=dict(path=str(TARGET),bytes=TARGET.stat().st_size,sha256=hashlib.sha256(TARGET.read_bytes()).hexdigest(),source_commit=source,members=len(files),verified_each_member=True)
    (Path(__file__).resolve().parent/'BUNDLE.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':main()
