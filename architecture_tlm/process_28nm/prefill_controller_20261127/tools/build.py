"""Build local RTL tests; toolchain is external, never copied into the PR."""
from pathlib import Path
import argparse, concurrent.futures, hashlib, json, os, subprocess, time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RTL = Path('C:/Users/86134/Documents/a_P_BIT/architecture_tlm/rtl_stage2_integration_20261121')

def sources(kind, rtl):
    if kind == 'state':
        return [ROOT/'rtl/prefill_state.sv']
    if kind == 'prompt':
        return [ROOT/'rtl/prefill_prompt.sv']
    deps = rtl/'ffn_sampling_config_20261124/deps'
    names = ['format.sv','rng_shared64_map.sv','primitives.sv','compare.sv',
             'sigmoid.sv','codecs.sv','wd_wide.sv','activity.sv','paired.sv','ffn_gu_codec.sv']
    result = [deps/n for n in names]
    result += [rtl/'ffn_sampling_config_20261124/rtl/ffn_config_rng.sv']
    result += [rtl/'cim_single_zone_20261124/rtl'/n for n in
               ['plpu_cim_bank32x128.sv','plpu_cim_single_zone.sv','plpu_cim_write_router.sv']]
    result += [rtl/'ffn_slots12_20261126/rtl'/n for n in ['tile_worker.sv','shared_dma.sv']]
    return result + [ROOT/'rtl'/n for n in ['prefill_core.sv','prefill_state.sv','prefill_top.sv']]

def build(kind, rtl, jobs=4):
    vr=rtl/'shared_matrix_20261121/tools/local/verilator_5_054/verilator'
    cr=rtl/'shared_matrix_20261121/tools/local/cxx_1_23_0/w64devkit'
    out=ROOT/'results'/('build_'+kind); out.mkdir(parents=True, exist_ok=True)
    env=os.environ.copy();env['VERILATOR_ROOT']=str(vr)
    env['PATH']=str(cr/'bin')+os.pathsep+env['PATH']
    top='plpu_prefill_'+('top' if kind=='matrix' else kind)
    src=sources(kind,rtl); driver=ROOT/'tb'/(kind+'.cpp')
    cmd=[str(vr/'bin/verilator_bin.exe'),'--cc','--no-timing','--assert',
         '--top-module',top,'--prefix','Vdut','--Mdir',str(out),'-Wno-fatal',
         '--output-split','12000']+[str(p) for p in src]
    aux=ROOT/'tb/util.h'
    receipt={'kind':kind,'tool':'Verilator 5.054','verilate':cmd,
             'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in src+[driver,aux]},
             'compile':[]}; start=time.time()
    r=subprocess.run(cmd,env=env,capture_output=True,timeout=240)
    (out/'verilate.log').write_bytes(r.stdout+r.stderr);receipt['verilate_code']=r.returncode
    (out/'BUILD.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace')[-9000:])
    cpp=list(out.glob('*.cpp'))+[vr/'include/verilated.cpp',vr/'include/verilated_threads.cpp',driver]
    # Header/source hashes gate reuse of local objects after a failed driver build.
    hh=hashlib.sha256(b''.join(p.read_bytes() for p in sorted(out.glob('*.h')))+aux.read_bytes()).hexdigest()
    def compile_one(p):
        obj=out/(p.stem+'.o');stamp=out/(p.stem+'.object_sha')
        sh=hashlib.sha256(p.read_bytes()+hh.encode()).hexdigest()
        cmd=[str(cr/'bin/g++.exe'),'-std=c++17','-O1','-pthread','-DVL_TIME_CONTEXT',
             '-I'+str(out),'-I'+str(vr/'include'),'-I'+str(vr/'include/vltstd'),'-c',str(p),'-o',str(obj)]
        if obj.exists() and stamp.exists() and stamp.read_text()==sh:
            return {'command':cmd,'code':0,'object':str(obj),'cached':True}
        r=subprocess.run(cmd,env=env,capture_output=True,timeout=360)
        (out/(p.stem+'.log')).write_bytes(r.stdout+r.stderr)
        if not r.returncode:stamp.write_text(sh)
        return {'command':cmd,'code':r.returncode,'object':str(obj),'cached':False}
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        receipt['compile']=list(pool.map(compile_one,cpp))
    (out/'BUILD.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    if any(r['code'] for r in receipt['compile']):
        raise RuntimeError('C++ compile failed: '+str([r['object'] for r in receipt['compile'] if r['code']]))
    exe=out/(kind+'_sim.exe')
    args=['-pthread','-static','-o',str(exe)]+[r['object'] for r in receipt['compile']]+['-lws2_32']
    rsp=out/'link_args.rsp';rsp.write_text('\n'.join('"'+x.replace('\\','/')+'"' for x in args),encoding='utf-8')
    r=subprocess.run([str(cr/'bin/g++.exe'),'@'+str(rsp)],env=env,capture_output=True,timeout=180)
    (out/'link.log').write_bytes(r.stdout+r.stderr)
    receipt.update(link_code=r.returncode,seconds=time.time()-start)
    (out/'BUILD.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    if r.returncode:raise RuntimeError('link failed')
    print(exe,flush=True)
    return exe

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=['state','prompt','matrix'],required=True)
    p.add_argument('--rtl-root',type=Path,default=DEFAULT_RTL);p.add_argument('--jobs',type=int,default=4)
    a=p.parse_args();build(a.kind,a.rtl_root,a.jobs)
