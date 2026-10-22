"""Audit archived full-model integration cases, never infer completion."""
import collections,hashlib,json,math,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'architecture_tlm/unified_v6/results/integrated_rng_20261022_v3'
N=collections.Counter();fail=[]
def check(group,ok,detail):
 N[group]+=1
 if not ok:fail.append(dict(group=group,detail=detail))
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
 s=read(OUT/'SUMMARY.json');plan=read(OUT/'PLAN.json');ex=read(OUT/'EXECUTION.json')
 check('completion',s['complete'] and not s['failures'] and len(s['rows'])==plan['case_count'],'complete full planned cases')
 for name,meta in read(OUT/'ARTIFACT_MANIFEST.json').items():
  p=OUT/name;check('artifact_bytes',p.stat().st_size==meta['bytes'] and sha(p.read_bytes())==meta['sha256'],name)
 for name,meta in ex['files'].items():
  b=subprocess.check_output(['git','show',ex['commit']+':'+name],cwd=ROOT)
  check('execution_bytes',len(b)==meta['bytes'] and sha(b)==meta['sha256'],name)
 helper='work/jieruiz/96/integrated/run_targeted.py'
 helper_sha=sha(subprocess.check_output(['git','show',ex['commit']+':'+helper],cwd=ROOT))
 cases={};comparisons=[]
 for row in s['rows']:
  r=read(OUT/row['path']);c=r['config'];model=r['model'];q=r['random_interface'];ident=row['path']
  check('result_bytes',sha((OUT/ident).read_bytes())==row['sha256'],ident)
  check('provenance',r['execution_commit']==ex['commit'] and sha(json.dumps(c,sort_keys=True,separators=(',',':')).encode())==r['config_sha256'],ident)
  for phase in ['attention_norm','QKV_projection','attention_core','O_projection','FFN_gate_up','FFN_SwiGLU','FFN_down','ffn_residual']:
   layers={p['layer'] for p in r['phases'] if p['name']==phase}
   check('full_layer_coverage',layers==set(range(model['num_hidden_layers'])),ident+':'+phase)
  check('unknowns',r['metrics']['full_physical_energy_J'] is None and r['metrics']['full_physical_area_mm2'] is None and r['metrics']['quality_reference_ppl'] is None,ident)
  check('storage',q['random_stream_SRAM_bytes']==0 and q.get('extra_probability_copy_bytes',0)==0 and q.get('extra_random_FIFO_bytes',0)==0,ident)
  if row['backend']=='integrated_service':
   check('backend',q['actual_backend_executed'] and c['random']['clock_hz']==c['core_hz']==100000000 and q['clock_ns']==10,ident)
   check('cost_boundary',not any(x in r['actions'] for x in ['rng_uniform_bit','local_probability_compare','sampler_delegated_drive_bits']),ident)
   check('cost_boundary',r['actions'].get('sampler_config_bits',0)==0,ident)
   net=q['network']
   if net:
    check('network_time',net['cycles']==math.ceil(r['metrics']['elapsed_ns']/10-1e-8),ident)
    for name,port in net['ports'].items():
     check('persistent_clock',port['cycles']==net['cycles']==port['counts']['clock_edges'],ident+':'+name)
     check('finite_frames',port['counts']['frames_generated']==port['counts']['responses_consumed'],ident+':'+name)
    beats=sum(x['bus_beats'] for x in net['seed_transport'].values())
    check('seed_bus',beats==len(net['seed_word_transcript'])==q['source_counts']['rng_seed_bus_beat'] if 'rng_seed_bus_beat' in q['source_counts'] else beats==len(net['seed_word_transcript']),ident)
    check('seed_bus',len(net['seed_events'])==sum(p['counts']['seed_loads'] for p in net['ports'].values()),ident)
   if c['ffn']['mode']=='sc':
    h,d=model['hidden_size'],model['intermediate_size'];g=64;e=c['ffn']['engines'];L=model['num_hidden_layers'];tok=c['decode_tokens']
    gu_groups=math.ceil(h/g);down_groups=math.ceil(d/g)
    streams=(gu_groups*math.ceil(math.ceil(2*d/g)/e)+down_groups*math.ceil(math.ceil(h/g)/e))*L*tok
    z=q['source_counts'];p=net['ports']['ffn']['counts'];saves=(gu_groups+down_groups)*L*tok
    check('FFN_replay',z['ffn_streams']==streams and z['ffn_samples_consumed']==streams*c['ffn']['samples']==p['frames_generated'],ident)
    check('FFN_replay',z['ffn_saves']==z['ffn_releases']==saves and z.get('ffn_restores',0)==streams-saves,ident)
    check('FFN_replay',p['commands']==saves*2+streams-saves,ident)
   costs=q['endpoint_costs']
   check('cost_boundary',math.isclose(sum(x['conditional_energy_J'] for x in costs),q['calibrated_endpoint_two_state_energy_J'],abs_tol=1e-15),ident)
   check('cost_boundary',math.isclose(q['calibrated_endpoint_two_state_energy_J'],r['energy_J'].get('RNG_endpoint_calibrated',0),abs_tol=1e-15),ident)
   check('cost_boundary',q['full_random_energy_J'] is None and q['full_random_area_mm2'] is None,ident)
   if row['attention'].startswith('screen_'):check('selector',q['source_counts']['selector_calls']==model['num_key_value_heads']*model['num_hidden_layers']*c['decode_tokens'],ident)
   if row['attention'] in ('pv','screen_pv'):check('PV_offsets',q['source_counts']['pv_systematic_offsets']==model['num_attention_heads']*model['num_hidden_layers']*c['decode_tokens'],ident)
  key=(row['model'],row['context'],row['seed'],row['ffn'],row['attention'],row.get('diagnostic_samples'))
  cases.setdefault(key,{})[row['backend']]=(row,r)
 for key,pair in cases.items():
  check('paired_cases',set(pair)=={'local_prng_interface','integrated_service'},str(key))
  a,ra=pair['local_prng_interface'];b,rb=pair['integrated_service']
  if key[3:5]==('bf16','exact'):
   check('reference_unchanged',a['TPOT_ms']==b['TPOT_ms'] and ra['DRAM']==rb['DRAM'] and ra['SRAM']==rb['SRAM'] and ra['phase_ns']==rb['phase_ns'],str(key))
  comparisons.append(dict(model=key[0],context=key[1],seed=key[2],ffn=key[3],attention=key[4],diagnostic_samples=key[5],
    legacy_TPOT_ms=a['TPOT_ms'],integrated_TPOT_ms=b['TPOT_ms'],delta_ms=b['TPOT_ms']-a['TPOT_ms'],
    delta_percent=100*(b['TPOT_ms']/a['TPOT_ms']-1),K_bytes=b['K_physical_bytes'],V_bytes=b['V_physical_bytes'],
    endpoint_mJ=b['rng_calibrated_endpoint_mJ'],endpoint_area_mm2=b['rng_calibrated_endpoint_area_mm2']))
 unchanged=not subprocess.check_output(['git','diff','--name-only','eb317e4f6fb1b0d8844887401f3275f128ef8a83','HEAD','--','architecture_tlm/random_service'],cwd=ROOT)
 check('backend_source_unchanged',unchanged,'original Issue95 model/RTL unchanged')
 result=dict(execution_commit=ex['commit'],run_helper_sha256=helper_sha,cases=len(s['rows']),checks=sum(N.values()),groups=dict(N),failures=fail,paired=comparisons,
    scope='synthetic complete-model scheduling, no PPL/new PT; S8 sampler diagnostics distinct from default quality budgets')
 out=ROOT/'work/jieruiz/96/integrated/AUDIT.json'
 with out.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps(dict(cases=result['cases'],checks=result['checks'],failures=fail)))
 return int(bool(fail))
if __name__=='__main__':sys.exit(main())
