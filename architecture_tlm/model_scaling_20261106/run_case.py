"""Immutable Slurm entry and actual-work/byte gate for one pilot configuration."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys

def main():
    p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True);p.add_argument('--index',type=int,required=True)
    p.add_argument('--phase',choices=('pilot','full'),default='pilot');a=p.parse_args();r=a.runtime.resolve()
    manifest=json.loads((r/'EXECUTION_MANIFEST.json').read_bytes())
    for name,entry in manifest['sources'].items():
        assert hashlib.sha256((r/name).read_bytes()).hexdigest()==entry['sha256'],name
    cases=[(model,clock,scheme) for model in ('qwen3_4b','llama32_3b','deepseek_7b') for clock in (100,250)
           for scheme in ('SC_ising','BF16_dense','W8_dense','W8_screen')]
    model,clock,scheme=cases[a.index];out=r/'results'/a.phase/('%02d_%s_%d_%s'%(a.index,model,clock,scheme))
    if out.exists():raise RuntimeError('existing result; inspect receipt, do not overwrite/repeat')
    command=[sys.executable,'-B',str(r/'architecture_tlm/model_scaling_20261106/execution.py'),'--runtime',str(r),
             '--model',model,'--clock',str(clock),'--scheme',scheme,'--layers','1' if a.phase=='pilot' else '0','--native','--out',str(out)]
    if a.phase=='pilot':command+=['--skip-head']
    subprocess.run(command,check=True)
    d=json.loads((out/'RESULT.json').read_bytes());m=d['shape'];L=d['layers_executed'];H,F=m['hidden'],m['ffn']
    by=d['by_kind'];weights=sum(v.get('read_bytes',0) for key,v in by.items() if key in ('digital_weights','GU_weights','down_weights'))
    expected=L*(2*H*((m['q_heads']+2*m['kv_heads'])*128)+2*H*m['q_heads']*128+3*H*F*(2 if scheme=='BF16_dense' else 1))
    if a.phase=='full':expected+=m['vocab']*H*2
    assert weights==expected,('weight bytes',weights,expected)
    for actor in d['Attention']:
        physical=4*m['kv_heads'];active=m['q_heads'];actions=actor['actions']
        assert actor['padded_heads']==physical and actor['useful_heads']==active
        assert actions['completed_groups']==m['kv_heads']
        assert actions['exact_QK_MAC']==physical*(2048 if scheme in ('BF16_dense','W8_dense') else 128)*128
        if scheme=='SC_ising':assert actions['sampler_samples']==active*64
        else:assert actions['PV_MAC']==physical*(128 if scheme=='W8_screen' else 2048)*128
    validation=dict(status='PASS',scope=a.phase,actual_weight_read_bytes=weights,expected_weight_read_bytes=expected,
                    full_model_accuracy=False,clock_MHz=clock,physical_heads=4*m['kv_heads'],useful_heads=m['q_heads'],
                    logical_layers=L,native=d['backend']['backend'],queues_drained=True)
    (out/'WORK_GATE.json').write_bytes((json.dumps(validation,indent=2)+'\n').encode())
    seal=json.loads((out/'SEAL.json').read_bytes());seal['files_sha256']['WORK_GATE.json']=hashlib.sha256((out/'WORK_GATE.json').read_bytes()).hexdigest()
    (out/'SEAL.json').write_bytes((json.dumps(seal,indent=2)+'\n').encode())
    print(json.dumps(validation),flush=True)

if __name__=='__main__':main()
