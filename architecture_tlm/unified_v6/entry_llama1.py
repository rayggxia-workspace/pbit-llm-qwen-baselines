from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from architecture_tlm.unified_v6.run import main
if __name__=='__main__':main(['--model','llama1']+sys.argv[1:])
