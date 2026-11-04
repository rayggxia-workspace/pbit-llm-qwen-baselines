"""Task-only Python overlay; never pip-install into the existing Torch venv."""
from pathlib import Path
import hashlib,json,os,subprocess,sys

def main():
    root=Path(sys.argv[1]);env=Path(sys.argv[2]);env.mkdir(exist_ok=False)
    config=json.loads((root/'CONFIG.json').read_bytes());wheels=env/'downloads';wheels.mkdir()
    site=env/'site'
    packages=['flashinfer-python=='+config['flashinfer_version'],'ninja=='+config['ninja_version']]
    subprocess.run([sys.executable,'-m','pip','download','--disable-pip-version-check','--no-cache-dir',
                    '--no-deps','--no-build-isolation','--dest',str(wheels),*packages],check=True)
    source=next(wheels.glob('flashinfer_python-0.2.5.tar.gz'))
    assert hashlib.sha256(source.read_bytes()).hexdigest()=='990aa090ef781783e76b836696ece4efd23956f72b5696d622fc619a61162aef'
    artifacts=[dict(name=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(wheels.iterdir())]
    subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--no-cache-dir',
                    '--no-deps','--no-build-isolation','--target',str(site),*[str(p) for p in sorted(wheels.iterdir())]],check=True)
    os.environ['PYTHONPATH']=str(site)+':'+str(root)+':'+str(root/'dependencies')
    probe="import torch,flashinfer,importlib.metadata as m,json;print(json.dumps(dict(torch=torch.__version__,flashinfer=m.version('flashinfer-python'),ninja=m.version('ninja'))))"
    r=subprocess.check_output([sys.executable,'-B','-c',probe],text=True)
    subprocess.run([sys.executable,'-B','-m','unittest','test_contract','test_meter','-v'],cwd=str(root),check=True)
    receipt=dict(status='completed',python=sys.version,packages=packages,artifacts=artifacts,probe=r,
                 unchanged_existing_Torch=True,new_environment=str(env),GPU_used=False)
    with (env/'INSTALL.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(receipt,f,indent=2);f.write('\n')
    (env/'READY').write_text('PASS\n')

if __name__=='__main__':main()
