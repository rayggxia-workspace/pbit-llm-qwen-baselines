"""Replay frozen vectors against parameter-specific tops before server submission."""
from pathlib import Path
import argparse,subprocess,json,hashlib
H=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser();p.add_argument('--vectors',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    tools=Path('C:/Users/86134/Documents/a_P_BIT/sc_weight_storage_or4_20261014/tools/iverilog')
    ivl=tools/'lib/ivl';index=json.loads((a.vectors/'TRACES.json').read_bytes());results=[]
    for s in json.loads((H/'CASES.json').read_bytes())['tops']:
        top=s['top'];binary=(a.output/(top+'.vvp')).resolve()
        cmd=[str(tools/'bin/iverilog.exe'),'-B',str(ivl),'-g2012','-Wall','-s','tb_eda','-DSYNTHESIS','-DAC_WINNER','-DAC_TOP='+top,'-DAC_COUNT_W='+str(s['count_width']),'-o',str(binary)]+[str(H/'rtl'/f) for f in ['ac_scan.sv','ac_winner128.sv',top+'.sv']]+[str(H/'tb_eda.sv')]
        r=subprocess.run(cmd,capture_output=True);(a.output/(top+'_compile.log')).write_bytes(r.stdout+r.stderr);assert r.returncode==0,(top,r.stderr)
        for row in index[top]:
            folder=(a.vectors/top/row['trace']).resolve()
            r=subprocess.run([str(tools/'bin/vvp.exe'),'-M',str(ivl),str(binary),'+VECTORS='+str(folder/'vectors.txt')],capture_output=True)
            log=a.output/(top+'_'+row['trace']+'.log');log.write_bytes(r.stdout+r.stderr)
            lines=lambda b:[x for x in b.decode().splitlines() if x.startswith(('P ','C '))]
            assert r.returncode==0 and lines(r.stdout)==lines((folder/'golden.log').read_bytes()),(top,row['trace'])
            results.append(dict(top=top,trace=row['trace'],cycles=row['cycles'],status='pass',log_sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
        print(top+' PASS',flush=True)
    out=dict(status='pass',checks=len(results),cycles=sum(x['cycles'] for x in results),cases=results,trace_index_sha256=hashlib.sha256((a.vectors/'TRACES.json').read_bytes()).hexdigest())
    (a.output/'VALIDATION.json').write_bytes((json.dumps(out,indent=2)+'\n').encode());print(json.dumps({k:v for k,v in out.items() if k!='cases'}))
if __name__=='__main__':main()
