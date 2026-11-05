from pathlib import Path
import urllib.request,json,hashlib,zipfile,io,subprocess,shutil,concurrent.futures
R=Path(__file__).resolve().parents[4];W=R.parents[1];P=R/'architecture_tlm/bf16_ppa_20261028';A=W/'project_archives/matrix204_bf16_ppa_20261028'
P.mkdir(parents=True,exist_ok=True);A.mkdir(parents=True,exist_ok=True)
def fetch(url):return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BF16-PPA-repro/1.0'}),timeout=60).read()
repos=[('openhwfoundation/cvfpu','develop','cvfpu'),('pulp-platform/common_cells','v1.38.0','common_cells')]
records=[]
for repo,ref,name in repos:
    marker=A/(name+'_'+ref.replace('/','_')+'_upstream.json')
    if marker.exists():d=json.loads(marker.read_text());commit=d['commit']
    else:
        commit=json.loads(fetch('https://api.github.com/repos/'+repo+'/commits/'+ref))['sha']
        d={'repo':repo,'ref':ref,'commit':commit};marker.write_bytes((json.dumps(d,indent=2)+'\n').encode())
    arc=A/(name+'_'+commit+'_minimal.zip')
    files=(['src/fpnew_pkg.sv','src/fpnew_fma.sv','src/fpnew_fma_multi.sv','src/fpnew_classifier.sv','src/fpnew_rounding.sv','vendor/cvw/fma/fmalza.sv','LICENSE.solderpad','LICENSE.apache','README.license.md'] if name=='cvfpu' else ['src/lzc.sv','src/cf_math_pkg.sv','include/common_cells/registers.svh','include/common_cells/assertions.svh','LICENSE'])
    def one(rel):
        dst=P/'vendor'/name/rel;dst.parent.mkdir(parents=True,exist_ok=True)
        if not dst.exists() or name=='common_cells':dst.write_bytes(fetch('https://raw.githubusercontent.com/'+repo+'/'+commit+'/'+rel))
        return rel,dst.read_bytes()
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:blobs=list(pool.map(one,files))
    if not arc.exists():
        with zipfile.ZipFile(arc,'w',zipfile.ZIP_DEFLATED) as z:
            for n,b in blobs:z.writestr(n,b)
    records.append(d|{'archive':str(arc),'archive_sha256':hashlib.sha256(arc.read_bytes()).hexdigest()})
(P/'UPSTREAM.json').write_bytes((json.dumps(records,indent=2)+'\n').encode())
F=P/'flow';F.mkdir(exist_ok=True)
for n in ['upstream.py','common.tcl','library_conditions.tcl','dc.tcl','power_bulk.tcl','power_vcd.py','power_parse.py','vcd_alias_v2.py','constant_ports.py']:
    src=R/'architecture_tlm/module_energy_20261028/flow'/n
    shutil.copyfile(src,F/n)
print(json.dumps({'upstream':records,'package':str(P)},indent=2))
