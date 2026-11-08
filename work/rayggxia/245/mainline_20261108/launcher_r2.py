"""Physical logical-KV input mapping revision; original jobs/snapshot retained."""
from pathlib import Path
import sys,ops
root=Path(__file__).resolve().parent
ops.HERE=root/'revision2';ops.HERE.mkdir(exist_ok=True)
action=sys.argv[1]
if action=='prepare':ops.prepare()
elif action in ('recover','dispatch','status'):
    name={'recover':'recover.py','dispatch':'dispatch_v2.py','status':'poll.py'}[action]
    exec(compile((root/name).read_text(),str(root/name),'exec'),dict(__name__='__main__',__file__=str(root/name)))
else:raise ValueError(action)
