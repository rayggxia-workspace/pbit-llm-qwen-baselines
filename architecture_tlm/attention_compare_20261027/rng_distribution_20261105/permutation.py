"""Targeted follow-up after the four-peak GF diagnostic; same frozen executable."""
from pathlib import Path
import sys,json,shutil
import numpy as np
P=Path(__file__).resolve().parent;A=P.parents[2].parents[1]/'project_archives/attention_rng198_20261105';D=A/'permutation'
if sys.argv[1]=='prepare':
 D.mkdir(exist_ok=True);shutil.copyfile(A/'gf_tables.bin',D/'gf_tables.bin');base=json.loads((A/'rows_private.json').read_bytes())[2]
 sets=[[0,1,2,3],[0,16,32,48],[0,32,64,96],np.random.default_rng(19805).choice(128,4,replace=False).tolist()]
 rr=[dict(id='four_peaks_p'+str(i),threshold=[max(base['threshold']) if j in ix else min(base['threshold']) for j in range(128)],peak_indices=ix,kind='synthetic') for i,ix in enumerate(sets)]
 (D/'rows.txt').write_bytes((str(len(rr))+'\n'+''.join(x['id']+' '+' '.join(map(str,x['threshold']))+'\n' for x in rr)).encode())
 (D/'rows_private.json').write_bytes((json.dumps(rr,indent=2)+'\n').encode())
else:
 rr=json.loads((D/'rows_private.json').read_bytes());m=np.loadtxt(D/'long_meta.tsv',skiprows=1,dtype=int);h=np.fromfile(D/'long_hist.bin',dtype='<u4').reshape(-1,128)/32768;out=[]
 modes=['iid_iid','gf_iid','iid_biv','gf_biv','shared_lfsr1_iid','shared_iid_iid','shared_lfsr8_iid']
 for mode in range(4):
  for ri,r in enumerate(rr):
   x=h[(m[:,0]==mode)&(m[:,1]==ri)];p=np.array(r['threshold'])/256;odds=p/(1-p);pi=odds/odds.sum();delta=x[:,r['peak_indices']].sum(1)-pi[r['peak_indices']].sum()
   out.append(dict(mode=modes[mode],row=r['id'],TV=float(abs(x.mean(0)-pi).sum()/2),peak_mass_error=float(delta.mean()),peak_mass_SE=float(delta.std(ddof=1)/np.sqrt(8))))
 (P/'PERMUTATION_SUMMARY.json').write_bytes((json.dumps(out,indent=2)+'\n').encode())
 print('Permutation analysis complete:',len(out),'summaries')
