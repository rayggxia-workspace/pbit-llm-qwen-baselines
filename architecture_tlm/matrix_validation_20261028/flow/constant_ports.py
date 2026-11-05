"""Complete absent PT attributes ONLY for directly tied top-level outputs.

Require an explicit mapped-Verilog literal assignment and identical constant VCD
activity. Preserve the unmodified PT table and a per-port proof. No leaf-cell pin,
unknown signal, or nonconstant waveform may use this path.
"""
import csv,hashlib,json,re
def complete(pt,audit,netlist,top):
 path=pt/'output_activity.tsv';raw=path.read_bytes()
 with path.open() as f:rows=list(csv.DictReader(f,delimiter='\t'))
 missing=[x for x in rows if x['toggle_rate']=='NA' or x['static_probability']=='NA']
 if not missing:return []
 source=netlist.read_text();z=re.search(r'\bmodule\s+'+re.escape(top)+r'\b(.*?)\bendmodule',source,re.S)
 if z is None:raise ValueError('Missing mapped top for constant proof')
 proofs=[]
 for row in missing:
  name=row['name']
  if not re.fullmatch(r'[A-Za-z_]\w*',name):raise ValueError('Unproved non-port activity '+name)
  m=re.search(r'\bassign\s+'+re.escape(name)+r"\s*=\s*1'[bB]([01])\s*;",z[1])
  if m is None:raise ValueError('Absent explicit top tie '+name)
  value=int(m[1]);e=audit['expected_activity'][name]
  if e['toggle_rate_per_ns']!=0 or e['static_probability']!=value:raise ValueError('Constant tie disagrees with VCD '+name)
  row['toggle_rate']='0';row['static_probability']=str(value)
  proofs.append({'port':name,'literal_value':value,'VCD_toggle_rate_per_ns':0,'VCD_static_probability':value,
   'mapped_netlist_sha256':hashlib.sha256(netlist.read_bytes()).hexdigest(),'assignment':m[0]})
 (pt/'output_activity.unmodified.tsv').write_bytes(raw)
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['name','toggle_rate','static_probability'],delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)
 (pt/'CONSTANT_TOP_PORT_PROOF.json').write_text(json.dumps({'proofs':proofs,'unmodified_PT_table_sha256':hashlib.sha256(raw).hexdigest(),
  'derived_PT_table_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'leaf_pins_relaxed':0},indent=2)+'\n')
 return proofs
