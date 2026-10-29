import subprocess,json
from pathlib import Path
R=Path('C:/Users/86134/Documents/a_P_BIT/tmp/group64-scale-issue206-20261028');W=R/'work/jieruiz/206'
v=json.loads(sorted(W.glob('FULL_WT2_SUBMISSION_*.json'))[-1].read_bytes());root=v['root'];head=v['commit'][:8]
ssh=['C:/Windows/System32/OpenSSH/ssh.exe','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','-o','BatchMode=yes','lab-server-ai']
s='shopt -s nullglob\nsqueue -u "$(id -un)" -o "%.18i %.24j %.10T %.9M %R"\n'
s+='tail -n 9 '+root+'/logs/full-cpu-'+head+'-'+v['cpu_job']+'.out\n'
s+='tail -n 9 '+root+'/logs/full-gate-'+head+'-'+v['gate_job']+'.out\n'
s+='for f in '+root+'/logs/full-'+head+'-'+v['array']+'_*.out; do echo "$f"; tail -n 2 "$f"; done\n'
print(subprocess.check_output(ssh+['bash -l -s'],input=s.encode(),timeout=50).decode())
