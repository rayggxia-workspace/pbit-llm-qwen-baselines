"""Load exact existing implementations from a caller-owned, hashed source cache.

No dependency source is copied into this task's tracked module. A cache can be
recreated from the recorded Git commits; an unpublished backend object must
already exist locally and is never described as merged/public by this loader.
"""
import argparse
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

SOURCES={
 'feed':{'commit':'ecb0f5efb19be8ad72bf7ef0ee0109a3decd5ca5','pr':120,'files':[
  'architecture_tlm/ffn_storage_contract/'+p for p in ('__init__.py','model.py','counter.py')]},
 'restore':{'commit':'8007d98f15676ad316180ee18b5d1b29aa00af95','pr':122,'files':[
  'architecture_tlm/encoding_restore_contract/'+p for p in ('__init__.py','adapter.py','arithmetic.py','backend.py')]+[
  'architecture_tlm/digital_ppa_v1/sim/validate.py','format_conversion_rtl_20261016/sim/reference.py']},
 'backend':{'commit':'6a56940900cf7e104f1c6c10ca8698c739e1da52','issue':116,'public_at_initial_freeze':False,'files':[
  'architecture_tlm/cycle_v1/'+p for p in ('__init__.py','contracts.py','kernel.py','memory.py')]}}

def record(path):
 raw=path.read_bytes();return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def materialize(repository,destination):
 destination=Path(destination).resolve()
 if destination.exists():return verify(destination)
 destination.mkdir(parents=True)
 records={}
 for name,spec in SOURCES.items():
  files={}
  for rel in spec['files']:
   raw=subprocess.check_output(['git','-c','credential.username=amlink1219','-C',str(repository),'show',spec['commit']+':'+rel])
   path=destination/name/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);files[rel]=record(path)
  records[name]={**spec,'files':files}
 lock={'repository':'rayggxia-workspace/pbit-llm-qwen-baselines','sources':records,
       'scope':'Exact dependency source cache; not a merge or republication of another task.'}
 (destination/'DEPENDENCIES.json').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf-8',newline='\n')
 return verify(destination)

def verify(root):
 root=Path(root).resolve();lock=json.loads((root/'DEPENDENCIES.json').read_text(encoding='utf-8'))
 for name,expected in SOURCES.items():
  actual=lock['sources'][name]
  if actual['commit']!=expected['commit'] or set(actual['files'])!=set(expected['files']):raise ValueError('dependency identity changed: '+name)
  for rel,info in actual['files'].items():
   if record(root/name/rel)!=info:raise ValueError('dependency bytes changed: '+rel)
 return lock

def package(folder,key):
 if key not in sys.modules:
  spec=importlib.util.spec_from_file_location(key,folder/'__init__.py',submodule_search_locations=[str(folder)])
  module=importlib.util.module_from_spec(spec);sys.modules[key]=module;spec.loader.exec_module(module)
 return key

def load(root):
 root=Path(root).resolve();lock=verify(root)
 digest=hashlib.sha256(json.dumps(lock,sort_keys=True).encode()).hexdigest()
 feedkey=package(root/'feed/architecture_tlm/ffn_storage_contract','_df_feed_'+digest)
 restorekey=package(root/'restore/architecture_tlm/encoding_restore_contract','_df_restore_'+digest)
 backend=importlib.import_module(restorekey+'.backend')
 api,hashes=backend.load(root/'backend')
 profile=importlib.import_module(restorekey+'.adapter').Profile
 return SimpleNamespace(api=api,feed=importlib.import_module(feedkey+'.model'),
  restore=importlib.import_module(restorekey+'.arithmetic'),Profile=profile,lock=lock,root=root,source_sha256=digest)

def main():
 p=argparse.ArgumentParser();p.add_argument('--repository',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 lock=materialize(a.repository,a.output);deps=load(a.output)
 print(json.dumps({'sources':len(lock['sources']),'files':sum(len(x['files']) for x in lock['sources'].values()),'source_sha256':deps.source_sha256}))

if __name__=='__main__':main()
