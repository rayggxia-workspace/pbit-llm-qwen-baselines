from pathlib import Path
import json,sys
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent/'digital250_20261110'));from ops import remote
code=r'''
from pathlib import Path
import json,datetime
base=Path('/public3/home/t6s011227/pbit_chimera_pipeline_20260920')
targets=[('tlm28cross250_225_e0291ed6b5a9','full_deepseek_7b_SC_ising_s503'),
    ('tlm28cross250_225_e0291ed6b5a9','full_deepseek_7b_SC_ising_s1009'),
    ('tlm28cross250_225_e0291ed6b5a9','full_llama32_3b_BF16_dense_s17'),
    ('tlm28d250_full225_34375c559476','full_BF16_dense')]
out=[]
for root,name in targets:
    rows=[]
    for line in (base/root/'work'/name/'run.log').read_text(errors='replace').splitlines():
        try:
            z=json.loads(line)
            if z.get('stage') in ('final_norm','lm_head'):rows.append(z)
        except ValueError:pass
    out.append(dict(name=name,phases=rows))
print(json.dumps(dict(observed_UTC=datetime.datetime.utcnow().isoformat(),cases=out)))
'''
x=remote(code);(H/'HEAD_RUNTIME.json').write_bytes((json.dumps(x,indent=2)+'\n').encode());print(json.dumps(x))
