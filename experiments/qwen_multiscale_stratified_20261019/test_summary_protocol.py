"""Synthetic protocol fixture, not measured PPL: keep strata groups separate.

Added after frozen execution db27fa3 as post-processing validation only.
"""
import ast,hashlib,importlib.util,json,pathlib,tempfile

root=pathlib.Path(__file__).resolve().parent
code=(root/'run_stratified.py').read_text(encoding='utf-8')
tree=ast.parse(code)
function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='cases')
scope={'SEEDS':(0,1,2)}
exec(compile(ast.Module(body=[function],type_ignores=[]),'cases-only','exec'),scope)
cases=scope['cases']()
assert len(cases)==67 and len({c['name'] for c in cases})==67
assert all(c['full'] and c['cycles']%c['strata']==0 and 256%c['strata']==0 for c in cases)
spec=importlib.util.spec_from_file_location('stratified_analyzer_audit',root/'analyze_results.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
chosen=[c for c in cases if c['policy']=='pot2' and c['mode']=='sampled' and c['cycles']==64 and c['strata'] in (1,4)]
assert len(chosen)==6
_temporary=tempfile.TemporaryDirectory(prefix='summary-fixture-',dir=str(root))
scratch=pathlib.Path(_temporary.name)
source=scratch/'originals';source.mkdir();(source/'runs').mkdir()
commit='a'*40
identity={'execution_commit':commit,'model_revision':'m','tokens':{'test':{'ids_sha256':'full_hash'}}}
suite={'code_commit':commit,'executed_phases':['scan'],'scan':chosen}
def write(path,data):
    path.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8')
write(source/'identity.json',identity);write(source/'suite.json',suite)
ready={'baseline_gate_passed':True,'code_commit':commit,'identity_sha256':module.digest(source/'identity.json'),'suite_sha256':module.digest(source/'suite.json')}
write(source/'READY.json',ready)
for full in (True,False):
    cfg={'name':'bf16_full' if full else 'bf16_n512','mode':'baseline','full':full}
    raw={'configuration':cfg,'code_commit':commit,'scored_tokens':299077 if full else 511,'protocol':'full_WT2_sliding_window' if full else 'WT2_fixed_test_prefix','baseline_gate_passed':True,'token_ids_sha256':'full_hash' if full else 'prefix_hash','perplexity':11.,'forward_seconds':1.}
    write(source/'runs'/(cfg['name']+'.json'),raw)
for cfg in chosen:
    raw={'configuration':cfg,'code_commit':commit,'configuration_sha256':module.configuration_hash(cfg),'identity_sha256':ready['identity_sha256'],'model_revision':'m','full_test_token_ids_sha256':'full_hash','token_ids_sha256':'full_hash','scored_tokens':299077,'protocol':'full_WT2_sliding_window','perplexity':12. if cfg['strata']==1 else 11.5,'forward_seconds':2.,'status':'completed'}
    write(source/'runs'/(cfg['name']+'.json'),raw)
status=module.summarize(source,scratch/'summary','/test/originals')
summary=json.loads((scratch/'summary/SUMMARY.json').read_text(encoding='utf-8'))
groups=[g for g in summary['groups'] if g['mode']=='sampled']
assert len(groups)==2 and {g['strata'] for g in groups}=={1,4}
assert all(g['completed']==3 and g['seeds']==[0,1,2] for g in groups)
assert {g['strata']:g['ppl_mean'] for g in groups}=={1:12.,4:11.5}
# Mutated strata under an old run filename is not accepted.
target=source/'runs'/(chosen[0]['name']+'.json')
bad=json.loads(target.read_text(encoding='utf-8'));bad['configuration']['strata']=4;write(target,bad)
try:
    module.summarize(source,scratch/'bad-summary','/test/originals')
except ValueError as exc:
    assert 'Unplanned or changed configuration' in str(exc)
else:
    raise AssertionError('mutated strata accepted')
print(json.dumps({'cases':len(cases),'selected':len(chosen),'separate_K_groups':'PASS','mutated_K_rejected':'PASS','status':status,'scratch':str(scratch)}))
