import pathlib,subprocess,json,hashlib,importlib.util,sys,zipfile
out=pathlib.Path(__file__).resolve().parent;root=out.parents[1]/'tmp/pr55-review-round8-20261023'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('storage_review',root/'work/amlink1219/118/validate_artifacts.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.WORK=out/'120_artifacts';m.WORK.mkdir(exist_ok=True);m.main()
rtl=root/'architecture_tlm/encoding_restore_contract/results/rtl_2778';v=read(rtl/'VALIDATION.json')
for n,s in v['source_sha256'].items():assert sha(root/n)==s,n
assert sha(rtl/'INPUT_MANIFEST.json')==v['input_manifest_sha256']
assert v['passed'] and len(v['results'])==45
assert sum(x['received'] for x in v['results'])==11667
assert sum(x['flushed'] for x in v['results'])==180
for x in v['results']:assert x['accepted']==x['received']+x['flushed']
smoke=root/'architecture_tlm/ffn_cycle_integration/results/smoke_20261023';manifest=read(smoke/'MANIFEST.json')
for n,x in manifest.items():assert sha(smoke/n)==x['sha256'] and (smoke/n).stat().st_size==x['bytes'],n
record=dict(rtl_source_files=len(v['source_sha256']),rtl_scenarios=45,outputs=11667,reset_flushed=180,smoke_original_files=len(manifest),scope='source and public receipt authentication; existing RTL outputs, no new RTL simulation or full-size FFN run')
(out/'125_artifacts.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n');print(record)
folder=root/'architecture_tlm/memory_savings_20261023';idx=read(folder/'SOURCE_INDEX.json')
cache=root/'work/jieruiz/129/evidence';cache.mkdir(exist_ok=True)
for item in idx['sources']:
 raw=subprocess.check_output(['git','-C',str(root),'show',item['commit']+':'+item['path']])
 assert hashlib.sha256(raw).hexdigest()==item['sha256'] and len(raw)==item['bytes'],item['path']
 for n,part in [(120,'ffn_storage_contract'),(127,'ffn_dataflow_optimization'),(119,'resource_optimization_v1')]:
  if part in item['path']:(cache/f'pr{n}.md').write_bytes(raw)
before={n:sha(folder/n) for n in ['CALCULATIONS.json','SOURCE_INDEX.json']}
subprocess.run([sys.executable,'-B','-X','utf8',str(root/'work/jieruiz/129/calculate.py')],cwd=root,check=True)
assert {n:sha(folder/n) for n in before}==before
validation=read(root/'work/jieruiz/129/VALIDATION.json')
for x in validation['files']:assert sha(root/x['path'])==x['sha256'] and (root/x['path']).stat().st_size==x['bytes']
doc=next(folder.glob('*.docx'))
with zipfile.ZipFile(doc) as z:assert z.testzip() is None
record=dict(source_blobs=len(idx['sources']),recalculated_rows=8,exact_derived_json=True,deliverable_hashes=len(validation['files']),docx_zip_integrity=True,scope='numbers/source/deliverable bytes; historical 7-page rendering receipt inspected, not rerendered this review')
(out/'130_artifacts.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n');print(record)
