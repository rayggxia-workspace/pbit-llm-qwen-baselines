"""Partition existing PT cell-power rows; no EDA run or invented cone attribution."""
import argparse
from collections import Counter
import csv
import hashlib
import heapq
import json
import math
from pathlib import Path
import re

LABELS = {
    'lut_threshold_registers': 'BANK LUT output threshold registers',
    'lut_i0_registers': 'BANK I0 input registers',
    'lut_load_control_registers': 'BANK threshold-load control registers',
    'i0_schedule_registers': 'Global I0 schedule registers',
    'schedule_interval_registers': 'Global schedule interval registers',
    'rng_state_registers': 'LFSR state/seed registers',
    'edge_weight_registers': 'Edge probability/sign/valid registers',
    'node_config_registers': 'Node bias/clamp registers',
    'spin_state_registers': 'Spin state registers',
    'contribution_pipeline_registers': 'MAC contribution pipeline registers',
    'macsum_pipeline_registers': 'MAC sum pipeline registers',
    'vote_accumulator_registers': 'Majority accumulator registers',
    'vote_threshold_registers': 'BANK majority threshold registers',
    'bank_request_response_registers': 'BANK configuration request/response registers',
    'array_other_named_registers': 'Other named array registers',
    'array_unattributed_cells': 'Array cells without reliable RTL attribution',
    'global_register_block_other': 'Other cells in global register block',
    'pll_config_digital': 'PLL digital configuration cells, not PLL macro',
    'other_digital': 'Other digital standard cells',
}


def classify(name):
    array = 'pbit_array_chimera' in name
    if array and '_q_o_reg' in name:
        rules = [
            ('GEN_THRESHOLD_REG_', 'lut_threshold_registers'),
            ('u_pbit_bank_i0_level_ff_', 'lut_i0_registers'),
            ('u_pbit_bank_threshold_load_ff_', 'lut_load_control_registers'),
            ('u_lfsr32_rng32_state_ff_', 'rng_state_registers'),
            ('u_edge_reg_coupler_', 'edge_weight_registers'),
            ('u_mac_GEN_CONTRIB_REG_', 'contribution_pipeline_registers'),
            ('u_mac_macsum_ff_', 'macsum_pipeline_registers'),
            ('u_comparator_vote_spin_sum_ff_', 'vote_accumulator_registers'),
            ('u_pbit_bank_vote_threshold_ff_', 'vote_threshold_registers'),
        ]
        for token, group in rules:
            if token in name: return group
        if 'u_pbit_node_spin_ff_' in name: return 'spin_state_registers'
        if 'u_pbit_node_' in name: return 'node_config_registers'
        if any(s in name for s in ('u_pbit_bank_cfg_request_ff_', 'u_pbit_bank_cfg_response')):
            return 'bank_request_response_registers'
    if array:
        return 'array_other_named_registers' if re.search(r'_reg(?:_|\[|$)',name) else 'array_unattributed_cells'
    if 'pbit_reg_block' in name:
        if 'i0_ff_q_o_reg' in name: return 'i0_schedule_registers'
        if 'interval_ff_q_o_reg' in name: return 'schedule_interval_registers'
        return 'global_register_block_other'
    if 'pll_cfg_regs' in name: return 'pll_config_digital'
    return 'other_digital'


NUM = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
ROW = re.compile(r'^(.*?)\s+('+NUM+r')\s+('+NUM+r')\s+('+NUM+r')\s+('+NUM+r')\s+\(\s*'+NUM+r'\s*%\)\s*([a-z ]*)$')
TOTAL = re.compile(r'^Totals\s*\((\d+)\s+cells?\)\s+('+NUM+r')\s+('+NUM+r')\s+('+NUM+r')\s+('+NUM+r')')


def rows(path):
    started=False; header=False; pending=''; total=None
    with path.open(encoding='ascii') as f:
        for line in f:
            s=line.strip()
            if not started:
                if re.match(r'^Cell\s+Power\s+Power',s): header=True
                if header and s.startswith('---'): started=True
                continue
            if not s or s.startswith('---'): continue
            if s.startswith(('Error:','Warning:','Fatal:')):
                raise ValueError('Unexpected report message: '+s)
            pending=(pending+' '+s).strip()
            if pending.startswith('Totals'):
                match=TOTAL.match(pending)
                if match:
                    total=(int(match.group(1)),[float(match.group(i)) for i in range(2,6)])
                    break
            else:
                match=ROW.fullmatch(pending)
                if match:
                    # This netlist uses simple identifiers; wrapped names can be rejoined.
                    name=''.join(match.group(1).split())
                    values=[float(match.group(i)) for i in range(2,6)]
                    if not name or not all(math.isfinite(v) for v in values):
                        raise ValueError('Malformed cell row')
                    yield name,values,match.group(6).strip()
                    pending=''
            if len(pending)>16384:
                raise ValueError('Unrecognized/wrapped report row: '+pending[:300])
    if total is None: raise ValueError('Missing PT cell totals / incomplete report')
    yield None,total,''


def unit_scales(text):
    factors={'W':1.,'mW':1e-3,'uW':1e-6,'nW':1e-9,'pW':1e-12}
    def find(kind):
        m=re.search(r'^\s*'+kind+r' Units?\s*[:=]\s*('+NUM+r')\s*(W|mW|uW|nW|pW)\s*$',text,re.M)
        if not m: raise ValueError('Missing power unit: '+kind)
        return float(m.group(1))*factors[m.group(2)]
    dyn=find('Dynamic Power'); leak=find('Leakage Power')
    return [dyn,dyn,leak,dyn]


