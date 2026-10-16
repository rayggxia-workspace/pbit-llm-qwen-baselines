"""Export existing max4 calibration, no fitting and no pickle without weights_only."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    import torch
    p=argparse.ArgumentParser();p.add_argument('checkpoint',type=Path)
    p.add_argument('--output',type=Path,default=Path(__file__).parent/'configs')
    args=p.parse_args();data=torch.load(args.checkpoint,map_location='cpu',weights_only=True)
    args.output.mkdir(parents=True,exist_ok=True)
    for context in (2048,8192):
        key=f'{context}_0.3_max4';entry=data[key]
        d=dict(parameter=entry['parameter'].tolist(),temperature=entry['temperature'].tolist(),
            source_checkpoint_sha256=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
            source_key=key,method='max4 free-block mean/std sigmoid; first/last2 mandatory')
        dest=args.output/f'attention_max4_c{context}.json'
        dest.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8');print(dest)


if __name__=='__main__':main()
