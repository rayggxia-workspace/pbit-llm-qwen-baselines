"""Build adapter around pinned native ONNXim Core/WS; no full graph emulator."""
import concurrent.futures,difflib,hashlib,io,json,pathlib,subprocess,sys,tarfile,time,urllib.request
BASE='https://raw.githubusercontent.com/PSAL-POSTECH/ONNXim/8599bee46b311fb267ac34b0677ad7db3d8a8ccd/'
root=pathlib.Path(sys.argv[1]).resolve();root.mkdir(exist_ok=False);records={}
def sha(b):return hashlib.sha256(b).hexdigest()
def get(url):
 cache=pathlib.Path(__file__).with_name('download_cache')
 cached=cache/(hashlib.sha256(url.encode()).hexdigest()+'.bin')
 if cached.exists():
  index=json.loads((cache/'INDEX.json').read_text());record=next(x for x in index if x['url']==url)
  b=cached.read_bytes();assert sha(b)==record['sha256'];return b
 for i in range(3):
  try:
   with urllib.request.urlopen(url,timeout=45) as r:return r.read()
  except Exception:
   if i==2:raise
   time.sleep(i+1)
def download(rel):
 b=get(BASE+rel);p=root/'original'/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);return rel,b
paths=['src/'+x for x in ['Core.cc','Core.h','SystolicWS.cc','SystolicWS.h','SystolicOS.cc','SystolicOS.h','Sram.cc','Sram.h','SimulationConfig.h','Stat.h','Common.h','helper/HelperFunctions.h']]+['LICENSE']
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for rel,b in pool.map(download,paths):
  records[BASE+rel]={'sha256':sha(b),'bytes':len(b)}
  if rel.startswith('src/'):
   p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
patches={}
def patch(rel,fn):
 p=root/rel;old=p.read_text();new=fn(old);assert old!=new,rel;p.write_text(new,encoding='utf-8',newline='\n');patches[rel]=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='original/'+rel,tofile=rel))
patch('src/Core.h',lambda s:s.replace('#include "Dram.h"','#include "Common.h"'))
patch('src/Common.h',lambda s:''.join(x for x in s.splitlines(True) if not ('#include' in x and 'onnx/' in x)))
patch('src/SystolicWS.h',lambda s:s.replace('cycle_type get_vector_compute_cycles','virtual cycle_type get_vector_compute_cycles'))
patch('src/helper/HelperFunctions.h',lambda s:'#pragma once\n#include <algorithm>\n#define MAX(a,b) ((a)>(b)?(a):(b))\n#define MIN(a,b) ((a)<(b)?(a):(b))\n')
for url,rel in [('https://raw.githubusercontent.com/nlohmann/json/v3.11.2/single_include/nlohmann/json.hpp','deps/json/include/nlohmann/json.hpp'),('https://raw.githubusercontent.com/martinus/robin-hood-hashing/3.11.5/src/include/robin_hood.h','deps/robin/include/robin_hood.h')]:
 b=get(url);p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);records[url]={'sha256':sha(b),'bytes':len(b)}
url='https://codeload.github.com/gabime/spdlog/tar.gz/refs/tags/v1.11.0';b=get(url);records[url]={'sha256':sha(b),'bytes':len(b)}
with tarfile.open(fileobj=io.BytesIO(b),mode='r:gz') as tf:
 for m in tf.getmembers():
  parts=pathlib.PurePosixPath(m.name).parts
  if not m.isfile() or len(parts)<2 or parts[1] not in ('include','LICENSE'):continue
  p=root/'deps/spdlog'/pathlib.Path(*parts[1:]);assert p.resolve().is_relative_to(root)
  p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(tf.extractfile(m).read())
(root/'probe.cc').write_bytes(pathlib.Path(__file__).with_name('probe.cc').read_bytes())
(root/'ADAPTER.patch').write_text(''.join(patches.values()),encoding='utf-8',newline='\n')
for name in ('Core.cc','Sram.cc','SystolicWS.cc','SystolicOS.cc'):
 assert (root/'src'/name).read_bytes()==(root/'original/src'/name).read_bytes()
manifest={'upstream':'8599bee46b311fb267ac34b0677ad7db3d8a8ccd','downloaded':records,'implementation_unchanged':['Core.cc','Sram.cc','SystolicWS.cc','SystolicOS.cc'],'header_adapters':list(patches),'files':{str(p.relative_to(root)):{'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in root.rglob('*') if p.is_file()}}
(root/'SOURCE.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
cmd=['g++','-std=c++20','-O2','-DFMT_HEADER_ONLY','-Isrc','-Ideps/spdlog/include','-Ideps/json/include','-Ideps/robin/include','probe.cc','src/Core.cc','src/Sram.cc','src/SystolicWS.cc','src/SystolicOS.cc','-o','probe','-pthread']
(root/'COMMAND.json').write_text(json.dumps({'compile':cmd,'compiler':subprocess.check_output(['g++','--version']).decode()},indent=2)+'\n',encoding='utf-8',newline='\n')
with (root/'build.out').open('wb') as log:subprocess.run(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
with (root/'run.out').open('wb') as log:subprocess.run([str(root/'probe'),str(root/'RESULT.json')],cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
r=json.loads((root/'RESULT.json').read_text());assert r['status']=='completed' and len(r['cases'])==25
files={p.name:{'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in root.iterdir() if p.is_file()}
(root/'MANIFEST.json').write_text(json.dumps({'status':'completed','files':files},indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps({'status':'completed','cases':len(r['cases']),'directory':str(root)}))
