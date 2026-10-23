"""Recollect small reports after a scheduler kill; never marks a run passed."""
import argparse
from pathlib import Path
from run import archive
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('result',type=Path);a=p.parse_args()
    if not a.result.is_dir():p.error('Existing result directory required')
    archive(a.result.resolve())