def summarize(run,out,slew='0p10'):
    folder=run/'pt'/('core_slew_'+slew+'ns')
    source=folder/'standard_cells.rpt'
    if not (folder/'CASE_COMPLETE.txt').exists(): raise ValueError('Incomplete PT slew case')
    scale=unit_scales((folder/'loaded_model_power.rpt').read_text())
    groups={}; seen=set(); attrs=Counter(); top=[]; negative=0
    sums=[0.,0.,0.,0.]; count=0
    for name,values,flags in rows(source):
        if name is None:
            reported_count,reported_raw=values
            reported=[a*b for a,b in zip(reported_raw,scale)]
            break
        if name in seen: raise ValueError('Duplicate cell row; review clock-only split: '+name)
        seen.add(name); count+=1
        v=[a*b for a,b in zip(values,scale)]
        if abs(sum(v[:3])-v[3])>max(1e-14,0.02*abs(v[3])):
            raise ValueError('Cell power columns do not reconcile: '+name)
        if any(x<0 for x in v): negative+=1
        if flags: attrs[flags]+=1
        category=classify(name)
        group=groups.setdefault(category,dict(cells=0,watts=[0.,0.,0.,0.],examples=[]))
        group['cells']+=1
        for i in range(4): group['watts'][i]+=v[i]; sums[i]+=v[i]
        if len(group['examples'])<5: group['examples'].append(name)
        item=(v[3],name,category,v[0],v[1],v[2])
        if len(top)<30: heapq.heappush(top,item)
        elif item[0]>top[0][0]: heapq.heapreplace(top,item)
    if count!=reported_count: raise ValueError('Cell row count differs from Totals')
    if sums[3]<=0: raise ValueError('Nonpositive total power')
    for actual,expected in zip(sums,reported):
        if not math.isclose(actual,expected,rel_tol=.005,abs_tol=1e-10):
            raise ValueError('Summed cell powers differ from Totals: {} vs {}'.format(sums,reported))
    out.mkdir(parents=True,exist_ok=True)
    result=[]
    for key,g in groups.items():
        v=g['watts']
        result.append(dict(category=key,label=LABELS[key],cells=g['cells'],internal_mW=v[0]*1000,
                           switching_mW=v[1]*1000,leakage_mW=v[2]*1000,total_mW=v[3]*1000,
                           percent_standard_total=100*v[3]/sums[3]))
    result.sort(key=lambda r:r['total_mW'],reverse=True)
    with (out/'power_breakdown.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(result[0])); w.writeheader(); w.writerows(result)
    with (out/'category_examples.tsv').open('w',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['category','cell'])
        for key,g in groups.items():
            for name in g['examples']: w.writerow([key,name])
    with (out/'top30_cells.tsv').open('w',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['total_mW','cell','category','internal_mW','switching_mW','leakage_mW'])
        for total,name,key,internal,switching,leak in sorted(top,reverse=True):
            w.writerow([total*1000,name,key,internal*1000,switching*1000,leak*1000])
    m=json.loads((run/'data/manifest.json').read_text())
    report=dict(status='BREAKDOWN_COMPLETE_REVIEW_REQUIRED',source=str(source),source_size=source.stat().st_size,
                core_frequency_MHz=m['core_frequency_MHz'],majority=m['majority'],sweeps=m['sweeps'],
                selected_slew_ns=float(slew.replace('p','.')),reported_cells=reported_count,
                summed_total_mW=sums[3]*1000,reported_total_mW=reported[3]*1000,
                attributes=dict(attrs),negative_power_rows_preserved=negative,categories=result,
                method='Exclusive instance-name groups; unknown optimized gates remain unattributed.',
                scope='Standard-cell-owned power only. PLL macro and IO excluded. Internal power is not clock-pin-only power.',
                caveats=['RNG/MAC/vote register groups do not include anonymous optimized combinational logic.',
                         'No isolated clock-pin power is inferred from internal power.',
                         'LUT is fixed combinational logic; threshold registers are a separate bank-shared pipeline.',
                         'Existing X/Z, model-range and pre-layout limitations still apply.'])
    (out/'power_breakdown.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def inventory(netlist):
    counts=Counter(); refs={}; module=''
    # Bounded recognizer for the delivered DC netlist, not a general HDL parser.
    inst=re.compile(r'^\s*(\w+_9TSVT)\s+(\S+)\s*\(')
    with netlist.open(encoding='ascii') as f:
        for line in f:
            mod=re.match(r'^module\s+(\w+)',line)
            if mod: module=mod.group(1)
            match=inst.match(line)
            if match and ('DFF' in match.group(1) or 'LATCH' in match.group(1)):
                group=classify(module+'/'+match.group(2)); counts[group]+=1
                refs.setdefault(group,Counter())[match.group(1)]+=1
    return dict(note='Netlist definition-instance inventory, not power or expanded hierarchy counts.',
                netlist_sha256=hashlib.sha256(netlist.read_bytes()).hexdigest(),
                register_counts=dict(counts),references={k:dict(v) for k,v in refs.items()})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path)
    p.add_argument('--out',type=Path)
    p.add_argument('--slew',choices=('0p05','0p10','0p20'),default='0p10')
    p.add_argument('--inventory-netlist',type=Path)
    a=p.parse_args()
    if a.inventory_netlist:
        print(json.dumps(inventory(a.inventory_netlist),indent=2))
    else:
        if a.run is None or a.out is None: p.error('--run and --out are required')
        print(json.dumps(summarize(a.run,a.out,a.slew),indent=2))
