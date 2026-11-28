"""Materialize only the existing small registry objects in this sparse task tree."""
from pathlib import Path
import json,subprocess

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[2]
def blob(path):
    return subprocess.run(['git','show','HEAD:'+path],cwd=REPO,check=True,capture_output=True).stdout
def main():
    # These two exact Git blob identities were matched to the current PR head.
    for name,want in [('catalog.json','d2681f07c2930cb0098765956842e59357926589'),
                      ('registry.py','e5e29fe11390fc360ebf451871d440ec89277a25')]:
        got=subprocess.run(['git','rev-parse','HEAD:digital_circuit_simulation_registry/'+name],cwd=REPO,check=True,capture_output=True,text=True).stdout.strip()
        if got!=want:raise RuntimeError('Recheck remote registry before materializing')
    prefix='digital_circuit_simulation_registry/'
    catalog=json.loads(blob(prefix+'catalog.json'))
    names=['catalog.json','registry.py','archive_inventory.csv']+['records/'+x+'.json' for x in catalog['record_ids']]
    for name in names:
        path=REPO/prefix/name;data=blob(prefix+name)
        if path.exists() and path.read_bytes()!=data:raise RuntimeError('Existing task registry differs: '+str(path))
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    print('Materialized existing registry:',len(catalog['record_ids']),'records; no originals changed')
if __name__=='__main__':main()
