"""Install only native inference-layer dependencies, not the training input stack."""
from pathlib import Path
import json,os,subprocess
P=Path('/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019');N=P/'env-native-v4/bin/python';E=P/'env-eval-v4/bin/python'
assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and P.resolve().is_relative_to(Path.home().resolve())
os.environ.update(PIP_CACHE_DIR=str(P/'cache/pip'),TMPDIR=str(P/'tmp'),JAX_PLATFORMS='cpu')
def run(args):print('RUN',' '.join(map(str,args)),flush=True);subprocess.run(list(map(str,args)),check=True)
def save(name,x):(P/'reports'/name).write_text(json.dumps(x,indent=2)+'\n')
try:
 run([N,'-m','pip','install','attrs==24.3.0','prefixed==0.9.0','numpy==1.26.4','absl-py==2.1.0','chex==0.1.88','einops==0.8.0','jax==0.4.38','jaxlib==0.4.38','ml-dtypes==0.4.1','msgpack==1.1.0','optax==0.1.7','flax==0.10.2','orbax-checkpoint==0.11.1','aqtp==0.8.2','scipy==1.12.0','tensorstore==0.1.68','sentencepiece==0.2.0','typing-extensions==4.12.2','pillow'])
 run([N,'-c','import jax; from axlearn.common.attention import SigmoidAttention; from axlearn.common.decoder import Decoder; print(jax.devices()); print("NATIVE_INFERENCE_IMPORT_OK")'])
 (P/'reports/native-freeze-v8.txt').write_text(subprocess.check_output([str(N),'-m','pip','freeze'],text=True))
 save('setup_v8_status.json',{'state':'COMPLETED','job_id':os.environ['SLURM_JOB_ID'],'native_scope':'official Decoder/attention/layers; training-input modules not imported'})
except BaseException as e:
 save('setup_v8_status.json',{'state':'FAILED','job_id':os.environ['SLURM_JOB_ID'],'error':repr(e)});raise
