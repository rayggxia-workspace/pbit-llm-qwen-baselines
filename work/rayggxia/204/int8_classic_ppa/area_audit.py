"""Audit cell-area sums and storage boundaries after user's area question."""
from pathlib import Path
import hashlib,json,math,tarfile
HERE=Path(__file__).resolve().parent;R=HERE.parents[3];W=R.parents[1];A=W/'project_archives'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
cases=[('SC54',A/'matrix204_module_energy_20261028/matrix204_modules_v2_20261028/ppa_28/reports.tar.gz','replay'),('INT32',A/'matrix204_int8_classic_ppa_20261028/ppa_38445883_0/reports.tar.gz','matched'),('INT22',A/'matrix204_int8_classic_ppa_20261028/ppa_38445883_1/reports.tar.gz','matched')]
out=[]
for name,p,mode in cases:
 with tarfile.open(p) as t:
  m=json.load(t.extractfile('RETURN_MANIFEST.json'))['files'];raw=t.extractfile('RESULT.json').read();assert hashlib.sha256(raw).hexdigest()==m['RESULT.json'];r=json.loads(raw)
 q=next(x for x in r['windows'] if x['mode']==mode and x['seed']==17)
 group={k:dict(cells=v['cells'],raw_area_um2=v['area_um2'],area_55eq_um2=.81*v['area_um2']) for k,v in q['groups'].items()}
 assert math.isclose(sum(v['raw_area_um2'] for v in group.values()),q['area_um2'],rel_tol=1e-12)
 out.append(dict(core=name,archive=str(p),archive_sha256=sha(p),result_member_sha256=m['RESULT.json'],cells=q['cells'],raw_area_um2=q['area_um2'],area_55eq_um2=.81*q['area_um2'],groups=group))
result=dict(type='Existing mapped-inventory reanalysis, no new EDA',date='2026-10-28',cases=out,boundaries={'SC54':'Six parallel weight magnitude planes1..6 x64 events; signed positive/negative OR4, popcount-difference, nine-bit saturated counters.54 counter bits+16 result+5 sample+2 state=77 registers; external weight/event/sign ports, no weight/probability register bank or SRAM/RNG.','INT32':'Four signed8x8 multipliers reused over16 beats;64 product register bits+32 sum+13 control=109 registers. External32-bit A and32-bit B stream, no resident64-weight bank/SRAM.','INT22':'Same four multipliers, ten fewer sum bits;99 registers; outputs remain32-bit by sign extension.'},interpretation='Small stochastic AND does not imply minimum whole-core area. Current SC saves sequential area but has more parallel combinational counting/sign/recovery logic. N64 problem size is not hardware parallelism. Compare area together with throughput/latency, precision and full storage/delivery boundary.',source_files=[dict(path=n,sha256=sha(R/n)) for n in ['architecture_tlm/module_energy_20261028/rtl/tops.sv','architecture_tlm/int8_classic_ppa_20261028/rtl/dot4.sv']])
(HERE/'AREA_AUDIT.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())
for x in out:print(x['core'],x['area_55eq_um2'],x['groups'])
