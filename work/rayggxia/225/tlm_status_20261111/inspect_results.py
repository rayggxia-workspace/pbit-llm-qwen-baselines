"""Read-only remote seal audit and current per-layer progress."""
from pathlib import Path
import hashlib,json,sys
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent/'digital250_20261110'));from ops import remote
code=r'''
from pathlib import Path
import hashlib,json,datetime,statistics,math
base=Path('/public3/home/t6s011227/pbit_chimera_pipeline_20260920');now=datetime.datetime.utcnow()
roots=[base/'tlm28d250_full225_34375c559476',base/'tlm28cross250_225_e0291ed6b5a9']
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
cases=[]
for root in roots:
    mf=json.loads((root/'FROZEN_MANIFEST.json').read_text())
    for n,v in mf['files_sha256'].items():assert sha(root/n)==v,(root,n)
    bsha=sha(root/'250MHz/BINDINGS.json');csha=sha(root/'250MHz/WHOLE_CONFIG.json')
    if 'cross' in root.name:
        items=[dict(c,name='full_'+c['model']+'_'+c['scheme']+'_s'+str(c['seed'])) for c in mf['full']]
    else:items=[dict(name='full_'+s,scheme=s,model='qwen3_4b',seed=17) for s in mf['schemes']]
    for c in items:
        work=root/'work'/c['name'];out=root/'outputs'/c['name'];x=dict(c,remote_root=str(root))
        ex=json.loads((work/'EXIT.json').read_text()) if (work/'EXIT.json').exists() else None
        inv=json.loads((work/'INVOCATION.json').read_text()) if (work/'INVOCATION.json').exists() else None
        x['job_id']=inv.get('job_id') if inv else None
        if ex and ex['exit_code']==0 and (out/'SEAL.json').exists():
            seal=json.loads((out/'SEAL.json').read_text())
            for n,v in seal['files_sha256'].items():assert sha(out/n)==v,(c,n)
            r=json.loads((out/'RESULT.json').read_text());b=json.loads((out/'BUDGET.json').read_text())
            assert r['status']==seal['status']=='completed' and r['scope']=='full'
            assert json.loads((out/'VALIDATION.json').read_text())['status']=='PASS'
            assert r['head_probe_rows'] is None and r['backend']=='native' and r['clock_MHz']==250
            target={'qwen3_4b':36,'llama32_3b':28,'deepseek_7b':30}[c['model']]
            assert r['layers']==target
            stage='NL_Wd' if c['scheme']=='SC_ising' else 'digital_FFN'
            assert {z['layer'] for z in r['phases'] if z['stage']==stage}==set(range(target))
            assert r['bindings_sha256']==bsha
            assert r.get('macro_config_sha256',r.get('macro_sha256'))==csha
            for name,v in r['code_sha256'].items():
                path=root/name if 'cross' in root.name else root/'digital250_20261110'/name
                assert sha(path)==v,name
            assert not b['gross_idle_double_counted']
            assert math.isclose(sum(z['energy_mJ'] for z in b['rows']),b['conditional_subsystem_energy_mJ'],rel_tol=1e-12)
            x.update(status='completed_seal_verified',layers=target,time_ms=r['time_ms'],
                area_mm2=b['conditional_subsystem_area_mm2'],core_mJ=b['conditional_subsystem_energy_mJ'],
                total_mJ_by_pJbit=b['conditional_total_energy_mJ_by_external_pJbit'],
                head_split=b['lm_head_split'],wall_seconds=r['wall_seconds'],
                files_sha256=seal['files_sha256'],seal_sha256=sha(out/'SEAL.json'),
                binding_sha256=bsha,config_sha256=csha,manifest_sha256=sha(root/'FROZEN_MANIFEST.json'),
                exit_finished_UTC=ex.get('finished_UTC'),unpriced=b.get('unpriced_in_chosen_boundary'))
        else:
            rows=[]
            if (work/'run.log').exists():
                for line in (work/'run.log').read_text(errors='replace').splitlines():
                    try:
                        z=json.loads(line)
                        if 'stage' in z and 'wall_seconds' in z:rows.append(z)
                    except ValueError:pass
            body=[z for z in rows if z['stage']=='residual']
            delta=[y['wall_seconds']-z['wall_seconds'] for z,y in zip(body,body[1:])]
            elapsed=None
            if inv:
                stamp=inv['started_UTC'];fmt='%Y-%m-%dT%H:%M:%S.%f' if '.' in stamp else '%Y-%m-%dT%H:%M:%S'
                elapsed=(now-datetime.datetime.strptime(stamp,fmt)).total_seconds()
            x.update(status='failed' if ex else 'running_or_pending',exit_code=ex.get('exit_code') if ex else None,
                complete_layers=len(body),last_progress=rows[-1] if rows else None,
                recent_layer_seconds=delta[-5:],median_layer_seconds=statistics.median(delta[-5:]) if delta else None,
                elapsed_seconds=elapsed,last_body_wall_seconds=body[-1]['wall_seconds'] if body else None)
        cases.append(x)
print(json.dumps(dict(observed_UTC=now.isoformat(),cases=cases)))
'''
x=remote(code,120);(H/'AUDIT_REMOTE.json').write_bytes((json.dumps(x,indent=2)+'\n').encode())
print(json.dumps(dict(observed_UTC=x['observed_UTC'],completed=sum(c['status']=='completed_seal_verified' for c in x['cases']),total=len(x['cases']))))
for c in x['cases']:
    print(json.dumps({k:v for k,v in c.items() if k in ('model','scheme','seed','status','time_ms','area_mm2','core_mJ',
        'complete_layers','last_progress','recent_layer_seconds','median_layer_seconds','elapsed_seconds','last_body_wall_seconds')}))
