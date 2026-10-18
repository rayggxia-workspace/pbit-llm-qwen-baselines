"""Model-specific entry point; historical implementations remain reproducible."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scripts'))
from model_workspace import main

if __name__ == '__main__':
    raise SystemExit(main(HERE.name))
