"""Correct only reference-certificate presentation; preserve server originals.

The analytic IID/reference rows have no empirical MC95 pass certificate.
All numerical curves, budgets, source/input bindings and raw hashes are unchanged.
"""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path


def read(path):
    data=Path(path).read_bytes()
    return gzip.decompress(data) if str(path).endswith('.gz') else data


def transform(summary_bytes,table_bytes):
    original=json.loads(summary_bytes);result=copy.deepcopy(original)
    if original['status']!='completed' or original['completed_rows']!=90:raise ValueError('complete source required')
    changes=0
    for group in ('groups','groups_map_insufficient'):
        for row in result[group]:
            if row['method'] in ('iid','rejection'):
                row['mc95_gate_reached']=None;changes+=1
    restored=copy.deepcopy(result)
    for group in ('groups','groups_map_insufficient'):
        for before,after in zip(original[group],restored[group]):after['mc95_gate_reached']=before['mc95_gate_reached']
    assert restored==original
    result['publication_view']=dict(parent_server_summary_sha256=hashlib.sha256(summary_bytes).hexdigest(),
        parent_server_table_sha256=hashlib.sha256(table_bytes).hexdigest(),
        transform_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        changed_reference_annotations=changes,
        change='Only iid/rejection group MC95 certificate becomes null/not applicable; known independent expectation is not empirical MC95. All numerical results unchanged.')
    lines=[]
    for line in table_bytes.decode('utf-8').splitlines():
        cols=line.split('|')
        if len(cols)>5 and cols[3] in ('iid','rejection'):
            cols[4]=cols[4].split('（')[0]+'（解析参照，MC95不适用）';line='|'.join(cols)
        lines.append(line)
    return result,'\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser();p.add_argument('--summary',required=True);p.add_argument('--table',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    s,t=transform(read(a.summary),read(a.table))
    (out/'SUMMARY.json').write_text(json.dumps(s,indent=2)+'\n',encoding='utf-8',newline='\n')
    (out/'RESULTS_ZH.md').write_text(t,encoding='utf-8',newline='\n')
    print(json.dumps(dict(numerical_results_unchanged=True,publication_view=s['publication_view'])))


if __name__=='__main__':main()
